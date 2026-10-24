"""
User administration endpoints guarded by ADMIN / USER_MANAGE permissions.
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, require_permission
from app.core.permissions import Permission
from app.core.roles import UserRole
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserRead, UserUpdate

router = APIRouter()


@router.get(
    "",
    response_model=list[UserRead],
    summary="List registered users (Admin only)",
)
async def list_users(
    session: AsyncSession = Depends(get_db),
    _guard: User = Depends(require_permission(Permission.USER_MANAGE)),
):
    user_repo = UserRepository(session)
    users = await user_repo.list_all()
    return users


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Update user role or active status (Admin only)",
)
async def update_user(
    user_id: UUID,
    payload: UserUpdate,
    session: AsyncSession = Depends(get_db),
    _guard: User = Depends(require_permission(Permission.USER_MANAGE)),
):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = payload.model_dump(exclude_unset=True)
    if "role" in updates and updates["role"] is not None:
        updates["role"] = UserRole.from_str(updates["role"]).value

    updated_user = await user_repo.update(user, updates)
    return updated_user
