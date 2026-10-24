"""Product repository with SKU lookup, multi-field filtering, sorting, and deletion guards."""
from typing import Sequence
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import Inventory
from app.models.order_item import OrderItem
from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Product, session)

    async def get_by_sku(self, sku: str) -> Product | None:
        stmt = (
            select(Product)
            .options(selectinload(Product.supplier))
            .where(func.lower(Product.sku) == sku.strip().lower())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_by_id(self, id: uuid.UUID) -> Product | None:
        stmt = (
            select(Product)
            .options(selectinload(Product.supplier))
            .where(Product.id == id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_category(self, category: str) -> Sequence[Product]:
        stmt = select(Product).where(Product.category == category)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_filtered(
        self,
        search: str | None = None,
        category: str | None = None,
        supplier_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        sort_by: str = "name",
        sort_dir: str = "asc",
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Product], int]:
        stmt = select(Product).options(selectinload(Product.supplier))
        count_stmt = select(func.count(Product.id))

        if search:
            term = f"%{search.strip()}%"
            cond = or_(Product.name.ilike(term), Product.sku.ilike(term), Product.category.ilike(term))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        if category:
            stmt = stmt.where(Product.category == category)
            count_stmt = count_stmt.where(Product.category == category)

        if supplier_id:
            stmt = stmt.where(Product.supplier_id == supplier_id)
            count_stmt = count_stmt.where(Product.supplier_id == supplier_id)

        if is_active is not None:
            stmt = stmt.where(Product.is_active == is_active)
            count_stmt = count_stmt.where(Product.is_active == is_active)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        # Sorting
        sort_col = Product.name
        if sort_by == "sku":
            sort_col = Product.sku
        elif sort_by == "unit_price":
            sort_col = Product.unit_price
        elif sort_by == "created_at":
            sort_col = Product.created_at

        stmt = stmt.order_by(sort_col.desc() if sort_dir.lower() == "desc" else sort_col.asc())
        stmt = stmt.offset(skip).limit(limit)

        items_res = await self.session.execute(stmt)
        return items_res.scalars().all(), total

    async def has_active_inventory_or_orders(self, product_id: uuid.UUID) -> bool:
        """Checks if product has active inventory quantity or order line items."""
        inv_stmt = select(func.count(Inventory.id)).where(
            Inventory.product_id == product_id,
            Inventory.quantity_on_hand > 0,
        )
        inv_count = (await self.session.execute(inv_stmt)).scalar_one()
        if inv_count > 0:
            return True

        order_stmt = select(func.count(OrderItem.id)).where(OrderItem.product_id == product_id)
        order_count = (await self.session.execute(order_stmt)).scalar_one()
        return order_count > 0
