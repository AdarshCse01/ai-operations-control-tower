"""
Role-based access control (RBAC) permissions matrix and policy engine.
"""
from enum import Enum
from app.core.roles import UserRole


class Permission(str, Enum):
    # User Administration
    USER_MANAGE = "users:manage"
    USER_READ = "users:read"

    # Operations & Decisions
    RECOMMENDATION_DECIDE = "recommendations:decide"
    DATA_MANAGE = "data:manage"

    # Operational Analytics
    ANALYTICS_READ = "analytics:read"

    # Core Dashboard
    DASHBOARD_READ = "dashboard:read"


ROLE_PERMISSIONS: dict[UserRole, set[Permission]] = {
    UserRole.ADMIN: {
        Permission.USER_MANAGE,
        Permission.USER_READ,
        Permission.RECOMMENDATION_DECIDE,
        Permission.DATA_MANAGE,
        Permission.ANALYTICS_READ,
        Permission.DASHBOARD_READ,
    },
    UserRole.OPERATIONS_MANAGER: {
        Permission.USER_READ,
        Permission.RECOMMENDATION_DECIDE,
        Permission.DATA_MANAGE,
        Permission.ANALYTICS_READ,
        Permission.DASHBOARD_READ,
    },
    UserRole.ANALYST: {
        Permission.ANALYTICS_READ,
        Permission.DASHBOARD_READ,
    },
    UserRole.VIEWER: {
        Permission.DASHBOARD_READ,
    },
}


def get_permissions_for_role(role: UserRole | str) -> set[Permission]:
    """Returns the set of permissions assigned to a given role."""
    if isinstance(role, str):
        try:
            role = UserRole.from_str(role)
        except ValueError:
            return set()
    return ROLE_PERMISSIONS.get(role, set())


def has_permission(role: UserRole | str, permission: Permission) -> bool:
    """Checks whether a role possesses a specific permission."""
    return permission in get_permissions_for_role(role)
