"""
Recommendation database model capturing automated operational proposals, human decisions, and execution results.
"""
from datetime import datetime
from typing import Any, TYPE_CHECKING
import uuid
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, GUID, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED')",
            name="ck_recommendation_status",
        ),
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_recommendation_priority",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4,
    )
    recommendation_type: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    priority: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="MEDIUM",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    entity_id: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    entity_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    explanation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    proposed_action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    parameters: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )

    # Human Approval Details
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    decided_by_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    decision_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Execution Details
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    execution_result: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationship
    decided_by: Mapped["User | None"] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<Recommendation id={self.id} type={self.recommendation_type!r} "
            f"entity={self.entity_type}:{self.entity_id} status={self.status!r}>"
        )
