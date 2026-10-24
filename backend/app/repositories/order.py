"""
Order repository with transaction-safe multi-item order creation,
backend price calculation, status state machine, and filtering.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.models.user import User
from app.repositories.base import BaseRepository

VALID_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "PENDING": {"PROCESSING", "CANCELLED"},
    "PROCESSING": {"SHIPPED", "CANCELLED"},
    "SHIPPED": {"DELIVERED", "CANCELLED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Order, session)

    async def get_by_id(self, id: uuid.UUID) -> Order | None:
        stmt = (
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.warehouse),
                selectinload(Order.created_by),
            )
            .where(Order.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_order_number(self, order_number: str) -> Order | None:
        stmt = (
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.warehouse),
                selectinload(Order.created_by),
            )
            .where(func.lower(Order.order_number) == order_number.strip().lower())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_filtered(
        self,
        search: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        warehouse_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Order], int]:
        stmt = (
            select(Order)
            .options(
                selectinload(Order.items).selectinload(OrderItem.product),
                selectinload(Order.warehouse),
                selectinload(Order.created_by),
            )
        )
        count_stmt = select(func.count(Order.id))

        if search:
            term = f"%{search.strip()}%"
            cond = or_(Order.order_number.ilike(term), Order.customer_name.ilike(term))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        if status:
            stmt = stmt.where(Order.status == status.strip().upper())
            count_stmt = count_stmt.where(Order.status == status.strip().upper())

        if priority:
            stmt = stmt.where(Order.priority == priority.strip().upper())
            count_stmt = count_stmt.where(Order.priority == priority.strip().upper())

        if warehouse_id:
            stmt = stmt.where(Order.warehouse_id == warehouse_id)
            count_stmt = count_stmt.where(Order.warehouse_id == warehouse_id)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Order.created_at.desc()).offset(skip).limit(limit)
        items_res = await self.session.execute(stmt)
        return items_res.scalars().all(), total

    async def list_by_status(self, status: str) -> Sequence[Order]:
        """Convenience method returning orders by status."""
        items, _ = await self.list_filtered(status=status, limit=1000)
        return items

    async def create_order_with_items(
        self,
        customer_name: str,
        warehouse_id: uuid.UUID | None,
        priority: str,
        expected_delivery_date: datetime | None,
        items_data: list[tuple[Product, int]],
        created_by_user_id: uuid.UUID | None,
    ) -> Order:
        """
        Creates an order and line items within a transaction.
        Calculates all line prices and total amount strictly from backend product records.
        """
        if not items_data:
            raise ValueError("An order must contain at least one line item")

        now = datetime.now(timezone.utc)
        order_number = f"ORD-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

        total_amount = Decimal("0.00")
        order_items: list[OrderItem] = []

        order = Order(
            order_number=order_number,
            customer_name=customer_name,
            status="PENDING",
            priority=priority.upper(),
            total_amount=Decimal("0.00"),
            warehouse_id=warehouse_id,
            created_by_user_id=created_by_user_id,
            expected_delivery_date=expected_delivery_date,
        )
        self.session.add(order)
        await self.session.flush()

        for product, quantity in items_data:
            if quantity <= 0:
                raise ValueError(f"Quantity for product {product.sku} must be greater than zero")
            unit_price = Decimal(str(product.unit_price))
            subtotal = unit_price * quantity
            total_amount += subtotal

            item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price=unit_price,
                subtotal=subtotal,
            )
            order_items.append(item)
            self.session.add(item)

        order.total_amount = total_amount
        await self.session.flush()

        # Reload with relationships
        return await self.get_by_id(order.id)  # type: ignore

    def validate_and_update_status(self, order: Order, new_status: str) -> None:
        """Enforces order lifecycle state transitions."""
        target_status = new_status.strip().upper()
        if target_status == order.status:
            return

        allowed = VALID_STATUS_TRANSITIONS.get(order.status, set())
        if target_status not in allowed:
            raise ValueError(
                f"Invalid status transition from {order.status} to {target_status}. "
                f"Permitted next states: {sorted(list(allowed)) if allowed else 'none (terminal state)'}"
            )

        order.status = target_status


class OrderItemRepository(BaseRepository[OrderItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OrderItem, session)

    async def list_by_order_id(self, order_id: uuid.UUID) -> Sequence[OrderItem]:
        stmt = (
            select(OrderItem)
            .options(selectinload(OrderItem.product))
            .where(OrderItem.order_id == order_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
