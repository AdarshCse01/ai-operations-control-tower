"""
Authentication and session management API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.roles import UserRole
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import TokenResponse, UserCreate, UserLogin, UserProfile, UserRead

router = APIRouter()


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit("10/minute")
async def register(
    request: Request,
    payload: UserCreate,
    session: AsyncSession = Depends(get_db),
):
    user_repo = UserRepository(session)
    existing_user = await user_repo.get_by_email(payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists",
        )

    # Securely hash password
    hashed_pw = hash_password(payload.password)
    normalized_role = UserRole.from_str(payload.role).value

    new_user = User(
        email=payload.email,
        hashed_password=hashed_pw,
        full_name=payload.full_name,
        role=normalized_role,
        is_active=payload.is_active,
    )
    saved_user = await user_repo.create(new_user)
    return saved_user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive JWT token / session cookie",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    session: AsyncSession = Depends(get_db),
):
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(payload.email)

    # Constant-time comparison or fail cleanly without leaking whether user exists
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Contact an administrator.",
        )

    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
    )

    # Set secure HttpOnly session cookie to protect SPAs against token exfiltration via XSS
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        path="/",
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserRead.model_validate(user),
    )


@router.post(
    "/logout",
    summary="Clear current session cookie",
)
async def logout(response: Response):
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite=settings.cookie_samesite,
        httponly=True,
        secure=settings.cookie_secure,
    )
    return {"status": "ok", "message": "Successfully logged out"}


@router.get(
    "/config",
    summary="Retrieve public client authentication configuration",
)
async def get_auth_config():
    """Returns safe, public authentication configuration without exposing secrets."""
    is_prod_or_staging = settings.app_env.lower() in ("production", "staging")
    return {
        "environment": settings.app_env,
        "demo_logins_enabled": settings.enable_demo_logins and not is_prod_or_staging,
        "cookie_secure": settings.cookie_secure,
        "password_policy": {
            "min_length": 8,
            "max_length": 72,
            "require_letter": True,
            "require_digit": True,
        },
    }


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Retrieve authenticated user profile and permissions",
)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
):
    return UserProfile.from_user(current_user)
