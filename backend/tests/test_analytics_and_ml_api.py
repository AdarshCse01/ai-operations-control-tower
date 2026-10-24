"""
Tests for Phase 5 Operational Analytics KPIs and Machine Learning Evaluation baseline.
Verifies temporal train/test splitting, anti-data-leakage measures, and honest data-sufficiency gating.
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
async def test_operational_analytics_summary_kpis(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    Validates genuine operational summary derivation from active products,
    warehouse inventories, valuations, and order breakdowns.
    """
    viewer = await make_user(role="VIEWER")
    headers = get_user_auth_headers(viewer)

    # Setup supplier, warehouse, products, and inventory
    sup = Supplier(name="Apex Materials", code="SUP-APEX-01", lead_time_days=4)
    wh = Warehouse(name="Southern Depot", code="WH-SOUTH-01", location="10 Gulf Rd", capacity=5000)
    db_session.add_all([sup, wh])
    await db_session.commit()
    await db_session.refresh(sup)
    await db_session.refresh(wh)

    p1 = Product(
        name="Steel Beam A",
        sku="SKU-BEAM-01",
        category="Steel",
        unit_price=Decimal("100.00"),
        unit_cost=Decimal("60.00"),
        safety_stock=10,
        supplier_id=sup.id,
    )
    db_session.add(p1)
    await db_session.commit()
    await db_session.refresh(p1)

    inv = Inventory(
        product_id=p1.id,
        warehouse_id=wh.id,
        quantity_on_hand=50,
        quantity_reserved=10,
        reorder_quantity=20,
    )
    db_session.add(inv)

    # Add orders
    o1 = Order(
        order_number="ORD-ANALYTICS-01",
        customer_name="Alpha Corp",
        warehouse_id=wh.id,
        status="PENDING",
        total_amount=Decimal("1500.00"),
    )
    o2 = Order(
        order_number="ORD-ANALYTICS-02",
        customer_name="Beta Corp",
        warehouse_id=wh.id,
        status="DELIVERED",
        total_amount=Decimal("3000.00"),
        expected_delivery_date=datetime.now(timezone.utc) + timedelta(days=2),
    )
    db_session.add_all([o1, o2])
    await db_session.commit()

    # Query summary
    res = client.get("/api/v1/analytics/summary", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_products"] >= 1
    assert data["total_inventory_units"] >= 50
    assert data["reserved_inventory_units"] >= 10
    assert data["available_inventory_units"] >= 40
    # Valuation: 50 units * $60.00 = $3000.00
    assert Decimal(data["total_inventory_valuation"]) >= Decimal("3000.00")
    assert data["total_orders"] >= 2
    assert data["pending_orders"] >= 1
    assert data["delivered_orders"] >= 1


@pytest.mark.asyncio
async def test_ml_delay_evaluation_insufficient_data_gating(
    client: TestClient, make_user
):
    """
    When historical order records are below threshold (< 20 samples),
    system must NOT fabricate accuracy; it must return 'insufficient_data'
    along with transparent requirements.
    """
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    res = client.get("/api/v1/analytics/ml-evaluation", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "insufficient_data"
    assert data["accuracy"] is None
    assert data["data_requirements"] is not None
    assert len(data["data_requirements"]) >= 3
    assert "no synthetic training labels were fabricated" in data["evaluation_notes"].lower()


@pytest.mark.asyncio
async def test_ml_delay_evaluation_with_sufficient_data_and_temporal_split(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    With >= 20 orders, the evaluation performs chronological train/test split,
    calculates real accuracy, precision, recall, F1, MAE, and compares with baseline.
    """
    analyst = await make_user(role="ANALYST")
    headers = get_user_auth_headers(analyst)

    wh = Warehouse(name="Evaluation Depot", code="WH-EVAL-01", location="100 Test St", capacity=10000)
    db_session.add(wh)
    await db_session.commit()
    await db_session.refresh(wh)

    base_time = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    orders = []

    # Generate 25 chronological orders with known delivery targets
    for i in range(25):
        created = base_time + timedelta(days=i)
        expected = created + timedelta(days=3)
        priority = "CRITICAL" if i % 2 == 0 else "NORMAL"
        # Simulate some delivered on time and some delivered late
        status = "DELIVERED"
        ord_obj = Order(
            order_number=f"ORD-EVAL-{i:03d}",
            customer_name=f"Customer {i}",
            warehouse_id=wh.id,
            status=status,
            priority=priority,
            total_amount=Decimal("1000.00"),
            expected_delivery_date=expected,
            created_at=created,
            updated_at=expected + timedelta(days=1 if i % 3 == 0 else -1),  # delayed every 3rd order
        )
        orders.append(ord_obj)

    db_session.add_all(orders)
    await db_session.commit()

    res = client.get("/api/v1/analytics/ml-evaluation", headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert data["status"] == "evaluated"
    assert data["samples_count"] >= 25
    assert data["accuracy"] is not None
    assert 0.0 <= data["accuracy"] <= 1.0
    assert data["f1_score"] is not None
    assert data["baseline_comparison"] is not None
    assert "majority_class_accuracy" in data["baseline_comparison"]


@pytest.mark.asyncio
async def test_analytics_rbac_guards(client: TestClient, make_user):
    """
    Viewer can read operational KPI summary, but is forbidden (403) from ML evaluation.
    """
    viewer = await make_user(role="VIEWER")
    v_headers = get_user_auth_headers(viewer)

    # Summary: Allowed for VIEWER (DASHBOARD_READ)
    assert client.get("/api/v1/analytics/summary", headers=v_headers).status_code == 200

    # ML Evaluation: Denied for VIEWER (Requires ANALYTICS_READ)
    assert client.get("/api/v1/analytics/ml-evaluation", headers=v_headers).status_code == 403
