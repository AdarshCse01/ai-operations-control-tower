"""
Recommendations API router for Phase 5 Real AI Decision Intelligence.
Enforces RBAC:
- DASHBOARD_READ for listing recommendations
- RECOMMENDATION_DECIDE for approving/rejecting proposals
- DATA_MANAGE for executing approved recommendations
All actions are tracked with database-backed audit logs.
"""
from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.repositories.recommendation import RecommendationRepository
from app.schemas.recommendation import (
    RecommendationApprovalRequest,
    RecommendationExecuteRequest,
    RecommendationListResponse,
    RecommendationRead,
)
from app.services.recommendation_engine import (
    execute_approved_recommendation,
    record_human_decision,
    sync_and_generate_recommendations,
)

router = APIRouter()


@router.get("", response_model=RecommendationListResponse)
async def list_recommendations(
    status_filter: str | None = Query(default=None, alias="status"),
    recommendation_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Synchronizes operational recommendations from active risk signals and returns
    deduplicated persistent recommendations.
    """
    # 1. Sync live database state and detect fresh or updated recommendations
    await sync_and_generate_recommendations(session)

    # 2. Query repository with filters
    repo = RecommendationRepository(session)
    items, total = await repo.list_filtered(
        status=status_filter,
        rec_type=recommendation_type,
        limit=limit,
        offset=offset,
    )

    # 3. Aggregate operational counts
    all_recs, _ = await repo.list_filtered(limit=500, offset=0)
    pending_cnt = sum(1 for r in all_recs if r.status == "PENDING")
    approved_cnt = sum(1 for r in all_recs if r.status == "APPROVED")
    executed_cnt = sum(1 for r in all_recs if r.status == "EXECUTED")

    read_items = [RecommendationRead.model_validate(r) for r in items]

    return RecommendationListResponse(
        items=read_items,
        count=len(read_items),
        pending_count=pending_cnt,
        approved_count=approved_cnt,
        executed_count=executed_cnt,
        data_mode="live_database",
    )


@router.post("/{recommendation_id}/approval")
async def record_approval(
    recommendation_id: str,
    payload: RecommendationApprovalRequest,
    current_user: User = Depends(require_permission(Permission.RECOMMENDATION_DECIDE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Records a human operator approval or rejection on a PENDING recommendation.
    Enforces RECOMMENDATION_DECIDE permission and creates persistent AuditLog record.
    """
    repo = RecommendationRepository(session)
    rec_uuid: uuid.UUID | None = None

    try:
        rec_uuid = uuid.UUID(recommendation_id)
    except ValueError:
        # Fallback lookup by entity_id for backward compatibility
        found = await repo.get_pending_by_entity("STOCK_REORDER", recommendation_id)
        if not found:
            all_recs, _ = await repo.list_filtered(limit=50)
            for r in all_recs:
                if str(r.id) == recommendation_id or r.entity_id == recommendation_id:
                    rec_uuid = r.id
                    break
        else:
            rec_uuid = found.id

    if not rec_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

    try:
        rec = await record_human_decision(
            recommendation_id=rec_uuid,
            approved=payload.approved,
            current_user=current_user,
            comment=payload.comment,
            session=session,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    decision_status = "approved" if payload.approved else "rejected"
    return {
        "id": str(rec.id),
        "recommendation_id": str(rec.id),
        "status": decision_status,
        "recommendation_status": rec.status,
        "comment": payload.comment,
        "actor": current_user.email,
        "occurred_at": (rec.decided_at or datetime.now(timezone.utc)).isoformat(),
        "event_type": "recommendation.decision_recorded",
        "item": RecommendationRead.model_validate(rec),
    }


@router.post("/{recommendation_id}/execute")
async def execute_recommendation(
    recommendation_id: str,
    payload: RecommendationExecuteRequest,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
):
    """
    Transactionally executes an APPROVED recommendation.
    Re-validates target entity state before applying operational changes (e.g. stock receipt).
    Enforces idempotency and logs the execution outcome in the AuditLog.
    """
    try:
        rec_uuid = uuid.UUID(recommendation_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recommendation UUID")

    try:
        rec, result_data = await execute_approved_recommendation(
            recommendation_id=rec_uuid,
            current_user=current_user,
            comment=payload.comment,
            session=session,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg.lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return {
        "id": str(rec.id),
        "recommendation_id": str(rec.id),
        "status": "executed",
        "recommendation_status": rec.status,
        "execution_result": result_data,
        "comment": payload.comment,
        "actor": current_user.email,
        "executed_at": (rec.executed_at or datetime.now(timezone.utc)).isoformat(),
        "item": RecommendationRead.model_validate(rec),
    }
