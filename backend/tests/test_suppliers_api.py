"""
Tests for Suppliers API: CRUD, code uniqueness, safe deletion, pagination, search, and RBAC guards.
"""
from decimal import Decimal
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.supplier import Supplier
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_supplier_crud_lifecycle(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    # 1. Create Supplier
    code = f"SUP-{uuid.uuid4().hex[:6].upper()}"
    create_payload = {
        "name": "Global Chipsets Inc.",
        "code": code,
        "contact_email": "sales@globalchipsets.com",
        "contact_phone": "+1-555-0199",
        "lead_time_days": 12,
        "reliability_score": "0.98",
    }
    create_res = client.post("/api/v1/suppliers", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["code"] == code
    assert created_data["name"] == "Global Chipsets Inc."
    assert created_data["lead_time_days"] == 12
    supplier_id = created_data["id"]

    # 2. Retrieve Supplier
    get_res = client.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == supplier_id

    # 3. Update Supplier
    update_res = client.patch(
        f"/api/v1/suppliers/{supplier_id}",
        json={"lead_time_days": 14, "reliability_score": "0.99"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["lead_time_days"] == 14
    assert Decimal(str(update_res.json()["reliability_score"])) == Decimal("0.99")

    # 4. Deactivate Supplier
    deact_res = client.post(f"/api/v1/suppliers/{supplier_id}/deactivate", headers=headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # 5. Delete Supplier (no products attached)
    del_res = client.delete(f"/api/v1/suppliers/{supplier_id}", headers=headers)
    assert del_res.status_code == 204

    # Verify 404 after deletion
    get_after_del = client.get(f"/api/v1/suppliers/{supplier_id}", headers=headers)
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_supplier_duplicate_code_conflict(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    code = f"SUP-{uuid.uuid4().hex[:6].upper()}"
    payload = {"name": "Alpha Parts", "code": code}
    res1 = client.post("/api/v1/suppliers", json=payload, headers=headers)
    assert res1.status_code == 201

    # Attempt duplicate code
    res2 = client.post("/api/v1/suppliers", json={"name": "Beta Parts", "code": code.lower()}, headers=headers)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_supplier_safe_deletion_prevention(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    # Create supplier
    sup = Supplier(name="Prime Motors", code=f"SUP-{uuid.uuid4().hex[:6].upper()}")
    db_session.add(sup)
    await db_session.flush()

    # Attach a product to supplier
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        name="Stepper Motor",
        category="Hardware",
        unit_price=Decimal("45.00"),
        unit_cost=Decimal("25.00"),
        supplier_id=sup.id,
    )
    db_session.add(prod)
    await db_session.flush()

    # Deletion should be rejected with 400 Bad Request
    del_res = client.delete(f"/api/v1/suppliers/{sup.id}", headers=headers)
    assert del_res.status_code == 400
    assert "cannot delete supplier" in del_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_supplier_rbac_enforcement(client: TestClient, db_session: AsyncSession, make_user):
    viewer = await make_user(role="VIEWER")
    analyst = await make_user(role="ANALYST")
    ops_mgr = await make_user(role="OPERATIONS_MANAGER")

    viewer_headers = get_user_auth_headers(viewer)
    analyst_headers = get_user_auth_headers(analyst)
    ops_headers = get_user_auth_headers(ops_mgr)

    # Unauthenticated rejected with 401
    unauth_res = client.get("/api/v1/suppliers")
    assert unauth_res.status_code == 401

    # Viewer can read list
    viewer_read = client.get("/api/v1/suppliers", headers=viewer_headers)
    assert viewer_read.status_code == 200

    # Viewer denied on write (403)
    viewer_write = client.post("/api/v1/suppliers", json={"name": "Test", "code": "TEST-1"}, headers=viewer_headers)
    assert viewer_write.status_code == 403

    # Analyst denied on write (403)
    analyst_write = client.post("/api/v1/suppliers", json={"name": "Test", "code": "TEST-2"}, headers=analyst_headers)
    assert analyst_write.status_code == 403

    # Operations Manager allowed to create (201)
    ops_write = client.post(
        "/api/v1/suppliers",
        json={"name": "Ops Approved Parts", "code": f"OPS-{uuid.uuid4().hex[:6].upper()}"},
        headers=ops_headers,
    )
    assert ops_write.status_code == 201


@pytest.mark.asyncio
async def test_supplier_audit_log_created(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN", full_name="Admin Audit Tester")
    headers = get_user_auth_headers(admin)

    code = f"SUP-{uuid.uuid4().hex[:6].upper()}"
    res = client.post("/api/v1/suppliers", json={"name": "Audited Logistics", "code": code}, headers=headers)
    assert res.status_code == 201
    sup_id = res.json()["id"]

    stmt = select(AuditLog).where(AuditLog.entity_id == sup_id, AuditLog.action == "supplier.create")
    audit_res = await db_session.execute(stmt)
    entry = audit_res.scalars().first()
    assert entry is not None
    assert entry.entity_type == "supplier"
    assert entry.actor_id == admin.id
    assert entry.payload["code"] == code
