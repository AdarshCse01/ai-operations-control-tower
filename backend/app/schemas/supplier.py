"""Pydantic schemas for Supplier operations."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class SupplierBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    lead_time_days: int = Field(default=7, ge=0)
    reliability_score: Decimal = Field(default=Decimal("0.95"), ge=Decimal("0.00"), le=Decimal("1.00"))
    is_active: bool = True


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    lead_time_days: int | None = Field(default=None, ge=0)
    reliability_score: Decimal | None = Field(default=None, ge=Decimal("0.00"), le=Decimal("1.00"))
    is_active: bool | None = None


class SupplierRead(SupplierBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
