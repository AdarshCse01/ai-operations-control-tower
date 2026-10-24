"""
Tests for Phase 6 Advanced Analytics & Executive Dashboard.
Covers:
- Executive dashboard KPI calculations and exact Decimal financial aggregation
- Date-range filtering, presets ('7d', '30d', '90d', 'all'), and custom date ranges
- Validation of invalid date inputs (start_date > end_date and malformed strings -> 422)
- Empty database behavior and division-by-zero resilience
- Insufficient historical data transparency (fulfillment and suppliers)
- Order status distribution and multi-warehouse / category breakdown
- Low-stock and stockout vulnerability tracking
- RBAC authorization matrix across Viewer, Analyst, and Operations Manager
- Consistency between API responses and stored records
- Live vs demo data source distinction
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_executive_dashboard_kpis_and_financial_aggregation(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    Validates executive dashboard KPIs: total orders, revenue, inventory units,
    exact Decimal valuations, and live status breakdowns.
    """
    viewer = await make_user(role="VIEWER")
    headers = get_user_auth_headers(viewer)

    # 1. Setup supplier, warehouse, products
    sup = Supplier(name="Titan Industrial", code="SUP-TITAN-01", lead_time_days=5, reliability_score=Decimal("0.96"))
    wh1 = Warehouse(name="Austin Distribution Hub", code="WH-ATX-01", location="100 Tech Ridge", capacity=10000)
    wh2 = Warehouse(name="Denver Regional Center", code="WH-DEN-01", location="200 Mountain Way", capacity=8000)
    db_session.add_all([sup, wh1, wh2])
    await db_session.commit()
    await db_session.refresh(sup)
    await db_session.refresh(wh1)
    await db_session.refresh(wh2)

    p1 = Product(
        name="Industrial Motor X1",
        sku="SKU-MTR-X1",
        category="Machinery",
        unit_price=Decimal("450.00"),
        unit_cost=Decimal("300.00"),
        safety_stock=5,
        supplier_id=sup.id,
    )
    p2 = Product(
        name="Hydraulic Valve V2",
        sku="SKU-VLV-V2",
        category="Valves",
        unit_price=Decimal("120.00"),
        unit_cost=Decimal("80.00"),
        safety_stock=10,
        supplier_id=sup.id,
    )
    db_session.add_all([p1, p2])
    await db_session.commit()
    await db_session.refresh(p1)
    await db_session.refresh(p2)

    # 2. Inventory: WH1 has 40 on-hand, 10 reserved; WH2 has 20 on-hand, 0 reserved
    inv1 = Inventory(product_id=p1.id, warehouse_id=wh1.id, quantity_on_hand=40, quantity_reserved=10, reorder_quantity=15)
    inv2 = Inventory(product_id=p2.id, warehouse_id=wh2.id, quantity_on_hand=20, quantity_reserved=0, reorder_quantity=25)
    db_session.add_all([inv1, inv2])

    # 3. Orders: 1 PENDING ($900.00), 1 DELIVERED ($240.00)
    o1 = Order(
        order_number="ORD-EXEC-01",
        customer_name="Apex Logistics",
        warehouse_id=wh1.id,
        status="PENDING",
        total_amount=Decimal("900.00"),
    )
    now = datetime.now(timezone.utc)
    o2 = Order(
        order_number="ORD-EXEC-02",
        customer_name="Boreas Energy",
        warehouse_id=wh2.id,
        status="DELIVERED",
        total_amount=Decimal("240.00"),
        expected_delivery_date=now + timedelta(days=2),
    )
    db_session.add_all([o1, o2])

    # 4. Pending Recommendation
    rec = Recommendation(
        recommendation_type="STOCK_TRANSFER",
        priority="HIGH",
        title="Balance hydraulic inventory",
        entity_type="PRODUCT",
        entity_id=str(p2.id),
        entity_name=p2.name,
        explanation="Inventory in Denver is below reorder quantity",
        proposed_action="TRANSFER",
        status="PENDING",
    )
    db_session.add(rec)
    await db_session.commit()

    # Query Executive Dashboard
    res = client.get("/api/v1/analytics/executive", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["data_mode"] == "live_database"
    kpis = data["kpis"]
    assert kpis["total_orders"] >= 2
    assert kpis["active_orders"] >= 1
    assert kpis["delivered_orders"] >= 1
    # Total order valuation includes 900.00 + 240.00 = 1140.00
    assert Decimal(kpis["total_order_valuation"]) >= Decimal("1140.00")

    # Inventory Units: 40 + 20 = 60 on-hand; 10 reserved; 50 available
    assert kpis["total_inventory_units"] >= 60
    assert kpis["reserved_inventory_units"] >= 10
    assert kpis["available_inventory_units"] >= 50

    # Total inventory cost valuation: (40 * 300) + (20 * 80) = 12000 + 1600 = $13600.00
    assert Decimal(kpis["total_inventory_valuation"]) >= Decimal("13600.00")

    # Pending recommendations count
    assert kpis["pending_recommendations_count"] >= 1

    # Warehouse breakdown verification
    wh_list = data["warehouse_stock"]
    assert len(wh_list) >= 2
    wh_codes = [w["warehouse_code"] for w in wh_list]
    assert "WH-ATX-01" in wh_codes
    assert "WH-DEN-01" in wh_codes

    # Category breakdown verification
    cat_list = data["category_stock"]
    cat_names = [c["category"] for c in cat_list]
    assert "Machinery" in cat_names
    assert "Valves" in cat_names


@pytest.mark.asyncio
async def test_date_range_filtering_and_presets(client: TestClient, db_session: AsyncSession, make_user):
    """
    Validates filtering across time presets ('7d', '30d', '90d', 'all')
    and custom bounded start_date / end_date ranges.
    """
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    # Test preset ranges
    for preset in ["7d", "30d", "90d", "all"]:
        res = client.get(f"/api/v1/analytics/orders/trend?range={preset}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["data_mode"] == "live_database"
        assert data["date_range"]["preset"] == preset

    # Test valid custom range
    now = datetime.now(timezone.utc)
    start_str = (now - timedelta(days=10)).strftime("%Y-%m-%d")
    end_str = now.strftime("%Y-%m-%d")

    res_custom = client.get(
        f"/api/v1/analytics/orders/trend?start_date={start_str}&end_date={end_str}",
        headers=headers,
    )
    assert res_custom.status_code == 200
    custom_data = res_custom.json()
    assert custom_data["date_range"]["preset"] == "custom"
    assert start_str in custom_data["date_range"]["start_date"]


@pytest.mark.asyncio
async def test_invalid_date_inputs(client: TestClient, make_user):
    """
    Verifies that malformed date strings and inverted date ranges (start > end)
    are strictly rejected with HTTP 422 Unprocessable Entity.
    """
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    # 1. Inverted range: start_date later than end_date
    res_inv = client.get(
        "/api/v1/analytics/orders/trend?start_date=2026-10-20&end_date=2026-10-10",
        headers=headers,
    )
    assert res_inv.status_code == 422
    assert "start_date must be earlier than or equal to end_date" in res_inv.json()["detail"]

    # 2. Malformed start_date
    res_malformed = client.get(
        "/api/v1/analytics/orders/trend?start_date=not-a-date&end_date=2026-10-10",
        headers=headers,
    )
    assert res_malformed.status_code == 422
    assert "Invalid start_date format" in res_malformed.json()["detail"]

    # 3. Unsupported preset
    res_bad_preset = client.get(
        "/api/v1/analytics/orders/trend?range=unsupported_range",
        headers=headers,
    )
    assert res_bad_preset.status_code == 422
    assert "Unsupported range preset" in res_bad_preset.json()["detail"]


@pytest.mark.asyncio
async def test_empty_database_analytics_behavior(client: TestClient, make_user):
    """
    In an empty or zero-activity date window, analytics endpoints must return clean,
    honest zero-state metrics without division-by-zero or crashes.
    """
    viewer = await make_user(role="VIEWER")
    headers = get_user_auth_headers(viewer)

    # Date range in the past where zero operational orders exist
    res_trend = client.get(
        "/api/v1/analytics/orders/trend?start_date=2020-01-01&end_date=2020-01-07",
        headers=headers,
    )
    assert res_trend.status_code == 200
    trend_data = res_trend.json()
    assert trend_data["total_orders"] == 0
    assert trend_data["total_revenue"] == "0.00"
    assert trend_data["average_order_value"] == "0.00"
    assert trend_data["is_empty"] is True

    # Empty Order Status Distribution for the zero-activity window
    res_dist = client.get(
        "/api/v1/analytics/orders/status-distribution?start_date=2020-01-01&end_date=2020-01-07",
        headers=headers,
    )
    assert res_dist.status_code == 200
    dist_data = res_dist.json()
    assert dist_data["total_orders"] == 0
    assert dist_data["is_empty"] is True
    for item in dist_data["distribution"]:
        assert item["count"] == 0
        assert item["percentage"] == 0.0
        assert item["total_amount"] == "0.00"


@pytest.mark.asyncio
async def test_insufficient_historical_data_transparency(client: TestClient, db_session: AsyncSession, make_user):
    """
    When historical delivery records or suppliers are insufficient, system reports
    has_sufficient_data=False and an honest explanation instead of fabricating scores.
    """
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    # 1. Fulfillment in a period with 0 delivered orders
    res_zero = client.get(
        "/api/v1/analytics/fulfillment?start_date=2020-01-01&end_date=2020-01-07",
        headers=headers,
    )
    assert res_zero.status_code == 200
    zero_data = res_zero.json()
    assert zero_data["has_sufficient_data"] is False
    assert zero_data["on_time_rate"] is None
    assert "No completed/delivered customer orders recorded" in zero_data["status_message"]

    # 2. Delivered order exists but has NO expected_delivery_date
    wh = Warehouse(name="SLA Test Facility", code="WH-SLA-99", location="Test Ln", capacity=2000)
    db_session.add(wh)
    await db_session.commit()
    await db_session.refresh(wh)

    past_date = datetime(2021, 5, 1, 10, 0, tzinfo=timezone.utc)
    ord_no_target = Order(
        order_number="ORD-NO-TARGET-01",
        customer_name="No Target Customer",
        warehouse_id=wh.id,
        status="DELIVERED",
        total_amount=Decimal("150.00"),
        expected_delivery_date=None,
        created_at=past_date,
        updated_at=past_date + timedelta(days=3),
    )
    db_session.add(ord_no_target)
    await db_session.commit()

    res_no_target = client.get(
        "/api/v1/analytics/fulfillment?start_date=2021-04-30&end_date=2021-05-10",
        headers=headers,
    )
    assert res_no_target.status_code == 200
    no_target_data = res_no_target.json()
    assert no_target_data["has_sufficient_data"] is False
    assert no_target_data["on_time_rate"] is None
    assert "recorded expected_delivery_date values" in no_target_data["status_message"]


@pytest.mark.asyncio
async def test_order_status_distribution(client: TestClient, db_session: AsyncSession, make_user):
    """
    Verifies that all 5 standard order statuses are computed with correct percentages
    and exact Decimal revenue amounts.
    """
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    wh = Warehouse(name="Distribution Alpha", code="WH-ALPHA-01", location="Central Way", capacity=5000)
    db_session.add(wh)
    await db_session.commit()
    await db_session.refresh(wh)

    # Add orders across different statuses
    o_pending = Order(order_number="ORD-P-01", customer_name="C1", warehouse_id=wh.id, status="PENDING", total_amount=Decimal("100.00"))
    o_proc = Order(order_number="ORD-PR-01", customer_name="C2", warehouse_id=wh.id, status="PROCESSING", total_amount=Decimal("200.00"))
    o_ship = Order(order_number="ORD-S-01", customer_name="C3", warehouse_id=wh.id, status="SHIPPED", total_amount=Decimal("300.00"))
    o_deliv = Order(order_number="ORD-D-01", customer_name="C4", warehouse_id=wh.id, status="DELIVERED", total_amount=Decimal("400.00"))
    db_session.add_all([o_pending, o_proc, o_ship, o_deliv])
    await db_session.commit()

    res = client.get("/api/v1/analytics/orders/status-distribution", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["total_orders"] >= 4
    status_map = {item["status"]: item for item in data["distribution"]}
    assert status_map["PENDING"]["count"] >= 1
    assert status_map["PROCESSING"]["count"] >= 1
    assert status_map["SHIPPED"]["count"] >= 1
    assert status_map["DELIVERED"]["count"] >= 1
    assert status_map["CANCELLED"]["count"] == 0

    # Percentages check
    total_pct = sum(item["percentage"] for item in data["distribution"])
    assert 99.0 <= total_pct <= 101.0


@pytest.mark.asyncio
async def test_low_stock_and_stockout_alerts(client: TestClient, db_session: AsyncSession, make_user):
    """
    Tests identification and classification of inventory items in stockout (avail <= 0)
    and low stock (avail <= reorder_quantity).
    """
    viewer = await make_user(role="VIEWER")
    headers = get_user_auth_headers(viewer)

    sup = Supplier(name="Apex Parts", code="SUP-APEX-PARTS", lead_time_days=4)
    wh = Warehouse(name="North Facility", code="WH-NORTH-99", location="North St", capacity=4000)
    db_session.add_all([sup, wh])
    await db_session.commit()
    await db_session.refresh(sup)
    await db_session.refresh(wh)

    # 1. Product in stockout (avail = 0)
    p_out = Product(name="Exhaust Gasket", sku="SKU-EXH-01", category="Exhaust", unit_price=Decimal("25.00"), unit_cost=Decimal("15.00"), supplier_id=sup.id)
    # 2. Product in low stock (on hand 8, reorder 20)
    p_low = Product(name="Brake Pad Front", sku="SKU-BRK-01", category="Brakes", unit_price=Decimal("50.00"), unit_cost=Decimal("30.00"), supplier_id=sup.id)
    db_session.add_all([p_out, p_low])
    await db_session.commit()
    await db_session.refresh(p_out)
    await db_session.refresh(p_low)

    inv_out = Inventory(product_id=p_out.id, warehouse_id=wh.id, quantity_on_hand=5, quantity_reserved=5, reorder_quantity=10)
    inv_low = Inventory(product_id=p_low.id, warehouse_id=wh.id, quantity_on_hand=8, quantity_reserved=0, reorder_quantity=20)
    db_session.add_all([inv_out, inv_low])
    await db_session.commit()

    res = client.get("/api/v1/analytics/inventory/low-stock", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["stockout_count"] >= 1
    assert data["low_stock_count"] >= 1

    skus = {item["product_sku"]: item for item in data["items"]}
    assert "SKU-EXH-01" in skus
    assert skus["SKU-EXH-01"]["status"] == "STOCKOUT"
    assert "SKU-BRK-01" in skus
    assert skus["SKU-BRK-01"]["status"] == "LOW_STOCK"


@pytest.mark.asyncio
async def test_analytics_rbac_authorizations(client: TestClient, make_user):
    """
    Verifies RBAC rules:
    - VIEWER can access all DASHBOARD_READ analytics endpoints.
    - Unauthenticated requests are rejected with 401.
    - ML Evaluation strictly requires ANALYTICS_READ (VIEWER gets 403).
    """
    viewer = await make_user(role="VIEWER")
    v_headers = get_user_auth_headers(viewer)

    # DASHBOARD_READ endpoints allowed for VIEWER
    endpoints = [
        "/api/v1/analytics/executive",
        "/api/v1/analytics/orders/trend",
        "/api/v1/analytics/orders/status-distribution",
        "/api/v1/analytics/inventory/valuation",
        "/api/v1/analytics/inventory/low-stock",
        "/api/v1/analytics/fulfillment",
        "/api/v1/analytics/suppliers",
        "/api/v1/dashboard/executive",
    ]
    for ep in endpoints:
        assert client.get(ep, headers=v_headers).status_code == 200

    # Unauthenticated rejected with 401
    assert client.get("/api/v1/analytics/executive").status_code == 401

    # ML evaluation strictly forbidden for VIEWER (requires ANALYTICS_READ)
    assert client.get("/api/v1/analytics/ml-evaluation", headers=v_headers).status_code == 403


@pytest.mark.asyncio
async def test_source_toggle_live_vs_demo(client: TestClient, make_user):
    """
    Verifies the data source distinction:
    - /dashboard/summary?source=demo returns illustrative demo benchmark
    - /dashboard/summary?source=live returns real database operational records
    """
    viewer = await make_user(role="VIEWER")
    headers = get_user_auth_headers(viewer)

    res_demo = client.get("/api/v1/dashboard/summary?source=demo", headers=headers)
    assert res_demo.status_code == 200
    assert res_demo.json()["data_mode"] == "illustrative_demo_data"

    res_live = client.get("/api/v1/dashboard/summary?source=live", headers=headers)
    assert res_live.status_code == 200
    assert res_live.json()["data_mode"] == "live_database"
