"""
Warehouse database model representing storage facilities and fulfillment centers.
"""
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, CheckConstraint, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.inventory import Inventory
    from app.models.order import Order


class Warehouse(Base, TimestampMixin):
    __tablename__ = "warehouses"
    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_warehouse_capacity"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    location: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    capacity: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Relationships
    inventories: Mapped[list["Inventory"]] = relationship(
        "Inventory",
        back_populates="warehouse",
        cascade="all, delete-orphan",
    )
    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="warehouse",
    )

    def __repr__(self) -> str:
        return f"<Warehouse code={self.code!r} name={self.name!r} location={self.location!r}>"
