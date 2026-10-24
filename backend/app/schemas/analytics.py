"""
Pydantic schemas for Operational Analytics and Statistical/ML Baseline Evaluation.
Includes Executive Dashboard KPIs, order volume time-series, status breakdown,
inventory valuations, low-stock trends, fulfillment performance, and supplier metrics.
"""
from typing import Any
from pydantic import BaseModel, Field


class OperationalSummary(BaseModel):
    total_products: int = Field(ge=0)
    active_products: int = Field(ge=0)
    total_inventory_units: int = Field(ge=0)
    reserved_inventory_units: int = Field(ge=0)
    available_inventory_units: int = Field(ge=0)
    low_stock_items_count: int = Field(ge=0)
    stockout_items_count: int = Field(ge=0)
    total_inventory_valuation: str
    total_orders: int = Field(ge=0)
    pending_orders: int = Field(ge=0)
    processing_orders: int = Field(ge=0)
    shipped_orders: int = Field(ge=0)
    delivered_orders: int = Field(ge=0)
    cancelled_orders: int = Field(ge=0)
    on_time_fulfillment_rate: float | None = None
    total_movement_volume: int = Field(ge=0)


class MLEvaluationMetrics(BaseModel):
    model_name: str
    task_type: str
    status: str  # "evaluated" | "insufficient_data"
    samples_count: int
    accuracy: float | None = None
    precision: float | None = None
    recall: float | None = None
    f1_score: float | None = None
    mae: float | None = None
    baseline_comparison: dict[str, Any] | None = None
    data_requirements: list[str] | None = None
    evaluation_notes: str


# -------------------------------------------------------------------------
# Phase 6: Advanced Analytics & Executive Dashboard Schemas
# -------------------------------------------------------------------------

class DateRangeInfo(BaseModel):
    label: str
    start_date: str | None = None
    end_date: str | None = None
    preset: str | None = None


class OrderTrendPoint(BaseModel):
    date: str
    orders_count: int = Field(ge=0)
    delivered_count: int = Field(ge=0)
    delayed_count: int = Field(ge=0)
    total_revenue: str


class OrderVolumeTrendResponse(BaseModel):
    data_mode: str = "live_database"
    date_range: DateRangeInfo
    total_orders: int = Field(ge=0)
    total_revenue: str
    average_order_value: str
    trend: list[OrderTrendPoint]
    is_empty: bool = False


class OrderStatusItem(BaseModel):
    status: str
    count: int = Field(ge=0)
    percentage: float = Field(ge=0.0, le=100.0)
    total_amount: str


class OrderStatusDistributionResponse(BaseModel):
    data_mode: str = "live_database"
    total_orders: int = Field(ge=0)
    distribution: list[OrderStatusItem]
    is_empty: bool = False


class WarehouseStockItem(BaseModel):
    warehouse_id: str
    warehouse_code: str
    warehouse_name: str
    total_units: int = Field(ge=0)
    available_units: int = Field(ge=0)
    reserved_units: int = Field(ge=0)
    valuation: str
    sku_count: int = Field(ge=0)


class CategoryStockItem(BaseModel):
    category: str
    total_units: int = Field(ge=0)
    valuation: str
    sku_count: int = Field(ge=0)


class InventoryValuationResponse(BaseModel):
    data_mode: str = "live_database"
    total_inventory_units: int = Field(ge=0)
    available_inventory_units: int = Field(ge=0)
    reserved_inventory_units: int = Field(ge=0)
    total_valuation: str
    retail_valuation: str
    warehouses: list[WarehouseStockItem]
    categories: list[CategoryStockItem]
    is_empty: bool = False


class LowStockAlertItem(BaseModel):
    inventory_id: str
    product_id: str
    product_sku: str
    product_name: str
    product_category: str
    warehouse_code: str
    warehouse_name: str
    quantity_on_hand: int = Field(ge=0)
    quantity_reserved: int = Field(ge=0)
    available_quantity: int
    reorder_quantity: int = Field(ge=0)
    safety_stock: int = Field(ge=0)
    unit_cost: str
    status: str  # "STOCKOUT" | "LOW_STOCK"


class LowStockResponse(BaseModel):
    data_mode: str = "live_database"
    stockout_count: int = Field(ge=0)
    low_stock_count: int = Field(ge=0)
    items: list[LowStockAlertItem]
    is_empty: bool = False


class FulfillmentMetricsResponse(BaseModel):
    data_mode: str = "live_database"
    has_sufficient_data: bool
    total_delivered_orders: int = Field(ge=0)
    delivered_with_targets: int = Field(ge=0)
    on_time_count: int = Field(ge=0)
    delayed_count: int = Field(ge=0)
    on_time_rate: float | None = None
    average_fulfillment_days: float | None = None
    status_message: str


class SupplierPerformanceItem(BaseModel):
    supplier_id: str
    code: str
    name: str
    lead_time_days: int = Field(ge=0)
    reliability_score: float = Field(ge=0.0, le=1.0)
    active_products_count: int = Field(ge=0)
    is_active: bool


class SupplierPerformanceResponse(BaseModel):
    data_mode: str = "live_database"
    has_sufficient_data: bool
    total_suppliers: int = Field(ge=0)
    average_reliability_score: float | None = None
    average_lead_time_days: float | None = None
    suppliers: list[SupplierPerformanceItem]
    transparency_note: str


class ExecutiveDashboardKPIs(BaseModel):
    total_orders: int = Field(ge=0)
    active_orders: int = Field(ge=0)  # PENDING + PROCESSING + SHIPPED
    delivered_orders: int = Field(ge=0)
    cancelled_orders: int = Field(ge=0)
    total_order_valuation: str
    total_inventory_units: int = Field(ge=0)
    available_inventory_units: int = Field(ge=0)
    reserved_inventory_units: int = Field(ge=0)
    total_inventory_valuation: str
    low_stock_items_count: int = Field(ge=0)
    stockout_items_count: int = Field(ge=0)
    pending_recommendations_count: int = Field(ge=0)
    critical_risks_count: int = Field(ge=0)
    on_time_fulfillment_rate: float | None = None
    average_supplier_reliability: float | None = None


class ExecutiveDashboardResponse(BaseModel):
    generated_at: str
    data_mode: str = "live_database"
    date_range: DateRangeInfo
    kpis: ExecutiveDashboardKPIs
    order_status_distribution: list[OrderStatusItem]
    order_volume_trend: list[OrderTrendPoint]
    warehouse_stock: list[WarehouseStockItem]
    category_stock: list[CategoryStockItem]
    low_stock_alerts: list[LowStockAlertItem]
    fulfillment_summary: FulfillmentMetricsResponse
    supplier_summary: SupplierPerformanceResponse
    critical_risks_preview: list[dict[str, Any]]
    pending_recommendations_preview: list[dict[str, Any]]
