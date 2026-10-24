"""Pydantic schemas for Orders, Order Items, and Status Transitions."""
from datetime import datetime
from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class OrderItemCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(gt=0, description="Positive unit quantity to order")


class OrderItemRead(BaseModel):
    id: UUID
    order_id: UUID
    product_id: UUID
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    created_at: datetime
    product_sku: str | None = None
    product_name: str | None = None
    model_config = ConfigDict(from_attributes=True)


class OrderCreate(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    priority: str = Field(default="NORMAL", pattern="^(LOW|NORMAL|HIGH|CRITICAL)$")
    warehouse_id: UUID | None = None
    expected_delivery_date: datetime | None = None
    items: list[OrderItemCreate] = Field(min_length=1, description="Order must contain at least one line item")


class OrderStatusUpdate(BaseModel):
    status: str = Field(pattern="^(PENDING|PROCESSING|SHIPPED|DELIVERED|CANCELLED)$")
    comment: str = Field(default="", max_length=500)


class OrderUpdate(BaseModel):
    customer_name: str | None = Field(default=None, min_length=1, max_length=255)
    priority: str | None = Field(default=None, pattern="^(LOW|NORMAL|HIGH|CRITICAL)$")
    warehouse_id: UUID | None = None
    expected_delivery_date: datetime | None = None


class OrderRead(BaseModel):
    id: UUID
    order_number: str
    customer_name: str
    status: str
    priority: str
    total_amount: Decimal
    warehouse_id: UUID | None = None
    warehouse_name: str | None = None
    warehouse_code: str | None = None
    created_by_user_id: UUID | None = None
    created_by_name: str | None = None
    expected_delivery_date: datetime | None = None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead] = []
    model_config = ConfigDict(from_attributes=True)
