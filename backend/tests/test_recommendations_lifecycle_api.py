"""
Tests for Phase 5 Recommendation Generation, Human Approval Workflow,
Idempotent Safe Execution, and Database Audit Trails.
"""
from datetime import datetime, timezone
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.recommendation import Recommendation
from app.models.supplier import Supplier
from app.models.warehouse import Warehouse
from tests.conftest import get_user_auth_headers


@pytest.mark.asyncio
async def test_recommendation_generation_and_deduplication(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    Generating recommendations multiple times for the same underlying operational risk
    must update the existing pending record and never create duplicate pending rows.
    """
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    sup = Supplier(name="Primary Parts Ltd", code="SUP-PART-01", lead_time_days=7)
    wh = Warehouse(name="Main Depot", code="WH-MAIN-01", location="1 Warehouse Row", capacity=10000)
    db_session.add_all([sup, wh])
    await db_session.commit()
    await db_session.refresh(sup)
    await db_session.refresh(wh)

    prod = Product(
        name="Turbine Valve A",
        sku="SKU-TURB-01",
        category="Valves",
        unit_price=Decimal("500.00"),
        unit_cost=Decimal("350.00"),
        safety_stock=20,
        supplier_id=sup.id,
    )

    db_session.add(prod)
    await db_session.commit()
    await db_session.refresh(prod)

    inv = Inventory(
        product_id=prod.id,
        warehouse_id=wh.id,
        quantity_on_hand=0,
        quantity_reserved=0,  # Available = 0 -> Stockout
        reorder_quantity=30,
    )
    db_session.add(inv)
    await db_session.commit()

    # Initial call: generates recommendation
    res1 = client.get("/api/v1/recommendations", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    recs1 = [r for r in data1["items"] if r["entity_id"] == str(prod.id)]
    assert len(recs1) == 1
    rec_id_1 = recs1[0]["id"]
    assert recs1[0]["recommendation_type"] == "STOCK_REORDER"
    assert recs1[0]["status"] == "PENDING"
    assert recs1[0]["proposed_action"] == "reorder_stock"

    # Second call (refresh): deduplication must preserve single row
    res2 = client.get("/api/v1/recommendations", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    recs2 = [r for r in data2["items"] if r["entity_id"] == str(prod.id)]
    assert len(recs2) == 1
    assert recs2[0]["id"] == rec_id_1  # Exact same ID, no duplicate row created


@pytest.mark.asyncio
async def test_recommendation_human_approval_rejection_flow(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    Tests approval and rejection state transitions, comment recording, and audit trails.
    """
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    rec = Recommendation(
        recommendation_type="STOCK_REORDER",
        priority="HIGH",
        title="Replenish stock for test SKU",
        entity_type="product",
        entity_id="test-sku-entity",
        entity_name="Test SKU",
        explanation="Test explanation",
        proposed_action="reorder_stock",
        status="PENDING",
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)

    # Approve recommendation
    appr_res = client.post(
        f"/api/v1/recommendations/{rec.id}/approval",
        json={"approved": True, "comment": "Approved by Operations Lead"},
        headers=headers,
    )
    assert appr_res.status_code == 200
    appr_data = appr_res.json()
    assert appr_data["status"] == "approved"
    assert appr_data["recommendation_status"] == "APPROVED"
    assert appr_data["item"]["status"] == "APPROVED"
    assert appr_data["item"]["decision_comment"] == "Approved by Operations Lead"
    assert appr_data["item"]["decided_by_name"] is not None

    # Audit log check
    audit_res = await db_session.execute(
        select(AuditLog).where(AuditLog.entity_id == str(rec.id), AuditLog.action == "recommendation.approved")
    )
    audit = audit_res.scalar_one_or_none()
    assert audit is not None
    assert audit.actor_id == manager.id

    # Trying to approve an already approved recommendation must fail with 400
    dup_appr = client.post(
        f"/api/v1/recommendations/{rec.id}/approval",
        json={"approved": True, "comment": "Trying duplicate decision"},
        headers=headers,
    )
    assert dup_appr.status_code == 400


@pytest.mark.asyncio
async def test_recommendation_safe_execution_and_idempotency(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    Tests transactional execution of an approved recommendation, database re-validation,
    inventory updates, and idempotency on duplicate execution requests.
    """
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    sup = Supplier(name="Hydraulic Corp", code="SUP-HYD-01", lead_time_days=5)
    wh = Warehouse(name="Central Distribution", code="WH-CD-01", location="50 Hub St", capacity=10000)
    db_session.add_all([sup, wh])
    await db_session.commit()
    await db_session.refresh(sup)
    await db_session.refresh(wh)

    prod = Product(
        name="Hydraulic Valve",
        sku="SKU-HYD-01",
        category="Valves",
        unit_price=Decimal("200.00"),
        unit_cost=Decimal("120.00"),
        safety_stock=10,
        supplier_id=sup.id,
    )

    db_session.add(prod)
    await db_session.commit()
    await db_session.refresh(prod)

    inv = Inventory(
        product_id=prod.id,
        warehouse_id=wh.id,
        quantity_on_hand=5,
        quantity_reserved=0,
        reorder_quantity=20,
    )
    db_session.add(inv)
    await db_session.commit()
    await db_session.refresh(inv)

    # 1. Create APPROVED recommendation
    rec = Recommendation(
        recommendation_type="STOCK_REORDER",
        priority="HIGH",
        title=f"Replenish {prod.sku}",
        entity_type="product",
        entity_id=str(prod.id),
        entity_name=prod.sku,
        explanation="Inventory is low",
        proposed_action="reorder_stock",
        parameters={"product_id": str(prod.id), "warehouse_id": str(wh.id), "quantity": 40},
        status="APPROVED",
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)

    # 2. Execute recommendation
    exec_res = client.post(
        f"/api/v1/recommendations/{rec.id}/execute",
        json={"comment": "Executed automated PO receipt"},
        headers=headers,
    )
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] == "executed"
    assert exec_data["recommendation_status"] == "EXECUTED"
    assert exec_data["execution_result"]["quantity_received"] == 40
    assert exec_data["execution_result"]["new_quantity_on_hand"] == 45  # 5 + 40

    # Verify inventory in database
    await db_session.refresh(inv)
    assert inv.quantity_on_hand == 45

    # 3. Idempotency test: calling execute again should safely return without re-adding 40 units
    exec_res_2 = client.post(
        f"/api/v1/recommendations/{rec.id}/execute",
        json={"comment": "Duplicate execution attempt"},
        headers=headers,
    )
    assert exec_res_2.status_code == 200
    await db_session.refresh(inv)
    assert inv.quantity_on_hand == 45  # Stays 45, no duplicate receipt!


@pytest.mark.asyncio
async def test_recommendation_unauthorized_rbac_rejection(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    ANALYST and VIEWER roles must be rejected (403 Forbidden) from approving or executing recommendations.
    """
    analyst = await make_user(role="ANALYST")
    viewer = await make_user(role="VIEWER")

    rec = Recommendation(
        recommendation_type="STOCK_REORDER",
        priority="HIGH",
        title="Test Guarded Rec",
        entity_type="product",
        entity_id="prod-guard-01",
        entity_name="Test Guard",
        explanation="Test explanation",
        proposed_action="reorder_stock",
        status="PENDING",
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)

    # Viewer cannot approve or execute
    v_headers = get_user_auth_headers(viewer)
    assert client.post(f"/api/v1/recommendations/{rec.id}/approval", json={"approved": True}, headers=v_headers).status_code == 403
    assert client.post(f"/api/v1/recommendations/{rec.id}/execute", json={}, headers=v_headers).status_code == 403

    # Analyst cannot approve or execute
    a_headers = get_user_auth_headers(analyst)
    assert client.post(f"/api/v1/recommendations/{rec.id}/approval", json={"approved": True}, headers=a_headers).status_code == 403
    assert client.post(f"/api/v1/recommendations/{rec.id}/execute", json={}, headers=a_headers).status_code == 403


@pytest.mark.asyncio
async def test_recommendation_stale_entity_safely_rejected(
    client: TestClient, db_session: AsyncSession, make_user
):
    """
    If the target product becomes inactive prior to execution, the execution
    must safely abort and reject the stale recommendation with 400 Bad Request.
    """
    manager = await make_user(role="OPERATIONS_MANAGER")
    headers = get_user_auth_headers(manager)

    sup = Supplier(name="Stale Vendor", code="SUP-STALE-01", lead_time_days=3)
    wh = Warehouse(name="Stale WH", code="WH-STALE-01", location="9 Stale Way", capacity=5000)
    db_session.add_all([sup, wh])
    await db_session.commit()
    await db_session.refresh(sup)
    await db_session.refresh(wh)

    prod = Product(
        name="Deactivated Part",
        sku="SKU-DEACT-01",
        category="Parts",
        unit_price=Decimal("10.00"),
        unit_cost=Decimal("5.00"),
        safety_stock=5,
        supplier_id=sup.id,
        is_active=False,  # Product has been deactivated!
    )
    db_session.add(prod)
    await db_session.commit()
    await db_session.refresh(prod)

    rec = Recommendation(
        recommendation_type="STOCK_REORDER",
        priority="HIGH",
        title="Replenish deactivated SKU",
        entity_type="product",
        entity_id=str(prod.id),
        entity_name=prod.sku,
        explanation="Stale risk alert",
        proposed_action="reorder_stock",
        parameters={"product_id": str(prod.id), "warehouse_id": str(wh.id), "quantity": 10},
        status="APPROVED",
    )
    db_session.add(rec)
    await db_session.commit()
    await db_session.refresh(rec)

    res = client.post(f"/api/v1/recommendations/{rec.id}/execute", json={}, headers=headers)
    assert res.status_code == 400
    assert "inactive" in res.json()["detail"].lower()

    # Re-verify recommendation was NOT marked as EXECUTED
    await db_session.refresh(rec)
    assert rec.status == "APPROVED"

