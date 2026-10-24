"""
Cryptographic security functions: bcrypt password hashing and PyJWT token lifecycle.
"""
from datetime import datetime, timedelta, timezone
from typing import Any
import uuid
import bcrypt
import jwt
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.roles import UserRole


def hash_password(password: str) -> str:
    """
    Hashes a plaintext password using bcrypt with automatic salt generation.
    Enforces password byte length limits to avoid silent truncation.
    """
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password exceeds maximum allowed length of 72 bytes")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plaintext password against a stored bcrypt hash.
    Safely returns False on malformed hashes without crashing.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def create_access_token(
    subject: str,
    role: str,
    email: str,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Issues a cryptographically signed JWT access token containing subject,
    role, email, and strict lifecycle claims (exp, iat, nbf, iss, aud, jti).
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    # Normalize role
    try:
        normalized_role = UserRole.from_str(role).value
    except ValueError:
        normalized_role = role.strip().upper()

    payload: dict[str, Any] = {
        "sub": str(subject),
        "email": email,
        "role": normalized_role,
        "exp": expire,
        "iat": now,
        "nbf": now,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "jti": uuid.uuid4().hex,
    }

    token = jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return token


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Validates token signature, expiration, audience, and required claims.
    Raises HTTPException 401 with standard WWW-Authenticate header on failure.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )
        if not payload.get("sub") or not payload.get("role"):
            raise credentials_exception
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise credentials_exception
