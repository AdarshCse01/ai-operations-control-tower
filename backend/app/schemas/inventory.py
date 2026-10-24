"""Pydantic schemas for Inventory management and controlled Stock Movements."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class InventoryBase(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    quantity_on_hand: int = Field(default=0, ge=0)
    quantity_reserved: int = Field(default=0, ge=0)
    reorder_quantity: int = Field(default=50, ge=0)

    @model_validator(mode="after")
    def check_reserved_lte_on_hand(self):
        if self.quantity_reserved > self.quantity_on_hand:
            raise ValueError("quantity_reserved cannot exceed quantity_on_hand")
        return self


class InventoryCreate(InventoryBase):
    pass


class InventoryUpdate(BaseModel):
    reorder_quantity: int | None = Field(default=None, ge=0)


class InventoryRead(InventoryBase):
    id: UUID
    available_quantity: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class InventoryDetailRead(InventoryRead):
    product_sku: str | None = None
    product_name: str | None = None
    product_category: str | None = None
    warehouse_code: str | None = None
    warehouse_name: str | None = None


# Stock Movement Schemas
class StockReceiptRequest(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    quantity: int = Field(gt=0, description="Quantity of items received into stock")
    reference: str = Field(default="", max_length=255, description="PO number, supplier invoice, or receipt note")
    idempotency_key: str | None = Field(default=None, max_length=100, description="Unique key preventing duplicate receipt submissions")


class StockIssueRequest(BaseModel):
    product_id: UUID
    warehouse_id: UUID
    quantity: int = Field(gt=0, description="Quantity of items issued out of stock")
    reference: str = Field(default="", max_length=255, description="Order dispatch, transfer manifest, or issue justification")
    idempotency_key: str | None = Field(default=None, max_length=100, description="Unique key preventing duplicate issue submissions")


class StockMovementRead(BaseModel):
    id: UUID
    product_id: UUID
    warehouse_id: UUID
    inventory_id: UUID | None = None
    movement_type: str
    quantity: int
    reference: str
    idempotency_key: str | None = None
    actor_id: UUID | None = None
    actor_name: str
    created_at: datetime
    product_sku: str | None = None
    warehouse_code: str | None = None
    model_config = ConfigDict(from_attributes=True)
