"""Pydantic schemas for Product catalog operations."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    sku: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str = Field(min_length=1, max_length=100)
    unit_price: Decimal = Field(ge=Decimal("0.00"))
    unit_cost: Decimal = Field(ge=Decimal("0.00"))
    reorder_point: int = Field(default=10, ge=0)
    safety_stock: int = Field(default=5, ge=0)
    supplier_id: UUID | None = None
    is_active: bool = True


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    sku: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=100)
    unit_price: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    unit_cost: Decimal | None = Field(default=None, ge=Decimal("0.00"))
    reorder_point: int | None = Field(default=None, ge=0)
    safety_stock: int | None = Field(default=None, ge=0)
    supplier_id: UUID | None = None
    is_active: bool | None = None


class ProductRead(ProductBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    supplier_name: str | None = None
    supplier_code: str | None = None
    model_config = ConfigDict(from_attributes=True)
