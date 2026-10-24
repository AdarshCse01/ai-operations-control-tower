"""
Tests for Orders API: server-calculated totals, status state machine, multi-item creation, and RBAC guards.
"""
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.warehouse import Warehouse
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_order_creation_server_calculated_totals(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN", full_name="Order Admin")
    headers = get_user_auth_headers(admin)

    # 1. Setup products with prices in DB
    p1 = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Industrial Sensor",
        category="Sensors",
        unit_price=Decimal("120.00"),
        unit_cost=Decimal("70.00"),
    )
    p2 = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Wiring Loom",
        category="Hardware",
        unit_price=Decimal("15.50"),
        unit_cost=Decimal("8.00"),
    )
    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6].upper()}", name="Order Depot", location="Atlanta, GA", capacity=50000)
    db_session.add_all([p1, p2, wh])
    await db_session.flush()

    # 2. Create Order with 2 line items:
    # 2 x p1 ($120.00) = $240.00
    # 4 x p2 ($15.50)  = $62.00
    # Total = $302.00
    create_payload = {
        "customer_name": "Apex Manufacturing",
        "priority": "HIGH",
        "warehouse_id": str(wh.id),
        "items": [
            {"product_id": str(p1.id), "quantity": 2},
            {"product_id": str(p2.id), "quantity": 4},
        ],
    }

    res = client.post("/api/v1/orders", json=create_payload, headers=headers)
    assert res.status_code == 201
    order_data = res.json()
    assert order_data["customer_name"] == "Apex Manufacturing"
    assert order_data["status"] == "PENDING"
    assert order_data["priority"] == "HIGH"
    assert Decimal(str(order_data["total_amount"])) == Decimal("302.00")
    assert len(order_data["items"]) == 2
    order_id = order_data["id"]

    # Verify line item sub-totals
    items = {item["product_id"]: item for item in order_data["items"]}
    assert Decimal(str(items[str(p1.id)]["subtotal"])) == Decimal("240.00")
    assert Decimal(str(items[str(p2.id)]["subtotal"])) == Decimal("62.00")

    # 3. Retrieve order
    get_res = client.get(f"/api/v1/orders/{order_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["warehouse_code"] == wh.code
    assert get_res.json()["created_by_name"] == "Order Admin"


@pytest.mark.asyncio
async def test_order_status_state_machine_transitions(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Testing Probe",
        category="Test",
        unit_price=Decimal("50.00"),
        unit_cost=Decimal("25.00"),
    )
    db_session.add(prod)
    await db_session.flush()

    res = client.post(
        "/api/v1/orders",
        json={"customer_name": "State Tester", "items": [{"product_id": str(prod.id), "quantity": 1}]},
        headers=headers,
    )
    order_id = res.json()["id"]

    # Valid step 1: PENDING -> PROCESSING
    p1 = client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "PROCESSING", "comment": "Started packing"}, headers=headers)
    assert p1.status_code == 200
    assert p1.json()["status"] == "PROCESSING"

    # Invalid jump: PROCESSING -> DELIVERED (Must be SHIPPED first)
    p_invalid = client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "DELIVERED"}, headers=headers)
    assert p_invalid.status_code == 400
    assert "invalid status transition" in p_invalid.json()["detail"].lower()

    # Valid step 2: PROCESSING -> SHIPPED
    p2 = client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "SHIPPED", "comment": "Handed to FedEx"}, headers=headers)
    assert p2.status_code == 200
    assert p2.json()["status"] == "SHIPPED"

    # Valid step 3: SHIPPED -> DELIVERED
    p3 = client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "DELIVERED", "comment": "Signed by customer"}, headers=headers)
    assert p3.status_code == 200
    assert p3.json()["status"] == "DELIVERED"

    # Terminal state: Cannot transition out of DELIVERED
    p_term = client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "CANCELLED"}, headers=headers)
    assert p_term.status_code == 400
    assert "invalid status transition" in p_term.json()["detail"].lower()


@pytest.mark.asyncio
async def test_order_rbac_and_audit(client: TestClient, db_session: AsyncSession, make_user):
    viewer = await make_user(role="VIEWER")
    mgr = await make_user(role="OPERATIONS_MANAGER")

    v_headers = get_user_auth_headers(viewer)
    m_headers = get_user_auth_headers(mgr)

    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="RBAC Module",
        category="General",
        unit_price=Decimal("100.00"),
        unit_cost=Decimal("50.00"),
    )
    db_session.add(prod)
    await db_session.flush()

    order_payload = {"customer_name": "RBAC Corp", "items": [{"product_id": str(prod.id), "quantity": 1}]}

    # Viewer denied creation (403)
    v_res = client.post("/api/v1/orders", json=order_payload, headers=v_headers)
    assert v_res.status_code == 403

    # Operations Manager allowed (201)
    m_res = client.post("/api/v1/orders", json=order_payload, headers=m_headers)
    assert m_res.status_code == 201
    order_id = m_res.json()["id"]

    # Verify AuditLog created
    stmt = select(AuditLog).where(AuditLog.entity_id == order_id, AuditLog.action == "order.create")
    entry = (await db_session.execute(stmt)).scalars().first()
    assert entry is not None
    assert entry.actor_id == mgr.id
