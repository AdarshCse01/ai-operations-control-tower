"""
Suppliers API router with full CRUD, filtering, pagination, safe deletion, and RBAC guards.
"""
from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.models.audit_log import AuditLog
from app.models.supplier import Supplier
from app.models.user import User
from app.repositories.audit_log import AuditLogRepository
from app.repositories.supplier import SupplierRepository
from app.schemas.common import PaginatedResponse
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate

router = APIRouter()


@router.get("", response_model=PaginatedResponse[SupplierRead])
async def list_suppliers(
    search: str | None = Query(default=None, description="Search by supplier name or code"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Lists suppliers with optional search, active filtering, and pagination."""
    repo = SupplierRepository(session)
    skip = (page - 1) * page_size
    items, total = await repo.list_filtered(search=search, is_active=is_active, skip=skip, limit=page_size)
    return PaginatedResponse.create(
        items=[SupplierRead.model_validate(s) for s in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Creates a new supplier after validating code uniqueness."""
    repo = SupplierRepository(session)
    existing = await repo.get_by_code(payload.code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Supplier with code '{payload.code}' already exists",
        )

    supplier = Supplier(**payload.model_dump())
    created = await repo.create(supplier)

    # Audit log
    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="supplier",
            entity_id=str(created.id),
            action="supplier.create",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={"code": created.code, "name": created.name},
        )
    )

    return SupplierRead.model_validate(created)


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(
    supplier_id: uuid.UUID,
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieves a single supplier by unique ID."""
    repo = SupplierRepository(session)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )
    return SupplierRead.model_validate(supplier)


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Updates supplier details and validates code uniqueness if changed."""
    repo = SupplierRepository(session)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    update_dict = payload.model_dump(exclude_unset=True)
    if "code" in update_dict and update_dict["code"] and update_dict["code"].strip().lower() != supplier.code.lower():
        existing = await repo.get_by_code(update_dict["code"])
        if existing and existing.id != supplier.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Supplier code '{update_dict['code']}' is already in use",
            )

    for field, val in update_dict.items():
        setattr(supplier, field, val)

    await repo.update(supplier)
    loaded = await repo.get_by_id(supplier.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="supplier",
            entity_id=str(supplier.id),
            action="supplier.update",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload=update_dict,
        )
    )

    return SupplierRead.model_validate(loaded)


@router.post("/{supplier_id}/deactivate", response_model=SupplierRead)
async def deactivate_supplier(
    supplier_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Deactivates a supplier safely without deleting historical relations."""
    repo = SupplierRepository(session)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    supplier.is_active = False
    await repo.update(supplier)
    loaded = await repo.get_by_id(supplier.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="supplier",
            entity_id=str(supplier.id),
            action="supplier.deactivate",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
        )
    )

    return SupplierRead.model_validate(loaded)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(
    supplier_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Deletes a supplier only if no catalog products reference it."""
    repo = SupplierRepository(session)
    supplier = await repo.get_by_id(supplier_id)
    if not supplier:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Supplier not found",
        )

    if await repo.has_associated_products(supplier_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete supplier: active catalog products reference this supplier. Deactivate instead.",
        )

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="supplier",
            entity_id=str(supplier.id),
            action="supplier.delete",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={"code": supplier.code, "name": supplier.name},
        )
    )

    await repo.delete(supplier_id)
