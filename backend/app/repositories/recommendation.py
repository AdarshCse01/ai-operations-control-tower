"""
Recommendation repository providing filtered lookups, entity deduplication checks, and status updates.
"""
from typing import Sequence
import uuid
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.recommendation import Recommendation
from app.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository[Recommendation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Recommendation, session)

    async def get_pending_by_entity(
        self, recommendation_type: str, entity_id: str
    ) -> Recommendation | None:
        """Finds active PENDING recommendation for the given type and entity to prevent duplicates."""
        stmt = select(Recommendation).where(
            Recommendation.recommendation_type == recommendation_type,
            Recommendation.entity_id == entity_id,
            Recommendation.status == "PENDING",
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_filtered(
        self,
        status: str | None = None,
        priority: str | None = None,
        entity_type: str | None = None,
        rec_type: str | None = None,
        skip: int = 0,
        limit: int = 50,
        offset: int | None = None,
    ) -> tuple[Sequence[Recommendation], int]:
        actual_skip = offset if offset is not None else skip
        stmt = select(Recommendation)
        count_stmt = select(func.count(Recommendation.id))

        if status:
            stmt = stmt.where(Recommendation.status == status.strip().upper())
            count_stmt = count_stmt.where(Recommendation.status == status.strip().upper())

        if priority:
            stmt = stmt.where(Recommendation.priority == priority.strip().upper())
            count_stmt = count_stmt.where(Recommendation.priority == priority.strip().upper())

        if entity_type:
            stmt = stmt.where(Recommendation.entity_type == entity_type.strip().lower())
            count_stmt = count_stmt.where(Recommendation.entity_type == entity_type.strip().lower())

        if rec_type:
            stmt = stmt.where(Recommendation.recommendation_type == rec_type.strip().upper())
            count_stmt = count_stmt.where(Recommendation.recommendation_type == rec_type.strip().upper())

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        # Order by created_at desc
        stmt = stmt.order_by(Recommendation.created_at.desc()).offset(actual_skip).limit(limit)
        items_res = await self.session.execute(stmt)
        return items_res.scalars().all(), total

