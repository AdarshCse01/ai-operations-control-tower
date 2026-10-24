"""
Inventory repository with controlled stock receipts, issues, locking, and movement tracking.
"""
from typing import Sequence
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.stock_movement import StockMovement
from app.models.warehouse import Warehouse
from app.repositories.base import BaseRepository


class InventoryRepository(BaseRepository[Inventory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Inventory, session)

    async def get_by_id(self, id: uuid.UUID) -> Inventory | None:
        stmt = (
            select(Inventory)
            .options(selectinload(Inventory.product), selectinload(Inventory.warehouse))
            .where(Inventory.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_product_and_warehouse(
        self, product_id: uuid.UUID, warehouse_id: uuid.UUID
    ) -> Inventory | None:
        stmt = (
            select(Inventory)
            .options(selectinload(Inventory.product), selectinload(Inventory.warehouse))
            .where(
                Inventory.product_id == product_id,
                Inventory.warehouse_id == warehouse_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_filtered(
        self,
        search: str | None = None,
        warehouse_id: uuid.UUID | None = None,
        low_stock_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Inventory], int]:
        stmt = (
            select(Inventory)
            .join(Product, Inventory.product_id == Product.id)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
            .options(selectinload(Inventory.product), selectinload(Inventory.warehouse))
        )
        count_stmt = (
            select(func.count(Inventory.id))
            .join(Product, Inventory.product_id == Product.id)
            .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
        )

        if search:
            term = f"%{search.strip()}%"
            cond = or_(
                Product.name.ilike(term),
                Product.sku.ilike(term),
                Warehouse.name.ilike(term),
                Warehouse.code.ilike(term),
            )
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        if warehouse_id:
            stmt = stmt.where(Inventory.warehouse_id == warehouse_id)
            count_stmt = count_stmt.where(Inventory.warehouse_id == warehouse_id)

        if low_stock_only:
            cond = (Inventory.quantity_on_hand - Inventory.quantity_reserved) <= Inventory.reorder_quantity
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Product.name.asc()).offset(skip).limit(limit)
        items_res = await self.session.execute(stmt)
        return items_res.scalars().all(), total

    async def list_low_stock(self) -> Sequence[Inventory]:
        """Convenience method returning items where available stock is below reorder quantity."""
        items, _ = await self.list_filtered(low_stock_only=True, limit=1000)
        return items

    async def execute_receipt(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity: int,
        reference: str,
        actor_id: uuid.UUID | None,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """
        Atomically receives stock into a warehouse inventory.
        Guarantees idempotency and creates a stock movement record.
        """
        if quantity <= 0:
            raise ValueError("Receipt quantity must be greater than zero")

        # Idempotency check
        if idempotency_key:
            stmt = select(StockMovement).where(StockMovement.idempotency_key == idempotency_key)
            existing_mov = (await self.session.execute(stmt)).scalars().first()
            if existing_mov:
                inv = await self.get_by_product_and_warehouse(product_id, warehouse_id)
                return inv, existing_mov  # type: ignore

        # Lock or create inventory row
        stmt_lock = (
            select(Inventory)
            .where(Inventory.product_id == product_id, Inventory.warehouse_id == warehouse_id)
            .with_for_update()
        )
        inv_res = await self.session.execute(stmt_lock)
        inventory = inv_res.scalars().first()

        if inventory is None:
            inventory = Inventory(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity_on_hand=quantity,
                quantity_reserved=0,
                reorder_quantity=50,
            )
            self.session.add(inventory)
            await self.session.flush()
        else:
            inventory.quantity_on_hand += quantity
            await self.session.flush()

        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            inventory_id=inventory.id,
            movement_type="RECEIPT",
            quantity=quantity,
            reference=reference,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            actor_name=actor_name,
        )
        self.session.add(movement)
        await self.session.flush()

        return inventory, movement

    async def execute_issue(
        self,
        product_id: uuid.UUID,
        warehouse_id: uuid.UUID,
        quantity: int,
        reference: str,
        actor_id: uuid.UUID | None,
        actor_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[Inventory, StockMovement]:
        """
        Atomically issues stock out of inventory, strictly enforcing available stock invariants.
        """
        if quantity <= 0:
            raise ValueError("Issue quantity must be greater than zero")

        # Idempotency check
        if idempotency_key:
            stmt = select(StockMovement).where(StockMovement.idempotency_key == idempotency_key)
            existing_mov = (await self.session.execute(stmt)).scalars().first()
            if existing_mov:
                inv = await self.get_by_product_and_warehouse(product_id, warehouse_id)
                return inv, existing_mov  # type: ignore

        stmt_lock = (
            select(Inventory)
            .where(Inventory.product_id == product_id, Inventory.warehouse_id == warehouse_id)
            .with_for_update()
        )
        inv_res = await self.session.execute(stmt_lock)
        inventory = inv_res.scalars().first()

        if inventory is None:
            raise ValueError("No inventory record exists for this product in the selected warehouse")

        available = inventory.quantity_on_hand - inventory.quantity_reserved
        if available < quantity:
            raise ValueError(
                f"Insufficient available stock for issue. Available: {available}, Requested: {quantity} "
                f"(On-hand: {inventory.quantity_on_hand}, Reserved: {inventory.quantity_reserved})"
            )

        inventory.quantity_on_hand -= quantity
        await self.session.flush()

        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            inventory_id=inventory.id,
            movement_type="ISSUE",
            quantity=quantity,
            reference=reference,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
            actor_name=actor_name,
        )
        self.session.add(movement)
        await self.session.flush()

        return inventory, movement

    async def list_movements(
        self,
        product_id: uuid.UUID | None = None,
        warehouse_id: uuid.UUID | None = None,
        movement_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[StockMovement], int]:
        stmt = (
            select(StockMovement)
            .options(
                selectinload(StockMovement.product),
                selectinload(StockMovement.warehouse),
            )
        )
        count_stmt = select(func.count(StockMovement.id))

        if product_id:
            stmt = stmt.where(StockMovement.product_id == product_id)
            count_stmt = count_stmt.where(StockMovement.product_id == product_id)

        if warehouse_id:
            stmt = stmt.where(StockMovement.warehouse_id == warehouse_id)
            count_stmt = count_stmt.where(StockMovement.warehouse_id == warehouse_id)

        if movement_type:
            stmt = stmt.where(StockMovement.movement_type == movement_type)
            count_stmt = count_stmt.where(StockMovement.movement_type == movement_type)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(StockMovement.created_at.desc()).offset(skip).limit(limit)
        items_res = await self.session.execute(stmt)
        return items_res.scalars().all(), total
