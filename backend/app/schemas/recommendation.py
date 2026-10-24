"""
Pydantic schemas for Recommendation lifecycle: generation, review, human approval, and execution.
"""
from datetime import datetime
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class RecommendationRead(BaseModel):
    id: UUID
    recommendation_type: str
    priority: str
    title: str
    entity_type: str
    entity_id: str
    entity_name: str
    evidence: dict[str, Any] | None = None
    explanation: str
    proposed_action: str
    parameters: dict[str, Any] | None = None
    status: str
    decided_at: datetime | None = None
    decided_by_user_id: UUID | None = None
    decided_by_name: str | None = None
    decision_comment: str | None = None
    executed_at: datetime | None = None
    execution_result: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RecommendationApprovalRequest(BaseModel):
    approved: bool
    comment: str = Field(default="", max_length=500, description="Operator rationale for approval or rejection")


class RecommendationExecuteRequest(BaseModel):
    comment: str = Field(default="", max_length=500, description="Optional execution commentary")


class RecommendationListResponse(BaseModel):
    items: list[RecommendationRead]
    count: int
    pending_count: int
    approved_count: int
    executed_count: int
    data_mode: str = "live_database"
