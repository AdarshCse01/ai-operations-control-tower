"""
User roles enumeration and normalization.
"""
from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    OPERATIONS_MANAGER = "OPERATIONS_MANAGER"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"

    @classmethod
    def from_str(cls, value: str) -> "UserRole":
        """Normalizes role strings case-insensitively with backward-compatible aliases."""
        cleaned = value.strip().upper()
        if cleaned in ("ADMIN",):
            return cls.ADMIN
        if cleaned in ("OPERATIONS_MANAGER", "OPERATOR", "MANAGER"):
            return cls.OPERATIONS_MANAGER
        if cleaned in ("ANALYST",):
            return cls.ANALYST
        if cleaned in ("VIEWER",):
            return cls.VIEWER
        raise ValueError(f"Invalid user role: {value}. Allowed roles: {[r.value for r in cls]}")
