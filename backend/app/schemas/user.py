"""Pydantic schemas for User authentication, profiles, and role assignments."""
from datetime import datetime
import re
from typing import Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from app.core.roles import UserRole
from app.core.permissions import get_permissions_for_role


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="VIEWER")
    is_active: bool = True

    @field_validator("role", mode="before")
    @classmethod
    def validate_and_normalize_role(cls, v: str) -> str:
        if isinstance(v, str):
            try:
                return UserRole.from_str(v).value
            except ValueError as e:
                raise ValueError(str(e))
        return v


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Za-z]", v):
            raise ValueError("Password must contain at least one letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = None
    is_active: bool | None = None

    @field_validator("role", mode="before")
    @classmethod
    def validate_update_role(cls, v: str | None) -> str | None:
        if v is not None:
            return UserRole.from_str(v).value
        return v


class UserRead(UserBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UserProfile(UserRead):
    """Detailed profile with resolved RBAC permissions list."""
    permissions: list[str] = []

    @classmethod
    def from_user(cls, user: Any) -> "UserProfile":
        perms = sorted([p.value for p in get_permissions_for_role(user.role)])
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            permissions=perms,
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead
