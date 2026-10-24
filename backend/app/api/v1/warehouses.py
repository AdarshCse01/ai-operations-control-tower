"""
Warehouses API router with facility management, unique codes, positive capacity, and RBAC guards.
"""
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.warehouse import Warehouse
from app.repositories.audit_log import AuditLogRepository
from app.repositories.warehouse import WarehouseRepository
from app.schemas.common import PaginatedResponse
from app.schemas.warehouse import WarehouseCreate, WarehouseRead, WarehouseUpdate

router = APIRouter()


@router.get("", response_model=PaginatedResponse[WarehouseRead])
async def list_warehouses(
    search: str | None = Query(default=None, description="Search by name, code, or location"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Lists warehouse facilities with search, active filtering, and pagination."""
    repo = WarehouseRepository(session)
    skip = (page - 1) * page_size
    items, total = await repo.list_filtered(search=search, is_active=is_active, skip=skip, limit=page_size)
    return PaginatedResponse.create(
        items=[WarehouseRead.model_validate(w) for w in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=WarehouseRead, status_code=status.HTTP_201_CREATED)
async def create_warehouse(
    payload: WarehouseCreate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Creates a new warehouse facility validating unique code and positive capacity."""
    repo = WarehouseRepository(session)
    existing = await repo.get_by_code(payload.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Warehouse with code '{payload.code}' already exists",
        )

    if payload.capacity <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Warehouse capacity must be strictly greater than zero",
        )

    warehouse = Warehouse(**payload.model_dump())
    created = await repo.create(warehouse)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="warehouse",
            entity_id=str(created.id),
            action="warehouse.create",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={"code": created.code, "name": created.name, "capacity": created.capacity},
        )
    )

    return WarehouseRead.model_validate(created)


@router.get("/{warehouse_id}", response_model=WarehouseRead)
async def get_warehouse(
    warehouse_id: uuid.UUID,
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieves a single warehouse facility by ID."""
    repo = WarehouseRepository(session)
    warehouse = await repo.get_by_id(warehouse_id)
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found",
        )
    return WarehouseRead.model_validate(warehouse)


@router.patch("/{warehouse_id}", response_model=WarehouseRead)
async def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Updates warehouse details, validating code uniqueness and positive capacity."""
    repo = WarehouseRepository(session)
    warehouse = await repo.get_by_id(warehouse_id)
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found",
        )

    update_dict = payload.model_dump(exclude_unset=True)
    if "code" in update_dict and update_dict["code"] and update_dict["code"].strip().lower() != warehouse.code.lower():
        existing = await repo.get_by_code(update_dict["code"])
        if existing and existing.id != warehouse.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Warehouse code '{update_dict['code']}' is already in use",
            )

    if "capacity" in update_dict and update_dict["capacity"] is not None and update_dict["capacity"] <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Warehouse capacity must be strictly greater than zero",
        )

    for field, val in update_dict.items():
        setattr(warehouse, field, val)

    await repo.update(warehouse)
    loaded = await repo.get_by_id(warehouse.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="warehouse",
            entity_id=str(warehouse.id),
            action="warehouse.update",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload=update_dict,
        )
    )

    return WarehouseRead.model_validate(loaded)


@router.post("/{warehouse_id}/deactivate", response_model=WarehouseRead)
async def deactivate_warehouse(
    warehouse_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Deactivates a warehouse safely without losing historical records."""
    repo = WarehouseRepository(session)
    warehouse = await repo.get_by_id(warehouse_id)
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found",
        )

    warehouse.is_active = False
    await repo.update(warehouse)
    loaded = await repo.get_by_id(warehouse.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="warehouse",
            entity_id=str(warehouse.id),
            action="warehouse.deactivate",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
        )
    )

    return WarehouseRead.model_validate(loaded)


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_warehouse(
    warehouse_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Deletes a warehouse only if no on-hand inventory exists."""
    repo = WarehouseRepository(session)
    warehouse = await repo.get_by_id(warehouse_id)
    if not warehouse:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Warehouse not found",
        )

    if await repo.has_active_inventory(warehouse_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete warehouse: active on-hand inventory exists. Transfer stock or deactivate instead.",
        )

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="warehouse",
            entity_id=str(warehouse.id),
            action="warehouse.delete",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={"code": warehouse.code, "name": warehouse.name},
        )
    )

    await repo.delete(warehouse_id)
