"""Central repositories package."""
from app.repositories.base import BaseRepository
from app.repositories.user import UserRepository
from app.repositories.supplier import SupplierRepository
from app.repositories.product import ProductRepository
from app.repositories.warehouse import WarehouseRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.order import OrderRepository, OrderItemRepository
from app.repositories.audit_log import AuditLogRepository
from app.repositories.recommendation import RecommendationRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "SupplierRepository",
    "ProductRepository",
    "WarehouseRepository",
    "InventoryRepository",
    "OrderRepository",
    "OrderItemRepository",
    "AuditLogRepository",
    "RecommendationRepository",
]
