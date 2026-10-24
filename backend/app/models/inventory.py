"""
Inventory database model tracking stock levels, allocations, and reorder triggers per warehouse.
"""
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.warehouse import Warehouse


class Inventory(Base, TimestampMixin):
    __tablename__ = "inventories"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id", name="uq_inventory_product_warehouse"),
        CheckConstraint("quantity_on_hand >= 0", name="ck_inventory_qty_on_hand"),
        CheckConstraint("quantity_reserved >= 0", name="ck_inventory_qty_reserved"),
        CheckConstraint(
            "quantity_reserved <= quantity_on_hand",
            name="ck_inventory_reserved_lte_on_hand",
        ),
        CheckConstraint("reorder_quantity >= 0", name="ck_inventory_reorder_qty"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity_on_hand: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    quantity_reserved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    reorder_quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
    )

    # Relationships
    product: Mapped["Product"] = relationship(
        "Product",
        back_populates="inventories",
    )
    warehouse: Mapped["Warehouse"] = relationship(
        "Warehouse",
        back_populates="inventories",
    )

    @property
    def available_quantity(self) -> int:
        """Calculates unreserved stock available for fulfillment."""
        return self.quantity_on_hand - self.quantity_reserved

    @property
    def product_sku(self) -> str | None:
        return self.product.sku if self.product else None

    @property
    def product_name(self) -> str | None:
        return self.product.name if self.product else None

    @property
    def product_category(self) -> str | None:
        return self.product.category if self.product else None

    @property
    def warehouse_code(self) -> str | None:
        return self.warehouse.code if self.warehouse else None

    @property
    def warehouse_name(self) -> str | None:
        return self.warehouse.name if self.warehouse else None

    def __repr__(self) -> str:
        return (
            f"<Inventory product_id={self.product_id} "
            f"warehouse_id={self.warehouse_id} "
            f"on_hand={self.quantity_on_hand} reserved={self.quantity_reserved}>"
        )
