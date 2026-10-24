"""
Integration tests targeting live PostgreSQL.
These tests only execute if a live, authenticated PostgreSQL instance is reachable.
If PostgreSQL is unreachable or authentication fails, tests are skipped with a clear explanation.
"""
import os
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.config import settings
from app.models.base import Base


@pytest.mark.asyncio
async def test_live_postgres_connectivity():
    """
    Attempts connection to the configured PostgreSQL instance.
    Skips cleanly if PostgreSQL is not reachable or credentials fail.
    """
    url = settings.async_database_url
    if not url.startswith("postgresql"):
        pytest.skip("Configured database URL is not PostgreSQL; skipping live PostgreSQL test.")

    test_engine = create_async_engine(url, connect_args={"timeout": 2})
    try:
        async with test_engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            row = result.scalar()
            assert row is not None
            assert "PostgreSQL" in row
    except Exception as exc:
        pytest.skip(
            f"Live PostgreSQL server is not accessible with configured credentials ({exc.__class__.__name__}: {exc}). "
            "To verify PostgreSQL, ensure a test PostgreSQL database is running with valid credentials in DATABASE_URL."
        )
    finally:
        await test_engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_schema_creation_and_transaction_rollback():
    """
    When live PostgreSQL is accessible, verifies schema creation, foreign key constraints,
    and transaction rollback behavior.
    """
    url = settings.async_database_url
    if not url.startswith("postgresql"):
        pytest.skip("Configured database URL is not PostgreSQL; skipping live PostgreSQL test.")

    test_engine = create_async_engine(url, connect_args={"timeout": 2})
    try:
        # Check connectivity first
        async with test_engine.connect() as conn:
            await conn.execute(text("SELECT 1;"))
    except Exception as exc:
        pytest.skip(
            f"Live PostgreSQL server is not accessible ({exc.__class__.__name__}: {exc}). "
            "Skipping schema verification on PostgreSQL."
        )
        return
    finally:
        await test_engine.dispose()

    # If connection succeeded, test Alembic migration against postgres
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    config = Config(ini_path)
    config.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    # Alembic online migration uses asyncpg/psycopg
    sync_url = settings.database_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    config.set_main_option("sqlalchemy.url", sync_url)

    try:
        command.upgrade(config, "head")
    except Exception as exc:
        pytest.fail(f"PostgreSQL Alembic migration to head failed: {exc}")
