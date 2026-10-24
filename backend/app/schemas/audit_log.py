"""Pydantic schemas for AuditLog records."""
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AuditLogBase(BaseModel):
    entity_type: str = Field(min_length=1, max_length=100)
    entity_id: str = Field(min_length=1, max_length=255)
    action: str = Field(min_length=1, max_length=100)
    actor_id: UUID | None = None
    actor_name: str = Field(default="system", min_length=1, max_length=255)
    payload: dict[str, Any] | list[Any] | None = None
    comment: str | None = None


class AuditLogCreate(AuditLogBase):
    pass


class AuditLogRead(AuditLogBase):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
