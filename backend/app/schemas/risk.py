"""
Pydantic schemas for Operational Risk Intelligence items, severity, and breakdown responses.
"""
from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class RiskItem(BaseModel):
    id: str = Field(description="Unique deterministic identifier for the risk signal")
    category: str = Field(
        pattern="^(STOCKOUT_RISK|SUPPLIER_RISK|FULFILLMENT_RISK|INVENTORY_IMBALANCE)$",
        description="Category of the operational risk",
    )
    severity: str = Field(pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$", description="Assessed severity level")
    score: int = Field(ge=0, le=100, description="Risk index from 0 (lowest) to 100 (highest)")
    entity_type: str = Field(description="Target entity type (product, supplier, order, inventory)")
    entity_id: str = Field(description="Database identifier of the affected entity")
    entity_name: str = Field(description="Human readable name or code of the entity")
    rules_triggered: list[str] = Field(default_factory=list, description="Specific operational rules triggered")
    metrics: dict[str, Any] = Field(default_factory=dict, description="Raw operational metrics responsible for score")
    explanation: str = Field(description="Detailed human-readable explanation of the risk")
    suggested_action: str = Field(description="Actionable mitigation recommendation")
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = Field(default="deterministic_rules", description="Scoring methodology: deterministic_rules | statistical_baseline")

    model_config = ConfigDict(from_attributes=True)


class RiskResponse(BaseModel):
    items: list[RiskItem]
    count: int
    critical_count: int
    high_count: int
    calculated_at: datetime
    data_mode: str = "live_database"
