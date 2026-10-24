"""
Product catalog model with pricing, inventory thresholds, and supplier association.
"""
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.supplier import Supplier
    from app.models.inventory import Inventory
    from app.models.order_item import OrderItem


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="ck_product_unit_price"),
        CheckConstraint("unit_cost >= 0", name="ck_product_unit_cost"),
        CheckConstraint("reorder_point >= 0", name="ck_product_reorder_point"),
        CheckConstraint("safety_stock >= 0", name="ck_product_safety_stock"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    sku: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    category: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )
    reorder_point: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )
    safety_stock: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("suppliers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Relationships
    supplier: Mapped["Supplier | None"] = relationship(
        "Supplier",
        back_populates="products",
    )
    inventories: Mapped[list["Inventory"]] = relationship(
        "Inventory",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    order_items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="product",
    )

    @property
    def supplier_name(self) -> str | None:
        return self.supplier.name if self.supplier else None

    @property
    def supplier_code(self) -> str | None:
        return self.supplier.code if self.supplier else None

    def __repr__(self) -> str:
        return f"<Product sku={self.sku!r} name={self.name!r} price={self.unit_price}>"
