"""Supplier repository with filtering, code lookup, and deletion safety checks."""
from typing import Sequence
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.product import Product
from app.models.supplier import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Supplier, session)

    async def get_by_code(self, code: str) -> Supplier | None:
        stmt = select(Supplier).where(func.lower(Supplier.code) == code.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_filtered(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Supplier], int]:
        stmt = select(Supplier)
        count_stmt = select(func.count(Supplier.id))

        if search:
            term = f"%{search.strip()}%"
            filter_cond = or_(Supplier.name.ilike(term), Supplier.code.ilike(term))
            stmt = stmt.where(filter_cond)
            count_stmt = count_stmt.where(filter_cond)

        if is_active is not None:
            stmt = stmt.where(Supplier.is_active == is_active)
            count_stmt = count_stmt.where(Supplier.is_active == is_active)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Supplier.name.asc()).offset(skip).limit(limit)
        items_res = await self.session.execute(stmt)
        return items_res.scalars().all(), total

    async def has_associated_products(self, supplier_id: uuid.UUID) -> bool:
        """Checks if any products reference this supplier."""
        stmt = select(func.count(Product.id)).where(Product.supplier_id == supplier_id)
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0
