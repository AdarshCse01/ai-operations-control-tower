"""Pytest fixtures for isolated async database testing using in-memory SQLite."""
import asyncio
from typing import AsyncGenerator
import uuid
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from app.models.base import Base
from app.models.user import User
from app.core.database import get_db
from app.core.roles import UserRole
from app.core.security import create_access_token, hash_password
from app.main import app

# In-memory SQLite async URL for 100% isolated unit and model tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Provides a shared in-memory async SQLite engine with all tables initialized."""
    engine = create_async_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides an isolated database session per test with automatic rollback.
    Guarantees no state leakage between tests and zero impact on real databases.
    """
    async_session = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
def override_get_db(db_session: AsyncSession):
    """Automatically overrides FastAPI get_db dependency to point to the isolated in-memory test session."""
    async def _test_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = _test_get_db
    # Disable rate limits during test runs
    from app.core.rate_limit import limiter
    limiter.enabled = False
    yield
    app.dependency_overrides.pop(get_db, None)
    limiter.enabled = True


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client configured for the FastAPI application."""
    return TestClient(app)


@pytest_asyncio.fixture
async def make_user(db_session: AsyncSession):
    """Factory fixture for quickly creating test users with specific roles."""
    async def _make(
        role: str = UserRole.VIEWER.value,
        email: str | None = None,
        password: str = "SecurePass123",
        full_name: str = "Test User",
        is_active: bool = True,
    ) -> User:
        user_email = email or f"user_{uuid.uuid4().hex[:8]}@example.com"
        user = User(
            email=user_email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole.from_str(role).value,
            is_active=is_active,
        )
        db_session.add(user)
        await db_session.flush()
        return user

    return _make


def get_user_auth_headers(user: User) -> dict[str, str]:
    """Generates a valid Bearer authorization header dict for a given user."""
    token = create_access_token(
        subject=str(user.id),
        role=user.role,
        email=user.email,
    )
    return {"Authorization": f"Bearer {token}"}
