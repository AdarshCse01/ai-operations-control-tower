"""Warehouse repository with code lookup, filtering, and deletion guards."""
from typing import Sequence
import uuid
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import Inventory
from app.models.warehouse import Warehouse
from app.repositories.base import BaseRepository


class WarehouseRepository(BaseRepository[Warehouse]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Warehouse, session)

    async def get_by_code(self, code: str) -> Warehouse | None:
        stmt = select(Warehouse).where(func.lower(Warehouse.code) == code.strip().lower())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_filtered(
        self,
        search: str | None = None,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[Sequence[Warehouse], int]:
        stmt = select(Warehouse)
        count_stmt = select(func.count(Warehouse.id))

        if search:
            term = f"%{search.strip()}%"
            cond = or_(Warehouse.name.ilike(term), Warehouse.code.ilike(term), Warehouse.location.ilike(term))
            stmt = stmt.where(cond)
            count_stmt = count_stmt.where(cond)

        if is_active is not None:
            stmt = stmt.where(Warehouse.is_active == is_active)
            count_stmt = count_stmt.where(Warehouse.is_active == is_active)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Warehouse.code.asc()).offset(skip).limit(limit)
        items_res = await self.session.execute(stmt)
        return items_res.scalars().all(), total

    async def has_active_inventory(self, warehouse_id: uuid.UUID) -> bool:
        """Checks if warehouse holds any active stock on hand."""
        stmt = select(func.count(Inventory.id)).where(
            Inventory.warehouse_id == warehouse_id,
            Inventory.quantity_on_hand > 0,
        )
        result = await self.session.execute(stmt)
        return (result.scalar_one() or 0) > 0
