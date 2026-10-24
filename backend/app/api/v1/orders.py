"""
Orders API router with server-calculated totals, strict state transitions, and RBAC guards.
"""
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.audit_log import AuditLog
from app.models.product import Product
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.order import OrderRepository
from app.repositories.product import ProductRepository
from app.repositories.warehouse import WarehouseRepository
from app.schemas.common import PaginatedResponse
from app.schemas.order import OrderCreate, OrderRead, OrderStatusUpdate, OrderUpdate

router = APIRouter()


@router.get("", response_model=PaginatedResponse[OrderRead])
async def list_orders(
    search: str | None = Query(default=None, description="Search by order number or customer name"),
    status_filter: str | None = Query(default=None, alias="status", description="Filter by status (PENDING, PROCESSING, etc.)"),
    priority: str | None = Query(default=None, description="Filter by priority (LOW, NORMAL, HIGH, CRITICAL)"),
    warehouse_id: uuid.UUID | None = Query(default=None, description="Filter by warehouse ID"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Lists orders with search, multi-field filtering, and pagination."""
    repo = OrderRepository(session)
    skip = (page - 1) * page_size
    items, total = await repo.list_filtered(
        search=search,
        status=status_filter,
        priority=priority,
        warehouse_id=warehouse_id,
        skip=skip,
        limit=page_size,
    )
    return PaginatedResponse.create(
        items=[OrderRead.model_validate(o) for o in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=OrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: OrderCreate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """
    Creates a new order with line items.
    All unit prices and totals are calculated strictly on the backend from product catalog records.
    """
    if payload.warehouse_id:
        wh_repo = WarehouseRepository(session)
        wh = await wh_repo.get_by_id(payload.warehouse_id)
        if not wh or not wh.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Warehouse {payload.warehouse_id} does not exist or is inactive",
            )

    prod_repo = ProductRepository(session)
    items_data: list[tuple[Product, int]] = []

    # Consolidate and validate requested line items
    consolidated_items: dict[uuid.UUID, int] = {}
    for item_in in payload.items:
        if item_in.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Item quantity for product {item_in.product_id} must be strictly positive",
            )
        consolidated_items[item_in.product_id] = (
            consolidated_items.get(item_in.product_id, 0) + item_in.quantity
        )

    for prod_id, qty in consolidated_items.items():
        product = await prod_repo.get_by_id(prod_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product with ID {prod_id} does not exist",
            )
        if not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Product '{product.sku}' ({product.name}) is inactive and cannot be ordered",
            )
        items_data.append((product, qty))

    repo = OrderRepository(session)
    try:
        order = await repo.create_order_with_items(
            customer_name=payload.customer_name,
            warehouse_id=payload.warehouse_id,
            priority=payload.priority,
            expected_delivery_date=payload.expected_delivery_date,
            items_data=items_data,
            created_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="order",
            entity_id=str(order.id),
            action="order.create",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={
                "order_number": order.order_number,
                "total_amount": str(order.total_amount),
                "item_count": len(order.items),
            },
        )
    )

    return OrderRead.model_validate(order)


@router.get("/{order_id}", response_model=OrderRead)
async def get_order(
    order_id: uuid.UUID,
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieves full order details including line items, warehouse, and creator."""
    repo = OrderRepository(session)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return OrderRead.model_validate(order)


@router.patch("/{order_id}/status", response_model=OrderRead)
@router.post("/{order_id}/status", response_model=OrderRead)
async def update_order_status(
    order_id: uuid.UUID,
    payload: OrderStatusUpdate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """
    Enforces valid order status lifecycle transitions:
    PENDING -> PROCESSING, CANCELLED
    PROCESSING -> SHIPPED, CANCELLED
    SHIPPED -> DELIVERED, CANCELLED
    DELIVERED, CANCELLED -> terminal
    """
    repo = OrderRepository(session)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    old_status = order.status
    try:
        repo.validate_and_update_status(order, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    await repo.update(order)
    loaded = await repo.get_by_id(order.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="order",
            entity_id=str(order.id),
            action="order.status_change",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            comment=payload.comment,
            payload={"old_status": old_status, "new_status": order.status},
        )
    )

    return OrderRead.model_validate(loaded)


@router.patch("/{order_id}", response_model=OrderRead)
async def update_order_metadata(
    order_id: uuid.UUID,
    payload: OrderUpdate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Updates non-financial metadata on orders that are not in terminal status."""
    repo = OrderRepository(session)
    order = await repo.get_by_id(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    if order.status in ("DELIVERED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot modify order in terminal status '{order.status}'",
        )

    update_dict = payload.model_dump(exclude_unset=True)
    if "warehouse_id" in update_dict and update_dict["warehouse_id"]:
        wh_repo = WarehouseRepository(session)
        wh = await wh_repo.get_by_id(update_dict["warehouse_id"])
        if not wh or not wh.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Warehouse {update_dict['warehouse_id']} does not exist or is inactive",
            )

    for field, val in update_dict.items():
        setattr(order, field, val)

    await repo.update(order)
    loaded = await repo.get_by_id(order.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="order",
            entity_id=str(order.id),
            action="order.update",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={k: str(v) if isinstance(v, uuid.UUID) else v for k, v in update_dict.items()},
        )
    )

    return OrderRead.model_validate(loaded)
