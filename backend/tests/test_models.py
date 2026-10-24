"""Tests for model creation, constraints, relationships, and data integrity."""
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import (
    User,
    Supplier,
    Product,
    Warehouse,
    Inventory,
    Order,
    OrderItem,
    AuditLog,
)


@pytest.mark.asyncio
async def test_create_user(db_session: AsyncSession):
    user = User(
        email="operator1@example.com",
        hashed_password="secure-hashed-pw",
        full_name="Alex Operator",
        role="operator",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()

    assert isinstance(user.id, uuid.UUID)
    assert user.role == "operator"
    assert user.is_active is True
    assert user.created_at is not None
    assert user.updated_at is not None


@pytest.mark.asyncio
async def test_user_unique_email_constraint(db_session: AsyncSession):
    u1 = User(
        email="dup@example.com",
        hashed_password="pw1",
        full_name="User 1",
    )
    db_session.add(u1)
    await db_session.flush()

    u2 = User(
        email="dup@example.com",
        hashed_password="pw2",
        full_name="User 2",
    )
    db_session.add(u2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_supplier_and_product_relationship(db_session: AsyncSession):
    supplier = Supplier(
        name="Global Logistics Hub",
        code=f"SUP-{uuid.uuid4().hex[:6]}",
        lead_time_days=5,
        reliability_score=Decimal("0.98"),
    )
    db_session.add(supplier)
    await db_session.flush()

    product = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        name="Precision Sensor X1",
        category="Sensors",
        unit_price=Decimal("1250.50"),
        unit_cost=Decimal("800.00"),
        reorder_point=15,
        safety_stock=5,
        supplier_id=supplier.id,
    )
    db_session.add(product)
    await db_session.flush()

    assert isinstance(product.id, uuid.UUID)
    assert product.unit_price == Decimal("1250.50")
    assert isinstance(product.unit_price, Decimal)
    assert product.supplier_id == supplier.id


@pytest.mark.asyncio
async def test_warehouse_and_inventory(db_session: AsyncSession):
    wh = Warehouse(
        code=f"WH-{uuid.uuid4().hex[:6]}",
        name="Central DC",
        location="Frankfurt, Germany",
        capacity=50000,
    )
    prod = Product(
        sku=f"SKU-{uuid.uuid4().hex[:6]}",
        name="Industrial Motor M4",
        category="Motors",
        unit_price=Decimal("450.00"),
        unit_cost=Decimal("300.00"),
    )
    db_session.add_all([wh, prod])
    await db_session.flush()

    inv = Inventory(
        product_id=prod.id,
        warehouse_id=wh.id,
        quantity_on_hand=100,
        quantity_reserved=20,
        reorder_quantity=30,
    )
    db_session.add(inv)
    await db_session.flush()

    assert inv.available_quantity == 80
    assert inv.product_id == prod.id
    assert inv.warehouse_id == wh.id


@pytest.mark.asyncio
async def test_inventory_unique_product_warehouse_constraint(db_session: AsyncSession):
    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6]}", name="DC 1", location="Loc 1", capacity=1000)
    prod = Product(sku=f"SKU-{uuid.uuid4().hex[:6]}", name="P1", category="C1", unit_price=Decimal("10"), unit_cost=Decimal("5"))
    db_session.add_all([wh, prod])
    await db_session.flush()

    i1 = Inventory(product_id=prod.id, warehouse_id=wh.id, quantity_on_hand=10, quantity_reserved=0)
    db_session.add(i1)
    await db_session.flush()

    i2 = Inventory(product_id=prod.id, warehouse_id=wh.id, quantity_on_hand=5, quantity_reserved=0)
    db_session.add(i2)
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_order_and_order_items(db_session: AsyncSession):
    user = User(email=f"user-{uuid.uuid4().hex[:6]}@example.com", hashed_password="pw", full_name="Customer Rep")
    wh = Warehouse(code=f"WH-{uuid.uuid4().hex[:6]}", name="DC", location="Loc", capacity=1000)
    prod = Product(sku=f"SKU-{uuid.uuid4().hex[:6]}", name="Part A", category="Parts", unit_price=Decimal("75.00"), unit_cost=Decimal("50.00"))
    db_session.add_all([user, wh, prod])
    await db_session.flush()

    order = Order(
        order_number=f"ORD-{uuid.uuid4().hex[:8]}",
        customer_name="Starlight Industries",
        status="PENDING",
        priority="HIGH",
        total_amount=Decimal("150.00"),
        warehouse_id=wh.id,
        created_by_user_id=user.id,
    )
    db_session.add(order)
    await db_session.flush()

    item = OrderItem(
        order_id=order.id,
        product_id=prod.id,
        quantity=2,
        unit_price=Decimal("75.00"),
        subtotal=Decimal("150.00"),
    )
    db_session.add(item)
    await db_session.flush()

    assert item.order_id == order.id
    assert item.product_id == prod.id
    assert item.quantity == 2
    assert item.subtotal == Decimal("150.00")


@pytest.mark.asyncio
async def test_audit_log_record(db_session: AsyncSession):
    log = AuditLog(
        entity_type="recommendation",
        entity_id="REC-001",
        action="recommendation.approved",
        actor_name="demo-operator",
        payload={"decision": "approved", "comment": "Expedite freight"},
        comment="Human approval recorded from control tower",
    )
    db_session.add(log)
    await db_session.flush()

    assert isinstance(log.id, uuid.UUID)
    assert log.entity_type == "recommendation"
    assert log.action == "recommendation.approved"
    assert log.payload["decision"] == "approved"
    assert log.created_at is not None
