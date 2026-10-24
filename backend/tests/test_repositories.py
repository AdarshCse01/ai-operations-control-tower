"""Tests for repository CRUD and domain lookup methods."""
from decimal import Decimal
import uuid
import pytest
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
from app.repositories import (
    UserRepository,
    SupplierRepository,
    ProductRepository,
    WarehouseRepository,
    InventoryRepository,
    OrderRepository,
    OrderItemRepository,
    AuditLogRepository,
)


@pytest.mark.asyncio
async def test_user_repository(db_session: AsyncSession):
    repo = UserRepository(db_session)
    user = User(
        email="operator_repo@example.com",
        hashed_password="pw",
        full_name="Ops Lead",
        role="operator",
    )
    created = await repo.create(user)
    assert created.id is not None

    found = await repo.get_by_email("operator_repo@example.com")
    assert found is not None
    assert found.full_name == "Ops Lead"

    all_users = await repo.list_all()
    assert any(u.email == "operator_repo@example.com" for u in all_users)

    updated = await repo.update(found, {"full_name": "Ops Lead Senior"})
    assert updated.full_name == "Ops Lead Senior"

    await repo.delete(found)
    assert await repo.get_by_email("operator_repo@example.com") is None


@pytest.mark.asyncio
async def test_supplier_and_product_repository(db_session: AsyncSession):
    sup_repo = SupplierRepository(db_session)
    prod_repo = ProductRepository(db_session)

    code = f"SUP-{uuid.uuid4().hex[:6]}"
    supplier = await sup_repo.create(
        Supplier(name="Apex Materials", code=code, lead_time_days=3, reliability_score=Decimal("0.99"))
    )
    assert (await sup_repo.get_by_code(code)) is not None

    sku = f"SKU-{uuid.uuid4().hex[:6]}"
    product = await prod_repo.create(
        Product(
            sku=sku,
            name="Apex Carbon Frame",
            category="Frames",
            unit_price=Decimal("500.00"),
            unit_cost=Decimal("350.00"),
            supplier_id=supplier.id,
        )
    )
    assert (await prod_repo.get_by_sku(sku)) is not None
    frames = await prod_repo.list_by_category("Frames")
    assert any(p.sku == sku for p in frames)


@pytest.mark.asyncio
async def test_inventory_repository(db_session: AsyncSession):
    wh_repo = WarehouseRepository(db_session)
    prod_repo = ProductRepository(db_session)
    inv_repo = InventoryRepository(db_session)

    wh = await wh_repo.create(
        Warehouse(code=f"WH-{uuid.uuid4().hex[:6]}", name="South Hub", location="Austin, TX", capacity=25000)
    )
    prod = await prod_repo.create(
        Product(
            sku=f"SKU-{uuid.uuid4().hex[:6]}",
            name="Relay Switch",
            category="Electronics",
            unit_price=Decimal("25.00"),
            unit_cost=Decimal("15.00"),
        )
    )

    inv = await inv_repo.create(
        Inventory(
            product_id=prod.id,
            warehouse_id=wh.id,
            quantity_on_hand=15,
            quantity_reserved=5,
            reorder_quantity=20,  # Available (10) <= reorder_quantity (20) -> low stock
        )
    )

    found = await inv_repo.get_by_product_and_warehouse(prod.id, wh.id)
    assert found is not None
    assert found.id == inv.id

    low_stock_items = await inv_repo.list_low_stock()
    assert any(item.id == inv.id for item in low_stock_items)


@pytest.mark.asyncio
async def test_order_and_items_repository(db_session: AsyncSession):
    order_repo = OrderRepository(db_session)
    item_repo = OrderItemRepository(db_session)
    prod_repo = ProductRepository(db_session)

    prod = await prod_repo.create(
        Product(
            sku=f"SKU-{uuid.uuid4().hex[:6]}",
            name="Controller Board",
            category="Electronics",
            unit_price=Decimal("120.00"),
            unit_cost=Decimal("80.00"),
        )
    )

    ord_num = f"ORD-{uuid.uuid4().hex[:8]}"
    order = await order_repo.create(
        Order(
            order_number=ord_num,
            customer_name="Nordic Energy",
            status="PENDING",
            priority="CRITICAL",
            total_amount=Decimal("240.00"),
        )
    )

    item = await item_repo.create(
        OrderItem(
            order_id=order.id,
            product_id=prod.id,
            quantity=2,
            unit_price=Decimal("120.00"),
            subtotal=Decimal("240.00"),
        )
    )

    loaded_order = await order_repo.get_by_order_number(ord_num)
    assert loaded_order is not None
    assert len(loaded_order.items) == 1
    assert loaded_order.items[0].id == item.id

    critical_orders = await order_repo.list_by_status("PENDING")
    assert any(o.order_number == ord_num for o in critical_orders)


@pytest.mark.asyncio
async def test_audit_log_repository(db_session: AsyncSession):
    repo = AuditLogRepository(db_session)
    entity_id = f"REC-{uuid.uuid4().hex[:6]}"

    log = await repo.create(
        AuditLog(
            entity_type="recommendation",
            entity_id=entity_id,
            action="recommendation.approved",
            actor_name="supervisor",
            payload={"approved": True},
        )
    )

    records = await repo.list_by_entity("recommendation", entity_id)
    assert len(records) >= 1
    assert records[0].id == log.id
