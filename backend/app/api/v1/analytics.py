"""
Operational Analytics and Executive Intelligence API router.
Provides server-side aggregations for:
- Executive dashboard KPIs & consolidated portfolio intelligence
- Order volume trends with date-range filters
- Order status distribution and percentages
- Inventory valuations, warehouse distributions, and category breakdowns
- Low-stock and stockout vulnerability alerts
- Order fulfillment performance metrics
- Supplier reliability ratings
- Transparent ML baseline evaluation with temporal splitting
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.user import User
from app.schemas.analytics import (
    ExecutiveDashboardResponse,
    FulfillmentMetricsResponse,
    InventoryValuationResponse,
    LowStockResponse,
    MLEvaluationMetrics,
    OperationalSummary,
    OrderStatusDistributionResponse,
    OrderVolumeTrendResponse,
    SupplierPerformanceResponse,
)
from app.services.analytics_service import (
    evaluate_delay_prediction_model,
    get_executive_dashboard,
    get_fulfillment_performance,
    get_inventory_valuation_and_distribution,
    get_low_stock_and_stockouts,
    get_operational_summary,
    get_order_status_distribution,
    get_order_volume_trend,
    get_supplier_performance,
    parse_date_range,
)

router = APIRouter()


@router.get("/executive", response_model=ExecutiveDashboardResponse)
async def get_executive_dashboard_endpoint(
    range: str | None = Query("30d", description="Time range preset: '7d', '30d', '90d', 'all'"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD or ISO-8601)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD or ISO-8601)"),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Consolidated Executive Dashboard endpoint.
    Aggregates orders, inventory valuations, stock alerts, fulfillment rates,
    supplier performance, pending recommendations, and critical operational risks.
    """
    start_dt, end_dt, date_info = parse_date_range(range, start_date, end_date)
    return await get_executive_dashboard(session, start_dt, end_dt, date_info)


@router.get("/summary", response_model=OperationalSummary)
async def get_operational_kpi_summary(
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Computes genuine operational statistics derived from products, inventory,
    warehouses, and order fulfillment status. (Phase 5 endpoint)
    """
    return await get_operational_summary(session)


@router.get("/orders/trend", response_model=OrderVolumeTrendResponse)
async def get_order_volume_trend_endpoint(
    range: str | None = Query("30d", description="Time range preset: '7d', '30d', '90d', 'all'"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD or ISO-8601)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD or ISO-8601)"),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Computes daily order volume time series, completed and delayed dispatch counts,
    and total monetary revenue over the specified date range.
    """
    start_dt, end_dt, date_info = parse_date_range(range, start_date, end_date)
    return await get_order_volume_trend(session, start_dt, end_dt, date_info)


@router.get("/orders/status-distribution", response_model=OrderStatusDistributionResponse)
async def get_order_status_distribution_endpoint(
    range: str | None = Query("30d", description="Time range preset: '7d', '30d', '90d', 'all'"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD or ISO-8601)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD or ISO-8601)"),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Computes order status distribution breakdown with exact counts, percentages, and valuations.
    """
    start_dt, end_dt, _ = parse_date_range(range, start_date, end_date)
    return await get_order_status_distribution(session, start_dt, end_dt)


@router.get("/inventory/valuation", response_model=InventoryValuationResponse)
async def get_inventory_valuation_endpoint(
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Computes total cost-weighted inventory valuation, units breakdown,
    and distribution across warehouses and product categories.
    """
    return await get_inventory_valuation_and_distribution(session)


@router.get("/inventory/low-stock", response_model=LowStockResponse)
async def get_low_stock_endpoint(
    limit: int = Query(50, ge=1, le=200, description="Maximum number of items to return"),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Lists inventory items currently in stockout or below reorder threshold.
    """
    return await get_low_stock_and_stockouts(session, limit=limit)


@router.get("/fulfillment", response_model=FulfillmentMetricsResponse)
async def get_fulfillment_performance_endpoint(
    range: str | None = Query("all", description="Time range preset: '7d', '30d', '90d', 'all'"),
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD or ISO-8601)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD or ISO-8601)"),
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Reports on-time delivery rate and average fulfillment cycle days based on genuine timestamps.
    Returns honest insufficient data status if completed orders lack delivery targets.
    """
    start_dt, end_dt, _ = parse_date_range(range, start_date, end_date)
    return await get_fulfillment_performance(session, start_dt, end_dt)


@router.get("/suppliers", response_model=SupplierPerformanceResponse)
async def get_supplier_performance_endpoint(
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
):
    """
    Provides supplier reliability metrics and SKU allocation counts derived from master catalog records.
    """
    return await get_supplier_performance(session)


@router.get("/ml-evaluation", response_model=MLEvaluationMetrics)
async def get_ml_model_evaluation(
    session: AsyncSession = Depends(get_db),
    _user: User = Depends(require_permission(Permission.ANALYTICS_READ)),
):
    """
    Provides transparent evaluation metrics for operational delay risk prediction.
    Enforces chronological time splits (preventing lookahead bias).
    Reports explicit data requirements if historical database records are below statistical threshold.
    """
    return await evaluate_delay_prediction_model(session)
