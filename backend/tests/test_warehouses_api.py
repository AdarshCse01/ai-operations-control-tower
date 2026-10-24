"""
Tests for Warehouses API: facility CRUD, unique codes, positive capacity, safe deletion, and RBAC guards.
"""
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.warehouse import Warehouse
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_warehouse_crud_lifecycle(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    code = f"WH-{uuid.uuid4().hex[:6].upper()}"
    create_payload = {
        "code": code,
        "name": "Pacific Distribution Hub",
        "location": "Seattle, WA",
        "capacity": 75000,
    }

    # 1. Create Warehouse
    create_res = client.post("/api/v1/warehouses", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    wh_data = create_res.json()
    assert wh_data["code"] == code
    assert wh_data["capacity"] == 75000
    wh_id = wh_data["id"]

    # 2. Get Warehouse
    get_res = client.get(f"/api/v1/warehouses/{wh_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Pacific Distribution Hub"

    # 3. Update Warehouse
    update_res = client.patch(
        f"/api/v1/warehouses/{wh_id}",
        json={"capacity": 80000, "location": "Tacoma, WA"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["capacity"] == 80000

    # 4. Deactivate Warehouse
    deact_res = client.post(f"/api/v1/warehouses/{wh_id}/deactivate", headers=headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # 5. Delete Warehouse
    del_res = client.delete(f"/api/v1/warehouses/{wh_id}", headers=headers)
    assert del_res.status_code == 204

    # 6. Verify 404
    get_after = client.get(f"/api/v1/warehouses/{wh_id}", headers=headers)
    assert get_after.status_code == 404


@pytest.mark.asyncio
async def test_warehouse_capacity_validation_and_unique_code(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    code = f"WH-{uuid.uuid4().hex[:6].upper()}"
    res1 = client.post(
        "/api/v1/warehouses",
        json={"code": code, "name": "East Coast Depot", "location": "Boston, MA", "capacity": 1000},
        headers=headers,
    )
    assert res1.status_code == 201

    # Duplicate code
    res_dup = client.post(
        "/api/v1/warehouses",
        json={"code": code.lower(), "name": "Duplicate Hub", "location": "Boston, MA", "capacity": 500},
        headers=headers,
    )
    assert res_dup.status_code == 409

    # Non-positive capacity rejected
    res_zero = client.post(
        "/api/v1/warehouses",
        json={"code": f"WH-{uuid.uuid4().hex[:6].upper()}", "name": "Zero Hub", "location": "Boston, MA", "capacity": 0},
        headers=headers,
    )
    assert res_zero.status_code in (422, 400)


@pytest.mark.asyncio
async def test_warehouse_safe_deletion_prevented_with_stock(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6].upper()}", name="Stocked Facility", location="Chicago, IL", capacity=50000)
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Steel Bearings",
        category="Mechanical",
        unit_price=Decimal("18.00"),
        unit_cost=Decimal("10.00"),
    )
    db_session.add_all([wh, prod])
    await db_session.flush()

    inv = Inventory(product_id=prod.id, warehouse_id=wh.id, quantity_on_hand=120, quantity_reserved=0)
    db_session.add(inv)
    await db_session.flush()

    del_res = client.delete(f"/api/v1/warehouses/{wh.id}", headers=headers)
    assert del_res.status_code == 400
    assert "cannot delete warehouse" in del_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_warehouse_rbac_and_audit(client: TestClient, db_session: AsyncSession, make_user):
    viewer = await make_user(role="VIEWER")
    manager = await make_user(role="OPERATIONS_MANAGER")

    v_headers = get_user_auth_headers(viewer)
    m_headers = get_user_auth_headers(manager)

    # Viewer denied on create (403)
    code = f"WH-{uuid.uuid4().hex[:6].upper()}"
    p_body = {"code": code, "name": "Role Test Depot", "location": "Denver, CO", "capacity": 15000}
    v_res = client.post("/api/v1/warehouses", json=p_body, headers=v_headers)
    assert v_res.status_code == 403

    # Operations Manager allowed
    m_res = client.post("/api/v1/warehouses", json=p_body, headers=m_headers)
    assert m_res.status_code == 201
    wh_id = m_res.json()["id"]

    # Verify AuditLog
    stmt = select(AuditLog).where(AuditLog.entity_id == wh_id, AuditLog.action == "warehouse.create")
    audit_entry = (await db_session.execute(stmt)).scalars().first()
    assert audit_entry is not None
    assert audit_entry.actor_id == manager.id
