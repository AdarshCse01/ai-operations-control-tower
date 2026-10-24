"""Generic async repository providing standard CRUD operations."""
from typing import Any, Generic, Sequence, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Lightweight async repository implementation.
    Operates on an injected AsyncSession.
    """

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get_by_id(self, id: Any) -> ModelType | None:
        """Fetch a single record by primary key."""
        return await self.session.get(self.model, id)

    async def list_all(self, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Fetch a paginated list of records."""
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def create(self, obj: ModelType) -> ModelType:
        """Persist a new model instance."""
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelType, updates: dict[str, Any] | None = None) -> ModelType:
        """Apply attributes to an existing instance and flush."""
        if updates:
            for key, value in updates.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj_or_id: ModelType | Any) -> None:
        """Remove a model instance and flush."""
        if isinstance(obj_or_id, self.model):
            await self.session.delete(obj_or_id)
        else:
            obj = await self.get_by_id(obj_or_id)
            if obj is not None:
                await self.session.delete(obj)
        await self.session.flush()
