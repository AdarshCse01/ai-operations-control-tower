"""
Tests for Phase 5 Operational Risk Intelligence engine and API.
Validates explainable, deterministic scoring across stockout, supplier SLA, order delays, and inventory imbalances.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import Inventory
from app.models.order import Order
from app.models.product import Product
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_risk_intelligence_response_structure(client: TestClient, make_user):
    """Risk endpoint returns valid schema, severity breakdown, and bounded scores."""
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    response = client.get("/api/v1/risks", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == len(data["items"])
    assert data["critical_count"] == sum(1 for r in data["items"] if r["severity"] == "CRITICAL")
    assert data["high_count"] == sum(1 for r in data["items"] if r["severity"] == "HIGH")
    assert data["data_mode"] == "live_database"
    assert all(0 <= r["score"] <= 100 for r in data["items"])



@pytest.mark.asyncio
async def test_risk_intelligence_rbac_guards(client: TestClient, make_user):
    """Only roles with ANALYTICS_READ (ANALYST, OPERATIONS_MANAGER, ADMIN) may access risks."""
    viewer = await make_user(role="VIEWER")
    analyst = await make_user(role="ANALYST")

    # Viewer denied
    res_viewer = client.get("/api/v1/risks", headers=get_user_auth_headers(viewer))
    assert res_viewer.status_code == 403

    # Analyst allowed
    res_analyst = client.get("/api/v1/risks", headers=get_user_auth_headers(analyst))
    assert res_analyst.status_code == 200


@pytest.mark.asyncio
async def test_risk_intelligence_stockout_and_safety_stock_scores(
    client: TestClient, db_session: AsyncSession, make_user
):
    """Verifies deterministic scoring for depleted inventory and safety buffer breaches."""
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    # 1. Setup supplier & warehouse
    sup = Supplier(name="Test Chipset Corp", code="SUP-CHIP-01", lead_time_days=10, reliability_score=Decimal("0.95"))
    wh = Warehouse(name="North Central Hub", code="WH-NC-01", location="100 Logistics Pkwy", capacity=5000)
    db_session.add_all([sup, wh])
    await db_session.commit()
    await db_session.refresh(sup)
    await db_session.refresh(wh)

    # 2. Setup product with stockout (avail == 0)
    p_depleted = Product(
        name="Industrial Sensor X1",
        sku="SKU-DEP-001",
        category="Sensors",
        unit_price=Decimal("150.00"),
        unit_cost=Decimal("100.00"),
        safety_stock=10,
        supplier_id=sup.id,
    )
    # 3. Setup product with safety stock breach (avail == 5 <= safety_stock 10)
    p_low = Product(
        name="Microcontroller MC-2",
        sku="SKU-LOW-002",
        category="Chips",
        unit_price=Decimal("45.00"),
        unit_cost=Decimal("30.00"),
        safety_stock=10,
        supplier_id=sup.id,
    )
    db_session.add_all([p_depleted, p_low])

    await db_session.commit()
    await db_session.refresh(p_depleted)
    await db_session.refresh(p_low)

    # 4. Attach inventories
    inv_dep = Inventory(
        product_id=p_depleted.id,
        warehouse_id=wh.id,
        quantity_on_hand=5,
        quantity_reserved=5,  # available = 0
        reorder_quantity=20,
    )
    inv_low = Inventory(
        product_id=p_low.id,
        warehouse_id=wh.id,
        quantity_on_hand=8,
        quantity_reserved=3,  # available = 5 <= safety 10
        reorder_quantity=20,
    )
    db_session.add_all([inv_dep, inv_low])
    await db_session.commit()


    # Query risks endpoint
    response = client.get("/api/v1/risks", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] >= 2

    # Find stockout risk item
    stockout_risk = next((r for r in data["items"] if r["entity_id"] == str(p_depleted.id)), None)
    assert stockout_risk is not None
    assert stockout_risk["category"] == "STOCKOUT_RISK"
    assert stockout_risk["severity"] == "CRITICAL"
    assert stockout_risk["score"] == 100
    assert "available_stock (0) <= 0" in stockout_risk["rules_triggered"]
    assert "suggested_action" in stockout_risk

    # Find safety stock breach risk item
    safety_risk = next((r for r in data["items"] if r["entity_id"] == str(p_low.id)), None)
    assert safety_risk is not None
    assert safety_risk["category"] == "STOCKOUT_RISK"
    assert safety_risk["severity"] == "CRITICAL"
    assert safety_risk["score"] == 85
    assert any("safety_stock" in r for r in safety_risk["rules_triggered"])


@pytest.mark.asyncio
async def test_risk_intelligence_supplier_and_order_delays(
    client: TestClient, db_session: AsyncSession, make_user
):
    """Verifies supplier SLA deficit detection and overdue customer orders."""
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    now = datetime.now(timezone.utc)

    # 1. Supplier with low reliability (< 0.85)
    unreliable_sup = Supplier(
        name="Shaky Logistics Co",
        code="SUP-UNREL-01",
        lead_time_days=15,
        reliability_score=Decimal("0.72"),
    )
    wh = Warehouse(name="East Coast Depot", code="WH-EC-01", location="200 Harbor Rd", capacity=5000)
    db_session.add_all([unreliable_sup, wh])
    await db_session.commit()
    await db_session.refresh(unreliable_sup)
    await db_session.refresh(wh)

    # 2. Overdue Order
    overdue_order = Order(
        order_number="ORD-TEST-OVERDUE-01",
        customer_name="Acme Global Industries",
        warehouse_id=wh.id,
        status="PROCESSING",
        priority="HIGH",
        total_amount=Decimal("12500.00"),
        expected_delivery_date=now - timedelta(days=3),  # 3 days overdue
    )
    db_session.add(overdue_order)
    await db_session.commit()
    await db_session.refresh(overdue_order)


    # Fetch risks
    response = client.get("/api/v1/risks", headers=headers)
    assert response.status_code == 200
    data = response.json()

    # Verify supplier risk
    sup_risk = next((r for r in data["items"] if r["entity_id"] == str(unreliable_sup.id)), None)
    assert sup_risk is not None
    assert sup_risk["category"] == "SUPPLIER_RISK"
    assert sup_risk["score"] >= 60
    assert any("reliability_score" in rule for rule in sup_risk["rules_triggered"])
    assert "72.0%" in sup_risk["explanation"]

    # Verify order delay risk
    ord_risk = next((r for r in data["items"] if r["entity_id"] == str(overdue_order.id)), None)
    assert ord_risk is not None
    assert ord_risk["category"] == "FULFILLMENT_RISK"
    assert ord_risk["severity"] == "CRITICAL"
    assert ord_risk["score"] >= 80
    assert "overdue" in ord_risk["explanation"].lower()
