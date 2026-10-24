"""
Dashboard summary router protected by RBAC DASHBOARD_READ permission.
Supports:
- GET /summary: Illustrative benchmark or live snapshot
- GET /executive: Full live executive dashboard intelligence
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.analytics import ExecutiveDashboardResponse
from app.services.analytics_service import get_executive_dashboard, parse_date_range
from app.services.demo_data import dashboard_snapshot

router = APIRouter()


@router.get("/summary")
async def summary(
    source: str = Query("demo", description="Data source: 'demo' for illustrative benchmark, 'live' for real database"),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Returns dashboard summary.
    Defaults to illustrative demo snapshot for backward compatibility and test consistency,
    or returns live operational metrics when source='live' is requested.
    """
    if source == "live":
        start_dt, end_dt, date_info = parse_date_range("30d", None, None)
        return await get_executive_dashboard(session, start_dt, end_dt, date_info)
    return dashboard_snapshot()


@router.get("/executive", response_model=ExecutiveDashboardResponse)
async def executive(
    range: str | None = Query("30d", description="Time range preset: '7d', '30d', '90d', 'all'"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD or ISO-8601)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD or ISO-8601)"),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Returns consolidated live executive dashboard intelligence from active database records.
    """
    start_dt, end_dt, date_info = parse_date_range(range, start_date, end_date)
    return await get_executive_dashboard(session, start_dt, end_dt, date_info)
