"""
Inventory API router with controlled stock receipts, issues, movement audits, and concurrency locks.
"""
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.product import ProductRepository
from app.repositories.warehouse import WarehouseRepository
from app.schemas.common import PaginatedResponse
from app.schemas.inventory import (
    InventoryDetailRead,
    InventoryUpdate,
    StockIssueRequest,
    StockMovementRead,
    StockReceiptRequest,
)

router = APIRouter()


@router.get("", response_model=PaginatedResponse[InventoryDetailRead])
async def list_inventory(
    search: str | None = Query(default=None, description="Search by product name, SKU, or warehouse name/code"),
    warehouse_id: uuid.UUID | None = Query(default=None, description="Filter by warehouse ID"),
    low_stock_only: bool = Query(default=False, description="Filter to items at or below reorder threshold"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Lists current inventory stock across warehouses with filtering and pagination."""
    repo = InventoryRepository(session)
    skip = (page - 1) * page_size
    items, total = await repo.list_filtered(
        search=search,
        warehouse_id=warehouse_id,
        low_stock_only=low_stock_only,
        skip=skip,
        limit=page_size,
    )
    return PaginatedResponse.create(
        items=[InventoryDetailRead.model_validate(inv) for inv in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/by-location", response_model=InventoryDetailRead)
async def get_inventory_by_location(
    product_id: uuid.UUID = Query(description="Product ID"),
    warehouse_id: uuid.UUID = Query(description="Warehouse ID"),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieves the inventory balance for a specific product at a specific warehouse facility."""
    repo = InventoryRepository(session)
    inv = await repo.get_by_product_and_warehouse(product_id, warehouse_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No inventory record exists for the given product and warehouse location",
        )
    return InventoryDetailRead.model_validate(inv)


@router.get("/movements", response_model=PaginatedResponse[StockMovementRead])
async def list_stock_movements(
    product_id: uuid.UUID | None = Query(default=None, description="Filter by product ID"),
    warehouse_id: uuid.UUID | None = Query(default=None, description="Filter by warehouse ID"),
    movement_type: str | None = Query(default=None, description="Filter by RECEIPT, ISSUE, etc."),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Lists immutable audit log of stock movements (receipts, issues, adjustments)."""
    repo = InventoryRepository(session)
    skip = (page - 1) * page_size
    movements, total = await repo.list_movements(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        skip=skip,
        limit=page_size,
    )
    return PaginatedResponse.create(
        items=[StockMovementRead.model_validate(m) for m in movements],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{inventory_id}", response_model=InventoryDetailRead)
async def get_inventory_item(
    inventory_id: uuid.UUID,
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieves a single inventory balance row by ID."""
    repo = InventoryRepository(session)
    inv = await repo.get_by_id(inventory_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory record not found",
        )
    return InventoryDetailRead.model_validate(inv)


@router.patch("/{inventory_id}", response_model=InventoryDetailRead)
async def update_inventory_thresholds(
    inventory_id: uuid.UUID,
    payload: InventoryUpdate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Updates operational thresholds (reorder quantity) only; does not overwrite live stock balances."""
    repo = InventoryRepository(session)
    inv = await repo.get_by_id(inventory_id)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory record not found",
        )

    if payload.reorder_quantity is not None:
        inv.reorder_quantity = payload.reorder_quantity

    await repo.update(inv)
    loaded = await repo.get_by_id(inv.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="inventory",
            entity_id=str(inv.id),
            action="inventory.update_threshold",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={"reorder_quantity": inv.reorder_quantity},
        )
    )

    return InventoryDetailRead.model_validate(loaded)


@router.post("/receipt", response_model=InventoryDetailRead, status_code=status.HTTP_200_OK)
async def receive_stock(
    payload: StockReceiptRequest,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """
    Atomically processes inbound stock receipt into the designated warehouse.
    Enforces row-level locking, records StockMovement, and verifies idempotency.
    """
    prod_repo = ProductRepository(session)
    product = await prod_repo.get_by_id(payload.product_id)
    if not product or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product {payload.product_id} does not exist or is inactive",
        )

    wh_repo = WarehouseRepository(session)
    warehouse = await wh_repo.get_by_id(payload.warehouse_id)
    if not warehouse or not warehouse.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Warehouse {payload.warehouse_id} does not exist or is inactive",
        )

    repo = InventoryRepository(session)
    try:
        inv, mov = await repo.execute_receipt(
            product_id=payload.product_id,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            reference=payload.reference,
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="inventory",
            entity_id=str(inv.id),
            action="inventory.receipt",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={
                "quantity": payload.quantity,
                "reference": payload.reference,
                "movement_id": str(mov.id),
                "idempotency_key": payload.idempotency_key,
            },
        )
    )

    loaded = await repo.get_by_id(inv.id)
    return InventoryDetailRead.model_validate(loaded)


@router.post("/issue", response_model=InventoryDetailRead, status_code=status.HTTP_200_OK)
async def issue_stock(
    payload: StockIssueRequest,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """
    Atomically issues outbound stock from a warehouse facility.
    Enforces row-level locking, prevents negative available stock, and records movement.
    """
    repo = InventoryRepository(session)
    try:
        inv, mov = await repo.execute_issue(
            product_id=payload.product_id,
            warehouse_id=payload.warehouse_id,
            quantity=payload.quantity,
            reference=payload.reference,
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            idempotency_key=payload.idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="inventory",
            entity_id=str(inv.id),
            action="inventory.issue",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={
                "quantity": payload.quantity,
                "reference": payload.reference,
                "movement_id": str(mov.id),
                "idempotency_key": payload.idempotency_key,
            },
        )
    )

    loaded = await repo.get_by_id(inv.id)
    return InventoryDetailRead.model_validate(loaded)
