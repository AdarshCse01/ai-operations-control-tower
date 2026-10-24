"""
Products API router with catalog CRUD, SKU uniqueness, Decimal pricing, sorting, filters, and RBAC guards.
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
from app.repositories.product import ProductRepository
from app.repositories.supplier import SupplierRepository
from app.schemas.common import PaginatedResponse
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate

router = APIRouter()


@router.get("", response_model=PaginatedResponse[ProductRead])
async def list_products(
    search: str | None = Query(default=None, description="Search by name, SKU, or category"),
    category: str | None = Query(default=None, description="Filter by product category"),
    supplier_id: uuid.UUID | None = Query(default=None, description="Filter by supplier ID"),
    is_active: bool | None = Query(default=None, description="Filter by active status"),
    sort_by: str = Query(default="name", pattern="^(name|sku|unit_price|created_at)$", description="Sort field"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$", description="Sort direction"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Lists catalog products with multi-criteria filtering, sorting, and pagination."""
    repo = ProductRepository(session)
    skip = (page - 1) * page_size
    items, total = await repo.list_filtered(
        search=search,
        category=category,
        supplier_id=supplier_id,
        is_active=is_active,
        sort_by=sort_by,
        sort_dir=sort_dir,
        skip=skip,
        limit=page_size,
    )
    return PaginatedResponse.create(
        items=[ProductRead.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Creates a new catalog product verifying SKU uniqueness and supplier existence."""
    repo = ProductRepository(session)
    existing = await repo.get_by_sku(payload.sku)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with SKU '{payload.sku}' already exists",
        )

    if payload.supplier_id:
        supplier_repo = SupplierRepository(session)
        supplier = await supplier_repo.get_by_id(payload.supplier_id)
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Referenced supplier {payload.supplier_id} does not exist",
            )

    product = Product(**payload.model_dump())
    created = await repo.create(product)
    # Reload with supplier relation
    loaded = await repo.get_by_id(created.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="product",
            entity_id=str(created.id),
            action="product.create",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={"sku": created.sku, "name": created.name, "price": str(created.unit_price)},
        )
    )

    return ProductRead.model_validate(loaded)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: uuid.UUID,
    _user: User = Depends(require_permission(Permission.DASHBOARD_READ)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Retrieves a single catalog product by ID."""
    repo = ProductRepository(session)
    product = await repo.get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return ProductRead.model_validate(product)


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: uuid.UUID,
    payload: ProductUpdate,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Updates product details, validating SKU uniqueness and supplier validity if changed."""
    repo = ProductRepository(session)
    product = await repo.get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    update_dict = payload.model_dump(exclude_unset=True)
    if "sku" in update_dict and update_dict["sku"] and update_dict["sku"].strip().lower() != product.sku.lower():
        existing = await repo.get_by_sku(update_dict["sku"])
        if existing and existing.id != product.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with SKU '{update_dict['sku']}' already exists",
            )

    if "supplier_id" in update_dict and update_dict["supplier_id"]:
        supplier_repo = SupplierRepository(session)
        supplier = await supplier_repo.get_by_id(update_dict["supplier_id"])
        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Referenced supplier {update_dict['supplier_id']} does not exist",
            )

    for field, val in update_dict.items():
        setattr(product, field, val)

    await repo.update(product)
    loaded = await repo.get_by_id(product.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="product",
            entity_id=str(product.id),
            action="product.update",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={k: str(v) if isinstance(v, uuid.UUID) else v for k, v in update_dict.items()},
        )
    )

    return ProductRead.model_validate(loaded)


@router.post("/{product_id}/deactivate", response_model=ProductRead)
async def deactivate_product(
    product_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> Any:
    """Deactivates a product safely without breaking historic orders or inventory."""
    repo = ProductRepository(session)
    product = await repo.get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    product.is_active = False
    await repo.update(product)
    loaded = await repo.get_by_id(product.id)

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="product",
            entity_id=str(product.id),
            action="product.deactivate",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
        )
    )

    return ProductRead.model_validate(loaded)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: uuid.UUID,
    current_user: User = Depends(require_permission(Permission.DATA_MANAGE)),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Deletes a product only if no active stock or historic order items exist."""
    repo = ProductRepository(session)
    product = await repo.get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    if await repo.has_active_inventory_or_orders(product_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete product: active inventory or purchase order items exist. Deactivate instead.",
        )

    audit_repo = AuditLogRepository(session)
    await audit_repo.create(
        AuditLog(
            entity_type="product",
            entity_id=str(product.id),
            action="product.delete",
            actor_id=current_user.id,
            actor_name=current_user.full_name or current_user.email,
            payload={"sku": product.sku, "name": product.name},
        )
    )

    await repo.delete(product_id)
