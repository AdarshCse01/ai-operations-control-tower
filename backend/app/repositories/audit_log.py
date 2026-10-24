"""AuditLog repository with entity history and actor filtering."""
from typing import Any, Sequence
import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit_log import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AuditLog, session)

    def _sanitize(self, val: Any) -> Any:
        from decimal import Decimal
        import uuid
        from datetime import datetime, date
        if isinstance(val, (Decimal, uuid.UUID, datetime, date)):
            return str(val)
        if isinstance(val, dict):
            return {k: self._sanitize(v) for k, v in val.items()}
        if isinstance(val, (list, tuple, set)):
            return [self._sanitize(v) for v in val]
        return val

    async def create(self, obj: AuditLog) -> AuditLog:
        if obj.payload and isinstance(obj.payload, dict):
            obj.payload = self._sanitize(obj.payload)
        return await super().create(obj)

    async def list_by_entity(
        self, entity_type: str, entity_id: str, limit: int = 100
    ) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_actor(
        self, actor_id: uuid.UUID, limit: int = 100
    ) -> Sequence[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
