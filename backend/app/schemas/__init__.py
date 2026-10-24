"""Central schemas package."""
from app.schemas.common import PaginatedResponse
from app.schemas.user import (
    UserBase,
    UserCreate,
    UserLogin,
    UserRead,
    UserProfile,
    UserUpdate,
    TokenResponse,
)
from app.schemas.supplier import SupplierBase, SupplierCreate, SupplierRead, SupplierUpdate
from app.schemas.product import ProductBase, ProductCreate, ProductRead, ProductUpdate
from app.schemas.warehouse import WarehouseBase, WarehouseCreate, WarehouseRead, WarehouseUpdate
from app.schemas.inventory import (
    InventoryBase,
    InventoryCreate,
    InventoryRead,
    InventoryDetailRead,
    InventoryUpdate,
    StockReceiptRequest,
    StockIssueRequest,
    StockMovementRead,
)
from app.schemas.order import (
    OrderCreate,
    OrderRead,
    OrderStatusUpdate,
    OrderUpdate,
    OrderItemCreate,
    OrderItemRead,
)
from app.schemas.audit_log import AuditLogBase, AuditLogCreate, AuditLogRead
from app.schemas.risk import RiskItem, RiskResponse
from app.schemas.recommendation import (
    RecommendationRead,
    RecommendationApprovalRequest,
    RecommendationExecuteRequest,
    RecommendationListResponse,
)
from app.schemas.analytics import OperationalSummary, MLEvaluationMetrics

__all__ = [
    "PaginatedResponse",
    "UserBase",
    "UserCreate",
    "UserLogin",
    "UserRead",
    "UserProfile",
    "UserUpdate",
    "TokenResponse",
    "SupplierBase",
    "SupplierCreate",
    "SupplierRead",
    "SupplierUpdate",
    "ProductBase",
    "ProductCreate",
    "ProductRead",
    "ProductUpdate",
    "WarehouseBase",
    "WarehouseCreate",
    "WarehouseRead",
    "WarehouseUpdate",
    "InventoryBase",
    "InventoryCreate",
    "InventoryRead",
    "InventoryDetailRead",
    "InventoryUpdate",
    "StockReceiptRequest",
    "StockIssueRequest",
    "StockMovementRead",
    "OrderCreate",
    "OrderRead",
    "OrderStatusUpdate",
    "OrderUpdate",
    "OrderItemCreate",
    "OrderItemRead",
    "AuditLogBase",
    "AuditLogCreate",
    "AuditLogRead",
    "RiskItem",
    "RiskResponse",
    "RecommendationRead",
    "RecommendationApprovalRequest",
    "RecommendationExecuteRequest",
    "RecommendationListResponse",
    "OperationalSummary",
    "MLEvaluationMetrics",
]
