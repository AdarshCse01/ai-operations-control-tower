"""
API dependencies: database session, authentication, and RBAC authorization guards.
"""
from typing import AsyncGenerator
from uuid import UUID
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.permissions import Permission, has_permission
from app.core.roles import UserRole
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository


def extract_token_from_header_or_cookie(
    request: Request,
    authorization: str | None = Header(default=None),
    access_token: str | None = Cookie(default=None),
    x_requested_with: str | None = Header(default=None, alias="X-Requested-With"),
) -> str:
    """
    Extracts JWT from the Authorization Bearer header or the secure access_token cookie.
    Allows browsers to use HttpOnly cookies while test runners and API clients use headers.

    CSRF Protection:
    State-changing requests (POST, PUT, PATCH, DELETE) authenticated via session cookie
    MUST provide the custom header 'X-Requested-With'. Simple cross-origin form submissions
    cannot set custom headers without triggering CORS preflight.
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()
    if access_token:
        # Enforce CSRF protection on mutating methods when authenticated via cookie
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            if not x_requested_with:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CSRF protection: 'X-Requested-With' header is required for cookie-authenticated state-changing requests.",
                )
        return access_token.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a Bearer token or active session cookie.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(extract_token_from_header_or_cookie),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Validates token claims, checks user persistence in the database,
    and returns the active User model instance.
    """
    payload = decode_access_token(token)
    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_uuid = UUID(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identifier format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_uuid)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Verifies that the authenticated user account is active."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )
    return current_user


def require_roles(*roles: UserRole):
    """Dependency factory restricting route access to specific roles."""
    async def _role_guard(current_user: User = Depends(get_current_active_user)) -> User:
        user_role = UserRole.from_str(current_user.role)
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation requires one of the following roles: {[r.value for r in roles]}",
            )
        return current_user

    return _role_guard


def require_permission(permission: Permission):
    """Dependency factory checking whether the current user has the required permission."""
    async def _permission_guard(current_user: User = Depends(get_current_active_user)) -> User:
        if not has_permission(current_user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission.value}",
            )
        return current_user

    return _permission_guard


__all__ = [
    "get_db",
    "get_current_user",
    "get_current_active_user",
    "require_roles",
    "require_permission",
    "AsyncSession",
    "Depends",
]
