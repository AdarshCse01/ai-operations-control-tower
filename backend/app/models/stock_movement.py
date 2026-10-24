"""
StockMovement model tracking controlled inventory receipts, issues, adjustments, and reservations.
"""
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID

if TYPE_CHECKING:
    from app.models.product import Product
    from app.models.warehouse import Warehouse
    from app.models.inventory import Inventory
    from app.models.user import User


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        CheckConstraint(
            "movement_type IN ('RECEIPT', 'ISSUE', 'RESERVATION', 'RELEASE', 'ADJUSTMENT')",
            name="ck_stock_movement_type",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_movement_quantity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    inventory_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("inventories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    movement_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    reference: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="system",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product")
    warehouse: Mapped["Warehouse"] = relationship("Warehouse")
    inventory: Mapped["Inventory | None"] = relationship("Inventory")
    actor: Mapped["User | None"] = relationship("User")

    @property
    def product_sku(self) -> str | None:
        return self.product.sku if self.product else None

    @property
    def warehouse_code(self) -> str | None:
        return self.warehouse.code if self.warehouse else None

    def __repr__(self) -> str:
        return (
            f"<StockMovement type={self.movement_type} qty={self.quantity} "
            f"prod={self.product_id} wh={self.warehouse_id} ref={self.reference!r}>"
        )
