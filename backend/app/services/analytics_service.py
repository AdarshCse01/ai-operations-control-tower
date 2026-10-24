"""
Operational Analytics and Statistical / Machine Learning Baseline Service.
Derives real historical metrics from stored database records and provides transparent,
unfabricated ML baseline evaluation with explicit data-sufficiency gates.

Includes Phase 6 Advanced Analytics aggregations:
- Order volume trends over time
- Order status distribution
- Inventory valuation and multi-facility stock distribution
- Low-stock and stockout vulnerability tracking
- Order fulfillment performance metrics
- Supplier reliability performance
- Executive dashboard unified intelligence
"""
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import uuid
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.stock_movement import StockMovement
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from app.schemas.analytics import (
    CategoryStockItem,
    DateRangeInfo,
    ExecutiveDashboardKPIs,
    ExecutiveDashboardResponse,
    FulfillmentMetricsResponse,
    InventoryValuationResponse,
    LowStockAlertItem,
    LowStockResponse,
    MLEvaluationMetrics,
    OperationalSummary,
    OrderStatusDistributionResponse,
    OrderStatusItem,
    OrderTrendPoint,
    OrderVolumeTrendResponse,
    SupplierPerformanceItem,
    SupplierPerformanceResponse,
    WarehouseStockItem,
)
from app.services.risk_engine import detect_operational_risks


def parse_date_range(
    range_preset: str | None = "30d",
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[datetime | None, datetime | None, DateRangeInfo]:
    """
    Parses and validates time range parameters.
    Supports presets: '7d', '30d', '90d', 'all', and custom ISO date strings.
    Guarantees timezone-aware UTC timestamps and validates start <= end.
    """
    now = datetime.now(timezone.utc)
    preset_lower = (range_preset or "").lower().strip()

    # Custom date parsing takes priority if start_date or end_date is provided
    if start_date or end_date:
        start_dt: datetime | None = None
        end_dt: datetime | None = None

        if start_date:
            try:
                # Handle YYYY-MM-DD or ISO 8601
                if len(start_date) == 10:
                    d = date.fromisoformat(start_date)
                    start_dt = datetime.combine(d, time.min, tzinfo=timezone.utc)
                else:
                    parsed = datetime.fromisoformat(start_date)
                    start_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid start_date format: '{start_date}'. Expected YYYY-MM-DD or ISO-8601.",
                )

        if end_date:
            try:
                if len(end_date) == 10:
                    d = date.fromisoformat(end_date)
                    # End of day in UTC
                    end_dt = datetime.combine(d, time.max, tzinfo=timezone.utc)
                else:
                    parsed = datetime.fromisoformat(end_date)
                    end_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid end_date format: '{end_date}'. Expected YYYY-MM-DD or ISO-8601.",
                )

        if start_dt and end_dt and start_dt > end_dt:
            raise HTTPException(
                status_code=422,
                detail="start_date must be earlier than or equal to end_date.",
            )

        label = f"{start_dt.strftime('%b %d, %Y') if start_dt else 'Epoch'} - {end_dt.strftime('%b %d, %Y') if end_dt else 'Present'}"
        return (
            start_dt,
            end_dt,
            DateRangeInfo(
                label=label,
                start_date=start_dt.isoformat() if start_dt else None,
                end_date=end_dt.isoformat() if end_dt else None,
                preset="custom",
            ),
        )

    # Preset intervals
    if preset_lower == "7d":
        start_dt = now - timedelta(days=7)
        end_dt = now
        label = "Last 7 Days"
    elif preset_lower == "30d" or not preset_lower:
        start_dt = now - timedelta(days=30)
        end_dt = now
        label = "Last 30 Days"
    elif preset_lower == "90d":
        start_dt = now - timedelta(days=90)
        end_dt = now
        label = "Last 90 Days"
    elif preset_lower == "all":
        start_dt = None
        end_dt = None
        label = "All Historical Data"
    else:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported range preset: '{range_preset}'. Expected '7d', '30d', '90d', or 'all'.",
        )

    return (
        start_dt,
        end_dt,
        DateRangeInfo(
            label=label,
            start_date=start_dt.isoformat() if start_dt else None,
            end_date=end_dt.isoformat() if end_dt else None,
            preset=preset_lower or "30d",
        ),
    )


async def get_order_volume_trend(
    session: AsyncSession,
    start_dt: datetime | None,
    end_dt: datetime | None,
    date_info: DateRangeInfo,
) -> OrderVolumeTrendResponse:
    """
    Computes server-side aggregated order volume grouped chronologically by date.
    Calculates total revenue using Decimal arithmetic and tracks on-time vs delayed dispatches.
    """
    filters = []
    if start_dt:
        filters.append(Order.created_at >= start_dt)
    if end_dt:
        filters.append(Order.created_at <= end_dt)

    # Group by date using dialect-compatible func.date
    date_col = func.date(Order.created_at)
    stmt = (
        select(
            date_col.label("order_date"),
            func.count(Order.id).label("total_orders"),
            func.coalesce(func.sum(Order.total_amount), Decimal("0.00")).label("total_revenue"),
        )
        .where(*filters)
        .group_by(date_col)
        .order_by(date_col.asc())
    )
    results = (await session.execute(stmt)).all()

    # Query detailed delivered/delayed counts per date
    deliv_stmt = (
        select(
            date_col.label("order_date"),
            Order.status,
            Order.expected_delivery_date,
            Order.updated_at,
        )
        .where(*filters, Order.status == "DELIVERED")
    )
    deliv_rows = (await session.execute(deliv_stmt)).all()

    delivered_counts: dict[str, int] = {}
    delayed_counts: dict[str, int] = {}
    for row in deliv_rows:
        d_str = str(row[0])
        delivered_counts[d_str] = delivered_counts.get(d_str, 0) + 1
        exp_dt = row[2]
        upd_dt = row[3]
        if exp_dt and upd_dt and upd_dt > exp_dt:
            delayed_counts[d_str] = delayed_counts.get(d_str, 0) + 1

    trend_points: list[OrderTrendPoint] = []
    overall_total_orders = 0
    overall_total_revenue = Decimal("0.00")

    for r in results:
        day_str = str(r[0])
        cnt = int(r[1])
        rev = Decimal(str(r[2]))
        overall_total_orders += cnt
        overall_total_revenue += rev

        trend_points.append(
            OrderTrendPoint(
                date=day_str,
                orders_count=cnt,
                delivered_count=delivered_counts.get(day_str, 0),
                delayed_count=delayed_counts.get(day_str, 0),
                total_revenue=f"{rev:.2f}",
            )
        )

    avg_order_value = (
        Decimal(overall_total_revenue / overall_total_orders)
        if overall_total_orders > 0
        else Decimal("0.00")
    )

    return OrderVolumeTrendResponse(
        data_mode="live_database",
        date_range=date_info,
        total_orders=overall_total_orders,
        total_revenue=f"{overall_total_revenue:.2f}",
        average_order_value=f"{avg_order_value:.2f}",
        trend=trend_points,
        is_empty=len(trend_points) == 0,
    )


async def get_order_status_distribution(
    session: AsyncSession,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> OrderStatusDistributionResponse:
    """
    Computes distribution counts, percentages, and total monetary amounts across order statuses.
    Includes zero-filled representations for unobserved lifecycle states.
    """
    filters = []
    if start_dt:
        filters.append(Order.created_at >= start_dt)
    if end_dt:
        filters.append(Order.created_at <= end_dt)

    stmt = (
        select(
            Order.status,
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), Decimal("0.00")),
        )
        .where(*filters)
        .group_by(Order.status)
    )
    rows = (await session.execute(stmt)).all()

    status_data = {r[0]: (int(r[1]), Decimal(str(r[2]))) for r in rows}
    total_orders = sum(item[0] for item in status_data.values())

    standard_statuses = ["PENDING", "PROCESSING", "SHIPPED", "DELIVERED", "CANCELLED"]
    items: list[OrderStatusItem] = []

    for st in standard_statuses:
        count, amount = status_data.get(st, (0, Decimal("0.00")))
        pct = round((count / total_orders) * 100.0, 1) if total_orders > 0 else 0.0
        items.append(
            OrderStatusItem(
                status=st,
                count=count,
                percentage=pct,
                total_amount=f"{amount:.2f}",
            )
        )

    return OrderStatusDistributionResponse(
        data_mode="live_database",
        total_orders=total_orders,
        distribution=items,
        is_empty=total_orders == 0,
    )


async def get_inventory_valuation_and_distribution(
    session: AsyncSession,
) -> InventoryValuationResponse:
    """
    Computes total inventory units, cost-weighted valuation, and multi-facility breakdown.
    Safe Decimal calculations for asset totals.
    """
    # 1. Total units aggregation
    units_stmt = select(
        func.coalesce(func.sum(Inventory.quantity_on_hand), 0),
        func.coalesce(func.sum(Inventory.quantity_reserved), 0),
    )
    sums = (await session.execute(units_stmt)).first()
    total_on_hand = int(sums[0] if sums else 0)
    total_reserved = int(sums[1] if sums else 0)
    total_available = max(0, total_on_hand - total_reserved)

    # 2. Total cost and retail valuation
    val_stmt = (
        select(
            func.coalesce(func.sum(Inventory.quantity_on_hand * Product.unit_cost), Decimal("0.00")),
            func.coalesce(func.sum(Inventory.quantity_on_hand * Product.unit_price), Decimal("0.00")),
        )
        .join(Product, Inventory.product_id == Product.id)
    )
    val_res = (await session.execute(val_stmt)).first()
    total_cost_val = Decimal(str(val_res[0])) if val_res else Decimal("0.00")
    total_retail_val = Decimal(str(val_res[1])) if val_res else Decimal("0.00")

    # 3. Warehouse breakdown
    wh_stmt = (
        select(
            Warehouse.id,
            Warehouse.code,
            Warehouse.name,
            func.coalesce(func.sum(Inventory.quantity_on_hand), 0),
            func.coalesce(func.sum(Inventory.quantity_reserved), 0),
            func.coalesce(func.sum(Inventory.quantity_on_hand * Product.unit_cost), Decimal("0.00")),
            func.count(func.distinct(Inventory.product_id)),
        )
        .join(Inventory, Warehouse.id == Inventory.warehouse_id)
        .join(Product, Inventory.product_id == Product.id)
        .group_by(Warehouse.id, Warehouse.code, Warehouse.name)
        .order_by(Warehouse.code.asc())
    )
    wh_rows = (await session.execute(wh_stmt)).all()
    warehouse_items: list[WarehouseStockItem] = []
    for r in wh_rows:
        wh_on_hand = int(r[3])
        wh_reserved = int(r[4])
        wh_val = Decimal(str(r[5]))
        warehouse_items.append(
            WarehouseStockItem(
                warehouse_id=str(r[0]),
                warehouse_code=r[1],
                warehouse_name=r[2],
                total_units=wh_on_hand,
                available_units=max(0, wh_on_hand - wh_reserved),
                reserved_units=wh_reserved,
                valuation=f"{wh_val:.2f}",
                sku_count=int(r[6]),
            )
        )

    # 4. Product category breakdown
    cat_stmt = (
        select(
            Product.category,
            func.coalesce(func.sum(Inventory.quantity_on_hand), 0),
            func.coalesce(func.sum(Inventory.quantity_on_hand * Product.unit_cost), Decimal("0.00")),
            func.count(func.distinct(Product.id)),
        )
        .join(Inventory, Product.id == Inventory.product_id)
        .group_by(Product.category)
        .order_by(func.sum(Inventory.quantity_on_hand * Product.unit_cost).desc())
    )
    cat_rows = (await session.execute(cat_stmt)).all()
    category_items: list[CategoryStockItem] = []
    for r in cat_rows:
        cat_units = int(r[1])
        cat_val = Decimal(str(r[2]))
        category_items.append(
            CategoryStockItem(
                category=r[0] or "Uncategorized",
                total_units=cat_units,
                valuation=f"{cat_val:.2f}",
                sku_count=int(r[3]),
            )
        )

    return InventoryValuationResponse(
        data_mode="live_database",
        total_inventory_units=total_on_hand,
        available_inventory_units=total_available,
        reserved_inventory_units=total_reserved,
        total_valuation=f"{total_cost_val:.2f}",
        retail_valuation=f"{total_retail_val:.2f}",
        warehouses=warehouse_items,
        categories=category_items,
        is_empty=total_on_hand == 0 and len(warehouse_items) == 0,
    )


async def get_low_stock_and_stockouts(
    session: AsyncSession,
    limit: int = 50,
) -> LowStockResponse:
    """
    Identifies active inventory balances that are in stockout or below reorder threshold.
    """
    stmt = (
        select(Inventory)
        .join(Product, Inventory.product_id == Product.id)
        .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        .options(selectinload(Inventory.product), selectinload(Inventory.warehouse))
        .where(
            (Inventory.quantity_on_hand - Inventory.quantity_reserved) <= Inventory.reorder_quantity
        )
        .order_by((Inventory.quantity_on_hand - Inventory.quantity_reserved).asc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).scalars().all()

    stockout_count = 0
    low_stock_count = 0
    alert_items: list[LowStockAlertItem] = []

    for item in rows:
        avail = item.available_quantity
        prod = item.product
        wh = item.warehouse
        is_stockout = avail <= 0

        if is_stockout:
            stockout_count += 1
            status_code = "STOCKOUT"
        else:
            low_stock_count += 1
            status_code = "LOW_STOCK"

        alert_items.append(
            LowStockAlertItem(
                inventory_id=str(item.id),
                product_id=str(item.product_id),
                product_sku=prod.sku if prod else "UNKNOWN",
                product_name=prod.name if prod else "Unknown Product",
                product_category=prod.category if prod else "General",
                warehouse_code=wh.code if wh else "WH-UNK",
                warehouse_name=wh.name if wh else "Unknown Facility",
                quantity_on_hand=item.quantity_on_hand,
                quantity_reserved=item.quantity_reserved,
                available_quantity=avail,
                reorder_quantity=item.reorder_quantity,
                safety_stock=prod.safety_stock if prod else 5,
                unit_cost=f"{prod.unit_cost:.2f}" if prod and prod.unit_cost else "0.00",
                status=status_code,
            )
        )

    return LowStockResponse(
        data_mode="live_database",
        stockout_count=stockout_count,
        low_stock_count=low_stock_count,
        items=alert_items,
        is_empty=len(alert_items) == 0,
    )


async def get_fulfillment_performance(
    session: AsyncSession,
    start_dt: datetime | None = None,
    end_dt: datetime | None = None,
) -> FulfillmentMetricsResponse:
    """
    Evaluates order fulfillment cycle times and on-time performance against genuine delivery targets.
    Reports honest data sufficiency if no orders have confirmed completion timestamps.
    """
    filters = [Order.status == "DELIVERED"]
    if start_dt:
        filters.append(Order.created_at >= start_dt)
    if end_dt:
        filters.append(Order.created_at <= end_dt)

    stmt = select(Order).where(*filters)
    delivered_orders = (await session.execute(stmt)).scalars().all()
    total_delivered = len(delivered_orders)

    if total_delivered == 0:
        return FulfillmentMetricsResponse(
            data_mode="live_database",
            has_sufficient_data=False,
            total_delivered_orders=0,
            delivered_with_targets=0,
            on_time_count=0,
            delayed_count=0,
            on_time_rate=None,
            average_fulfillment_days=None,
            status_message="No completed/delivered customer orders recorded in the selected period.",
        )

    # Filter orders with recorded expected delivery dates
    with_targets = [o for o in delivered_orders if o.expected_delivery_date is not None]
    if len(with_targets) == 0:
        return FulfillmentMetricsResponse(
            data_mode="live_database",
            has_sufficient_data=False,
            total_delivered_orders=total_delivered,
            delivered_with_targets=0,
            on_time_count=0,
            delayed_count=0,
            on_time_rate=None,
            average_fulfillment_days=None,
            status_message="Delivered orders exist, but none have recorded expected_delivery_date values to measure SLA performance.",
        )

    on_time_count = 0
    cycle_days_list: list[float] = []

    for ord in with_targets:
        exp = ord.expected_delivery_date
        delivered_at = ord.updated_at
        if delivered_at <= exp:
            on_time_count += 1

        cycle_sec = (delivered_at - ord.created_at).total_seconds()
        cycle_days = max(0.0, cycle_sec / 86400.0)
        cycle_days_list.append(cycle_days)

    delayed_count = len(with_targets) - on_time_count
    on_time_rate = round((on_time_count / len(with_targets)) * 100.0, 1)
    avg_cycle = round(sum(cycle_days_list) / len(cycle_days_list), 1) if cycle_days_list else None

    return FulfillmentMetricsResponse(
        data_mode="live_database",
        has_sufficient_data=True,
        total_delivered_orders=total_delivered,
        delivered_with_targets=len(with_targets),
        on_time_count=on_time_count,
        delayed_count=delayed_count,
        on_time_rate=on_time_rate,
        average_fulfillment_days=avg_cycle,
        status_message=f"Performance evaluated across {len(with_targets)} delivered orders with target dates.",
    )


async def get_supplier_performance(
    session: AsyncSession,
) -> SupplierPerformanceResponse:
    """
    Evaluates vendor reliability scores and catalog allocations from active database records.
    Reports honest sufficiency state if no active suppliers exist.
    """
    stmt = (
        select(
            Supplier.id,
            Supplier.code,
            Supplier.name,
            Supplier.lead_time_days,
            Supplier.reliability_score,
            Supplier.is_active,
            func.count(Product.id),
        )
        .outerjoin(Product, Supplier.id == Product.supplier_id)
        .where(Supplier.is_active == True)
        .group_by(
            Supplier.id,
            Supplier.code,
            Supplier.name,
            Supplier.lead_time_days,
            Supplier.reliability_score,
            Supplier.is_active,
        )
        .order_by(Supplier.reliability_score.desc())
    )
    rows = (await session.execute(stmt)).all()

    if not rows:
        return SupplierPerformanceResponse(
            data_mode="live_database",
            has_sufficient_data=False,
            total_suppliers=0,
            average_reliability_score=None,
            average_lead_time_days=None,
            suppliers=[],
            transparency_note="No active suppliers registered in the database catalog.",
        )

    supplier_items: list[SupplierPerformanceItem] = []
    total_reliability = Decimal("0.00")
    total_lead_time = 0

    for r in rows:
        score = float(r[4])
        lead = int(r[3])
        total_reliability += Decimal(str(r[4]))
        total_lead_time += lead

        supplier_items.append(
            SupplierPerformanceItem(
                supplier_id=str(r[0]),
                code=r[1],
                name=r[2],
                lead_time_days=lead,
                reliability_score=score,
                active_products_count=int(r[6]),
                is_active=bool(r[5]),
            )
        )

    avg_score = round(float(total_reliability / len(rows)), 2)
    avg_lead = round(total_lead_time / len(rows), 1)

    return SupplierPerformanceResponse(
        data_mode="live_database",
        has_sufficient_data=True,
        total_suppliers=len(rows),
        average_reliability_score=avg_score,
        average_lead_time_days=avg_lead,
        suppliers=supplier_items,
        transparency_note="Vendor performance reflects registered contractual reliability scores and active SKU allocations.",
    )


async def get_executive_dashboard(
    session: AsyncSession,
    start_dt: datetime | None,
    end_dt: datetime | None,
    date_info: DateRangeInfo,
) -> ExecutiveDashboardResponse:
    """
    Consolidates the complete executive intelligence portfolio into a single, cohesive dashboard payload.
    Provides unified KPIs, breakdown distributions, inventory health, fulfillment, and risk previews.
    """
    # 1. Order volume and status distribution
    order_trend = await get_order_volume_trend(session, start_dt, end_dt, date_info)
    order_dist = await get_order_status_distribution(session, start_dt, end_dt)

    # 2. Inventory and valuations
    inv_val = await get_inventory_valuation_and_distribution(session)
    low_stock = await get_low_stock_and_stockouts(session, limit=10)

    # 3. Fulfillment and suppliers
    fulfillment = await get_fulfillment_performance(session, start_dt, end_dt)
    supplier_perf = await get_supplier_performance(session)

    # 4. Critical risks detection
    detected_risks = await detect_operational_risks(session)
    critical_risks_count = sum(1 for r in detected_risks if r.severity == "CRITICAL")
    critical_previews = [
        r.model_dump() for r in detected_risks if r.severity in ("CRITICAL", "HIGH")
    ][:5]

    # 5. Pending recommendations count and preview
    rec_count_stmt = select(func.count(Recommendation.id)).where(Recommendation.status == "PENDING")
    pending_recs_count = int((await session.execute(rec_count_stmt)).scalar_one() or 0)

    rec_prev_stmt = (
        select(Recommendation)
        .where(Recommendation.status == "PENDING")
        .order_by(Recommendation.created_at.desc())
        .limit(3)
    )
    rec_rows = (await session.execute(rec_prev_stmt)).scalars().all()
    rec_previews = [
        {
            "id": str(r.id),
            "title": r.title,
            "priority": r.priority,
            "entity_name": r.entity_name,
            "proposed_action": r.proposed_action,
        }
        for r in rec_rows
    ]

    # Compute status counts from order_dist
    status_map = {item.status: item.count for item in order_dist.distribution}
    pending_orders = status_map.get("PENDING", 0)
    processing_orders = status_map.get("PROCESSING", 0)
    shipped_orders = status_map.get("SHIPPED", 0)
    delivered_orders = status_map.get("DELIVERED", 0)
    cancelled_orders = status_map.get("CANCELLED", 0)
    active_orders = pending_orders + processing_orders + shipped_orders

    kpis = ExecutiveDashboardKPIs(
        total_orders=order_dist.total_orders,
        active_orders=active_orders,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        total_order_valuation=order_trend.total_revenue,
        total_inventory_units=inv_val.total_inventory_units,
        available_inventory_units=inv_val.available_inventory_units,
        reserved_inventory_units=inv_val.reserved_inventory_units,
        total_inventory_valuation=inv_val.total_valuation,
        low_stock_items_count=low_stock.low_stock_count,
        stockout_items_count=low_stock.stockout_count,
        pending_recommendations_count=pending_recs_count,
        critical_risks_count=critical_risks_count,
        on_time_fulfillment_rate=fulfillment.on_time_rate,
        average_supplier_reliability=supplier_perf.average_reliability_score,
    )

    return ExecutiveDashboardResponse(
        generated_at=datetime.now(timezone.utc).isoformat(),
        data_mode="live_database",
        date_range=date_info,
        kpis=kpis,
        order_status_distribution=order_dist.distribution,
        order_volume_trend=order_trend.trend,
        warehouse_stock=inv_val.warehouses,
        category_stock=inv_val.categories,
        low_stock_alerts=low_stock.items,
        fulfillment_summary=fulfillment,
        supplier_summary=supplier_perf,
        critical_risks_preview=critical_previews,
        pending_recommendations_preview=rec_previews,
    )


# -------------------------------------------------------------------------
# Preserved Phase 5 Functions: Operational Summary and ML Evaluation
# -------------------------------------------------------------------------

async def get_operational_summary(session: AsyncSession) -> OperationalSummary:
    """
    Derives genuine operational KPIs and statistics from active database tables.
    Preserved for Phase 5 backward compatibility.
    """
    # 1. Product catalog counts
    total_prods_res = await session.execute(select(func.count(Product.id)))
    total_products = total_prods_res.scalar_one() or 0

    active_prods_res = await session.execute(
        select(func.count(Product.id)).where(Product.is_active == True)
    )
    active_products = active_prods_res.scalar_one() or 0

    # 2. Inventory units and valuation
    inv_stmt = (
        select(
            func.sum(Inventory.quantity_on_hand),
            func.sum(Inventory.quantity_reserved),
        )
    )
    inv_sums = (await session.execute(inv_stmt)).first()
    total_on_hand = int(inv_sums[0] or 0) if inv_sums else 0
    total_reserved = int(inv_sums[1] or 0) if inv_sums else 0
    total_available = max(0, total_on_hand - total_reserved)

    # Calculate valuation and low-stock count from inventory rows
    inv_rows_res = await session.execute(
        select(Inventory).options(selectinload(Inventory.product))
    )
    inv_rows = inv_rows_res.scalars().all()
    valuation = Decimal("0.00")
    low_stock_count = 0
    stockout_count = 0

    for item in inv_rows:
        avail = item.available_quantity
        if avail <= 0:
            stockout_count += 1
            low_stock_count += 1
        elif avail <= item.reorder_quantity:
            low_stock_count += 1

        if item.product and item.product.unit_cost:
            cost = Decimal(str(item.product.unit_cost))
            valuation += cost * item.quantity_on_hand

    # 3. Order status breakdowns
    order_stmt = select(Order.status, func.count(Order.id)).group_by(Order.status)
    order_counts = dict((await session.execute(order_stmt)).all())

    total_orders = sum(order_counts.values())
    pending_orders = order_counts.get("PENDING", 0)
    processing_orders = order_counts.get("PROCESSING", 0)
    shipped_orders = order_counts.get("SHIPPED", 0)
    delivered_orders = order_counts.get("DELIVERED", 0)
    cancelled_orders = order_counts.get("CANCELLED", 0)

    # On-time delivery rate
    delivered_stmt = select(Order).where(Order.status == "DELIVERED")
    delivered_orders_list = (await session.execute(delivered_stmt)).scalars().all()
    on_time_count = 0
    with_dates_count = 0
    for ord in delivered_orders_list:
        if ord.expected_delivery_date:
            with_dates_count += 1
            if ord.updated_at <= ord.expected_delivery_date:
                on_time_count += 1

    fulfillment_rate = (
        round((on_time_count / with_dates_count) * 100.0, 1) if with_dates_count > 0 else None
    )

    # 4. Stock movement volume
    mov_res = await session.execute(select(func.sum(StockMovement.quantity)))
    total_movement_volume = int(mov_res.scalar_one() or 0)

    return OperationalSummary(
        total_products=total_products,
        active_products=active_products,
        total_inventory_units=total_on_hand,
        reserved_inventory_units=total_reserved,
        available_inventory_units=total_available,
        low_stock_items_count=low_stock_count,
        stockout_items_count=stockout_count,
        total_inventory_valuation=f"{valuation:.2f}",
        total_orders=total_orders,
        pending_orders=pending_orders,
        processing_orders=processing_orders,
        shipped_orders=shipped_orders,
        delivered_orders=delivered_orders,
        cancelled_orders=cancelled_orders,
        on_time_fulfillment_rate=fulfillment_rate,
        total_movement_volume=total_movement_volume,
    )


async def evaluate_delay_prediction_model(session: AsyncSession) -> MLEvaluationMetrics:
    """
    Evaluates order delay prediction against genuine stored orders.
    Enforces chronologically split training/testing to prevent future data leakage.
    If database records are insufficient for statistical validity, returns transparent data requirements.
    """
    stmt = (
        select(Order)
        .where(Order.expected_delivery_date.isnot(None))
        .order_by(Order.created_at.asc())
    )
    orders = (await session.execute(stmt)).scalars().all()
    sample_count = len(orders)
    now = datetime.now(timezone.utc)

    # Minimum sample threshold for statistically meaningful evaluation
    MIN_SAMPLES = 20
    if sample_count < MIN_SAMPLES:
        return MLEvaluationMetrics(
            model_name="Operational Delay Risk Estimator (Supervised Baseline)",
            task_type="Binary Classification (Order Delivery Delay)",
            status="insufficient_data",
            samples_count=sample_count,
            accuracy=None,
            precision=None,
            recall=None,
            f1_score=None,
            mae=None,
            baseline_comparison=None,
            data_requirements=[
                f"Minimum {MIN_SAMPLES} orders with expected_delivery_date (currently available: {sample_count})",
                "Timestamped carrier handovers and confirmed delivery signatures",
                "Ground-truth fulfillment outcome labels without lookahead bias",
                "Minimum 30 calendar days of operational movement history",
            ],
            evaluation_notes=(
                f"Current database has {sample_count} qualifying orders with delivery targets. "
                f"Per strict portfolio standards, no synthetic training labels were fabricated. "
                f"Active system uses explainable deterministic rules until sample size reaches {MIN_SAMPLES}."
            ),
        )

    # Prepare features and labels
    records: list[tuple[float, int]] = []
    priority_weights = {"LOW": 0.1, "NORMAL": 0.3, "HIGH": 0.7, "CRITICAL": 0.9}

    for ord in orders:
        exp_date = ord.expected_delivery_date
        if exp_date.tzinfo is None:
            exp_date = exp_date.replace(tzinfo=timezone.utc)

        if ord.status == "DELIVERED":
            delivered_date = ord.updated_at
            if delivered_date.tzinfo is None:
                delivered_date = delivered_date.replace(tzinfo=timezone.utc)
            is_delayed = 1 if delivered_date > exp_date else 0
        else:
            is_delayed = 1 if now > exp_date else 0

        p_weight = priority_weights.get(ord.priority, 0.3)
        records.append((p_weight, is_delayed))

    # Chronological 70/30 split (strict temporal order, no shuffle to prevent data leakage)
    split_idx = int(len(records) * 0.7)
    train_records = records[:split_idx]
    test_records = records[split_idx:]

    if not test_records:
        test_records = records

    best_thresh = 0.5
    best_train_acc = -1.0
    for cand in [0.2, 0.4, 0.6, 0.8]:
        train_preds = [1 if r[0] >= cand else 0 for r in train_records]
        acc = sum(p == r[1] for p, r in zip(train_preds, train_records)) / len(train_records)
        if acc > best_train_acc:
            best_train_acc = acc
            best_thresh = cand

    y_true = [r[1] for r in test_records]
    y_pred = [1 if r[0] >= best_thresh else 0 for r in test_records]

    n_test = len(y_true)
    accuracy = sum(p == t for p, t in zip(y_pred, y_true)) / n_test

    tp = sum(p == 1 and t == 1 for p, t in zip(y_pred, y_true))
    fp = sum(p == 1 and t == 0 for p, t in zip(y_pred, y_true))
    fn = sum(p == 0 and t == 1 for p, t in zip(y_pred, y_true))

    precision = round(tp / (tp + fp), 3) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 3) if (tp + fn) > 0 else 0.0
    f1 = round(2 * (precision * recall) / (precision + recall), 3) if (precision + recall) > 0 else 0.0
    mae = round(sum(abs(p - t) for p, t in zip(y_pred, y_true)) / n_test, 3)

    majority_class = 1 if sum(r[1] for r in train_records) > len(train_records) / 2 else 0
    majority_acc = sum(t == majority_class for t in y_true) / n_test

    return MLEvaluationMetrics(
        model_name="Operational Delay Risk Estimator (Priority-Calibrated)",
        task_type="Binary Classification (Order Delivery Delay)",
        status="evaluated",
        samples_count=sample_count,
        accuracy=round(accuracy, 3),
        precision=precision,
        recall=recall,
        f1_score=f1,
        mae=mae,
        baseline_comparison={
            "majority_class_accuracy": round(majority_acc, 3),
            "model_improvement_delta": round(accuracy - majority_acc, 3),
            "decision_threshold": best_thresh,
        },
        data_requirements=None,
        evaluation_notes=(
            f"Evaluated on {n_test} hold-out test orders using temporal split. "
            f"Model achieved Accuracy: {accuracy:.1%}, F1: {f1}, MAE: {mae}."
        ),
    )
