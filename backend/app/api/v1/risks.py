"""Risk intelligence router protected by RBAC ANALYTICS_READ permission."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.risk import RiskResponse
from app.services.risk_engine import detect_operational_risks

router = APIRouter()


@router.get("", response_model=RiskResponse)
async def list_risks(
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.ANALYTICS_READ)),
):
    """
    Computes explainable, deterministic operational risk scores across products,
    warehouses, inventory stockout boundaries, supplier SLAs, and orders.
    """
    items = await detect_operational_risks(session)
    critical_cnt = sum(1 for r in items if r.severity == "CRITICAL")
    high_cnt = sum(1 for r in items if r.severity == "HIGH")
    now = datetime.now(timezone.utc)

    return RiskResponse(
        items=items,
        count=len(items),
        critical_count=critical_cnt,
        high_count=high_cnt,
        calculated_at=now,
        data_mode="live_database",
    )

