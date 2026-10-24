"""
Tests for Inventory API: atomic receipts, issues, invariant enforcement, idempotency, and RBAC guards.
"""
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_inventory_receipt_and_issue_workflow(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN", full_name="Inventory Admin")
    headers = get_user_auth_headers(admin)

    # 1. Setup product and warehouse
    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6].upper()}", name="Logistics Bay", location="Houston, TX", capacity=20000)
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Servo Actuator",
        category="Robotics",
        unit_price=Decimal("150.00"),
        unit_cost=Decimal("90.00"),
    )
    db_session.add_all([wh, prod])
    await db_session.flush()

    # 2. Inbound Stock Receipt
    receipt_payload = {
        "product_id": str(prod.id),
        "warehouse_id": str(wh.id),
        "quantity": 100,
        "reference": "PO-2026-001",
        "idempotency_key": f"key-{uuid.uuid4().hex[:8]}",
    }
    receipt_res = client.post("/api/v1/inventory/receipt", json=receipt_payload, headers=headers)
    assert receipt_res.status_code == 200
    r_data = receipt_res.json()
    assert r_data["quantity_on_hand"] == 100
    assert r_data["quantity_reserved"] == 0
    assert r_data["available_quantity"] == 100

    # 3. Outbound Stock Issue
    issue_payload = {
        "product_id": str(prod.id),
        "warehouse_id": str(wh.id),
        "quantity": 35,
        "reference": "DISPATCH-991",
        "idempotency_key": f"key-{uuid.uuid4().hex[:8]}",
    }
    issue_res = client.post("/api/v1/inventory/issue", json=issue_payload, headers=headers)
    assert issue_res.status_code == 200
    i_data = issue_res.json()
    assert i_data["quantity_on_hand"] == 65
    assert i_data["available_quantity"] == 65

    # 4. Check Stock Movements Log
    mov_res = client.get(f"/api/v1/inventory/movements?product_id={prod.id}", headers=headers)
    assert mov_res.status_code == 200
    movements = mov_res.json()["items"]
    assert len(movements) == 2
    types = [m["movement_type"] for m in movements]
    assert "RECEIPT" in types
    assert "ISSUE" in types


@pytest.mark.asyncio
async def test_inventory_insufficient_stock_invariant_prevented(
    client: TestClient, db_session: AsyncSession, make_user
):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6].upper()}", name="Tight Bay", location="Austin, TX", capacity=5000)
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Precision Sensor",
        category="Sensors",
        unit_price=Decimal("40.00"),
        unit_cost=Decimal("20.00"),
    )
    db_session.add_all([wh, prod])
    await db_session.flush()

    # Receive 10 units
    client.post(
        "/api/v1/inventory/receipt",
        json={"product_id": str(prod.id), "warehouse_id": str(wh.id), "quantity": 10, "reference": "INIT"},
        headers=headers,
    )

    # Attempt to issue 15 units (exceeds 10 available)
    issue_res = client.post(
        "/api/v1/inventory/issue",
        json={"product_id": str(prod.id), "warehouse_id": str(wh.id), "quantity": 15, "reference": "OVERDRAFT"},
        headers=headers,
    )
    assert issue_res.status_code == 400
    assert "insufficient available stock" in issue_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_inventory_idempotency_prevents_duplicate_movements(
    client: TestClient, db_session: AsyncSession, make_user
):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6].upper()}", name="Idempotent Hub", location="Reno, NV", capacity=10000)
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Lithium Cell",
        category="Power",
        unit_price=Decimal("30.00"),
        unit_cost=Decimal("15.00"),
    )
    db_session.add_all([wh, prod])
    await db_session.flush()

    idemp_key = f"idemp-{uuid.uuid4().hex}"
    receipt_body = {
        "product_id": str(prod.id),
        "warehouse_id": str(wh.id),
        "quantity": 50,
        "reference": "BATCH-1",
        "idempotency_key": idemp_key,
    }

    # First request
    res1 = client.post("/api/v1/inventory/receipt", json=receipt_body, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["quantity_on_hand"] == 50

    # Duplicate request with identical idempotency key
    res2 = client.post("/api/v1/inventory/receipt", json=receipt_body, headers=headers)
    assert res2.status_code == 200
    # Quantity MUST remain 50, not double to 100
    assert res2.json()["quantity_on_hand"] == 50

    # Confirm only 1 movement record exists for this idempotency key
    stmt = select(StockMovement).where(StockMovement.idempotency_key == idemp_key)
    movs = (await db_session.execute(stmt)).scalars().all()
    assert len(movs) == 1


@pytest.mark.asyncio
async def test_inventory_rbac_write_guards(client: TestClient, db_session: AsyncSession, make_user):
    viewer = await make_user(role="VIEWER")
    analyst = await make_user(role="ANALYST")
    mgr = await make_user(role="OPERATIONS_MANAGER")

    v_headers = get_user_auth_headers(viewer)
    a_headers = get_user_auth_headers(analyst)
    m_headers = get_user_auth_headers(mgr)

    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6].upper()}", name="RBAC Facility", location="Phoenix, AZ", capacity=5000)
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Relay Module",
        category="Electronics",
        unit_price=Decimal("10.00"),
        unit_cost=Decimal("5.00"),
    )
    db_session.add_all([wh, prod])
    await db_session.flush()

    # Viewer and Analyst can view inventory list
    assert client.get("/api/v1/inventory", headers=v_headers).status_code == 200
    assert client.get("/api/v1/inventory", headers=a_headers).status_code == 200

    # Viewer and Analyst denied on receipt (403)
    p_body = {"product_id": str(prod.id), "warehouse_id": str(wh.id), "quantity": 10, "reference": "RBAC-TEST"}
    assert client.post("/api/v1/inventory/receipt", json=p_body, headers=v_headers).status_code == 403
    assert client.post("/api/v1/inventory/receipt", json=p_body, headers=a_headers).status_code == 403

    # Operations Manager allowed (200)
    mgr_res = client.post("/api/v1/inventory/receipt", json=p_body, headers=m_headers)
    assert mgr_res.status_code == 200
