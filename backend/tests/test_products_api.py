"""
Tests for Products API: catalog CRUD, SKU uniqueness, Decimal pricing, sorting, safe deletion, and RBAC guards.
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
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_product_crud_lifecycle(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    # Pre-create a supplier
    sup = Supplier(name="Foundry Corp", code=f"SUP-{uuid.uuid4().hex[:6].upper()}")
    db_session.add(sup)
    await db_session.flush()

    sku = f"SKU-{uuid.uuid4().hex[:8].upper()}"
    create_payload = {
        "sku": sku,
        "name": "Microcontroller Unit V2",
        "description": "High-efficiency MCU",
        "category": "Semiconductors",
        "unit_price": "89.50",
        "unit_cost": "52.25",
        "reorder_point": 25,
        "safety_stock": 10,
        "supplier_id": str(sup.id),
    }

    # 1. Create Product
    create_res = client.post("/api/v1/products", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["sku"] == sku
    assert created_data["name"] == "Microcontroller Unit V2"
    assert Decimal(str(created_data["unit_price"])) == Decimal("89.50")
    assert Decimal(str(created_data["unit_cost"])) == Decimal("52.25")
    assert created_data["supplier_name"] == "Foundry Corp"
    prod_id = created_data["id"]

    # 2. Get Product
    get_res = client.get(f"/api/v1/products/{prod_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == prod_id
    assert get_res.json()["supplier_name"] == "Foundry Corp"

    # 3. Update Product
    update_res = client.patch(
        f"/api/v1/products/{prod_id}",
        json={"unit_price": "95.00", "reorder_point": 30},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert Decimal(str(update_res.json()["unit_price"])) == Decimal("95.00")
    assert update_res.json()["reorder_point"] == 30

    # 4. Deactivate Product
    deact_res = client.post(f"/api/v1/products/{prod_id}/deactivate", headers=headers)
    assert deact_res.status_code == 200
    assert deact_res.json()["is_active"] is False

    # 5. Delete Product (no inventory or orders)
    del_res = client.delete(f"/api/v1/products/{prod_id}", headers=headers)
    assert del_res.status_code == 204

    # 6. Verify 404
    get_after_del = client.get(f"/api/v1/products/{prod_id}", headers=headers)
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_product_sku_uniqueness_and_invalid_supplier(client: TestClient, db_session: AsyncSession, make_user):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    sku = f"SKU-{uuid.uuid4().hex[:6].upper()}"
    p1 = {
        "sku": sku,
        "name": "Optical Sensor",
        "category": "Sensors",
        "unit_price": "15.00",
        "unit_cost": "8.00",
    }
    res1 = client.post("/api/v1/products", json=p1, headers=headers)
    assert res1.status_code == 201

    # Duplicate SKU
    res2 = client.post(
        "/api/v1/products",
        json={"sku": sku.lower(), "name": "Other Sensor", "category": "Sensors", "unit_price": "20.00", "unit_cost": "10.00"},
        headers=headers,
    )
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()

    # Invalid non-existent supplier
    random_sup_id = str(uuid.uuid4())
    res3 = client.post(
        "/api/v1/products",
        json={
            "sku": f"SKU-{uuid.uuid4().hex[:6].upper()}",
            "name": "Wire Harness",
            "category": "Cables",
            "unit_price": "5.00",
            "unit_cost": "2.00",
            "supplier_id": random_sup_id,
        },
        headers=headers,
    )
    assert res3.status_code == 400
    assert "does not exist" in res3.json()["detail"].lower()


@pytest.mark.asyncio
async def test_product_safe_deletion_prevented_with_active_inventory(
    client: TestClient, db_session: AsyncSession, make_user
):
    admin = await make_user(role="ADMIN")
    headers = get_user_auth_headers(admin)

    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Inductive Coil",
        category="Hardware",
        unit_price=Decimal("12.50"),
        unit_cost=Decimal("7.00"),
    )
    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6].upper()}", name="Central Hub", location="Dallas, TX", capacity=10000)
    db_session.add_all([prod, wh])
    await db_session.flush()

    inv = Inventory(product_id=prod.id, warehouse_id=wh.id, quantity_on_hand=50, quantity_reserved=0)
    db_session.add(inv)
    await db_session.flush()

    del_res = client.delete(f"/api/v1/products/{prod.id}", headers=headers)
    assert del_res.status_code == 400
    assert "cannot delete product" in del_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_product_rbac_and_audit_trail(client: TestClient, db_session: AsyncSession, make_user):
    analyst = await make_user(role="ANALYST")
    manager = await make_user(role="OPERATIONS_MANAGER")

    analyst_headers = get_user_auth_headers(analyst)
    mgr_headers = get_user_auth_headers(manager)

    # Analyst can read
    list_res = client.get("/api/v1/products", headers=analyst_headers)
    assert list_res.status_code == 200

    # Analyst cannot create (403)
    sku = f"SKU-{uuid.uuid4().hex[:6].upper()}"
    p_body = {"sku": sku, "name": "Analyst Blocked", "category": "General", "unit_price": "10.00", "unit_cost": "5.00"}
    write_res = client.post("/api/v1/products", json=p_body, headers=analyst_headers)
    assert write_res.status_code == 403

    # Operations Manager can create
    mgr_res = client.post("/api/v1/products", json=p_body, headers=mgr_headers)
    assert mgr_res.status_code == 201
    prod_id = mgr_res.json()["id"]

    # Verify audit log entry
    stmt = select(AuditLog).where(AuditLog.entity_id == prod_id, AuditLog.action == "product.create")
    entry = (await db_session.execute(stmt)).scalars().first()
    assert entry is not None
    assert entry.actor_id == manager.id
