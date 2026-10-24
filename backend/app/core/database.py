"""
Database session management and async engine configuration.
SQLAlchemy 2.x async engine and sessionmaker.
Connections are NOT initiated during module import.
"""
import logging
from typing import Any, AsyncGenerator
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Returns the singleton AsyncEngine instance, creating it lazily if necessary.
    No physical connection is established until a connection is checked out.
    """
    global _engine
    if _engine is None:
        url = settings.async_database_url
        engine_kwargs: dict = {
            "echo": settings.db_echo,
            "future": True,
        }

        # Configure pool settings for non-SQLite databases
        if not url.startswith("sqlite"):
            engine_kwargs.update(
                {
                    "pool_size": settings.db_pool_size,
                    "max_overflow": settings.db_max_overflow,
                    "pool_timeout": settings.db_pool_timeout,
                    "pool_recycle": settings.db_pool_recycle,
                    "pool_pre_ping": True,
                }
            )

        _engine = create_async_engine(url, **engine_kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Returns the singleton async sessionmaker instance.
    """
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an isolated AsyncSession per request.
    Rolls back automatically on exception and always closes the session.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_connection(timeout_seconds: float = 3.0) -> tuple[bool, str | None]:
    """
    Safely verifies database connectivity without raising unhandled exceptions.
    Returns (True, None) if reachable, or (False, error_details) on failure.
    """
    try:
        engine = get_engine()
        import asyncio

        async def _ping():
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_ping(), timeout=timeout_seconds)
        return True, None
    except asyncio.TimeoutError:
        msg = f"Database connection timed out after {timeout_seconds}s"
        logger.warning(msg)
        return False, msg
    except SQLAlchemyError as exc:
        msg = f"Database connection error: {exc.__class__.__name__}: {str(exc)}"
        logger.warning(msg)
        return False, msg
    except Exception as exc:
        msg = f"Unexpected database error: {exc.__class__.__name__}: {str(exc)}"
        logger.warning(msg)
        return False, msg


async def dispose_engine() -> None:
    """Closes engine connections during application shutdown or test cleanup."""
    global _engine, _session_factory, _is_fallback_active
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        _is_fallback_active = False


_is_fallback_active: bool = False


def is_fallback_active() -> bool:
    return _is_fallback_active


def get_active_backend() -> str:
    """Returns the normalized name of the active database backend ('postgresql', 'sqlite', or 'unknown')."""
    global _is_fallback_active, _engine
    if _is_fallback_active:
        return "sqlite"
    try:
        engine = get_engine()
        name = engine.url.get_backend_name()
        if name in ("postgresql", "postgres"):
            return "postgresql"
        if name == "sqlite":
            return "sqlite"
        return name
    except Exception:
        return "unknown"


def get_database_diagnostics() -> dict[str, Any]:
    """
    Returns safe diagnostic metadata about the current database configuration.
    Strictly omits credentials, tokens, passwords, and sensitive network paths.
    """
    from typing import Any
    backend = get_active_backend()
    fallback = is_fallback_active()
    diag: dict[str, Any] = {
        "backend": backend,
        "fallback_active": fallback,
        "is_sqlite": backend == "sqlite",
        "is_postgresql": backend == "postgresql",
        "echo": settings.db_echo,
    }
    if backend == "postgresql":
        diag.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout,
                "pool_recycle": settings.db_pool_recycle,
            }
        )
    return diag


async def enable_sqlite_fallback(db_path: str = "./ops_control.db") -> None:
    """
    Safely switches sessionmaker and engine to persistent local SQLite
    when PostgreSQL is unconfigured or unreachable.
    Creates schema tables automatically if they do not exist.
    Refuses execution in production mode or when allow_sqlite_fallback is False.
    """
    if settings.app_env.lower() in ("production", "staging") or not settings.allow_sqlite_fallback:
        raise RuntimeError(
            f"SQLite fallback is forbidden in {settings.app_env} or when allow_sqlite_fallback is False. "
            "Please ensure primary PostgreSQL database is running, accessible, and correctly configured."
        )

    global _engine, _session_factory, _is_fallback_active
    if _engine is not None:
        await _engine.dispose()

    fallback_url = f"sqlite+aiosqlite:///{db_path}"
    _engine = create_async_engine(fallback_url, echo=settings.db_echo, future=True)
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )
    _is_fallback_active = True

    from app.models.base import Base
    import app.models.user
    import app.models.product
    import app.models.supplier
    import app.models.warehouse
    import app.models.inventory
    import app.models.order
    import app.models.recommendation
    import app.models.audit_log

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.warning(
        "OPERATIONAL WARNING: Local persistent SQLite fallback database activated at %s. "
        "Data changes will persist locally but will NOT synchronize to primary PostgreSQL.",
        fallback_url,
    )

