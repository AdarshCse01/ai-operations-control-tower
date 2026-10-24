import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import normalize_database_url, settings
from app.models import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set model metadata for autogenerate and migrations
target_metadata = Base.metadata


def get_sync_url(url: str) -> str:
    """Strips async driver prefix for offline migration script generation."""
    return url.replace("+asyncpg", "").replace("+aiosqlite", "")


def get_migration_url() -> str:
    """
    Resolves and normalizes database URL for Alembic migrations.
    Respects explicit configuration overrides (e.g. isolated test databases),
    falling back to settings.async_database_url (which incorporates environment DATABASE_URL).
    Ensures URL uses async driver and normalizes unsupported libpq query parameters.
    """
    ini_url = config.get_main_option("sqlalchemy.url")
    if ini_url and ini_url != "postgresql+asyncpg://postgres:postgres@localhost:5432/ops_control":
        return normalize_database_url(ini_url)
    return settings.async_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_migration_url()
    sync_url = get_sync_url(url)

    context.configure(
        url=sync_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    url = get_migration_url()

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
