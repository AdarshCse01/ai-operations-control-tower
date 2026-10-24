"""
Supplier database model representing supply chain vendors and reliability metrics.
"""
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid
from sqlalchemy import Boolean, CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.product import Product


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    __table_args__ = (
        CheckConstraint("lead_time_days >= 0", name="ck_supplier_lead_time_days"),
        CheckConstraint(
            "reliability_score >= 0.00 AND reliability_score <= 1.00",
            name="ck_supplier_reliability_score",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
    )
    contact_email: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    lead_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
    )
    reliability_score: Mapped[Decimal] = mapped_column(
        Numeric(precision=3, scale=2),
        nullable=False,
        default=Decimal("0.95"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Relationships
    products: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="supplier",
    )

    def __repr__(self) -> str:
        return f"<Supplier code={self.code!r} name={self.name!r} score={self.reliability_score}>"
