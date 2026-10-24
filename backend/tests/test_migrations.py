"""Tests for Alembic migration definitions, schema tracking, and migration execution."""
import os
import tempfile
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.models.base import Base


def test_metadata_contains_all_domain_tables():
    """Ensures all business models are registered in Base.metadata for migration tracking."""
    registered_tables = set(Base.metadata.tables.keys())
    expected_tables = {
        "users",
        "suppliers",
        "products",
        "warehouses",
        "inventories",
        "stock_movements",
        "orders",
        "order_items",
        "audit_logs",
        "recommendations",
    }
    assert expected_tables.issubset(registered_tables), (
        f"Missing tables in Base.metadata: {expected_tables - registered_tables}"
    )


def test_alembic_script_directory_and_head_revision():
    """Ensures Alembic can load migration history and has 0005_analytics_indexes as head."""
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    assert os.path.exists(ini_path), f"alembic.ini not found at {ini_path}"

    config = Config(ini_path)
    config.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
    script = ScriptDirectory.from_config(config)

    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "0005_analytics_indexes"

    rev = script.get_revision("0005_analytics_indexes")
    assert rev is not None
    assert rev.down_revision == "0004_add_recommendations"


def test_isolated_migration_upgrade_and_downgrade():
    """
    Executes actual migration upgrade and rollback against an isolated temporary database.
    Guarantees that migration DDL executes cleanly without touching live databases.
    """
    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ini_path = os.path.join(backend_dir, "alembic.ini")

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
        tmp_db_path = tmp_file.name

    try:
        config = Config(ini_path)
        config.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{tmp_db_path}")

        # Test upgrade
        command.upgrade(config, "head")

        # Test downgrade
        command.downgrade(config, "base")
    finally:
        if os.path.exists(tmp_db_path):
            os.remove(tmp_db_path)


def test_alembic_migration_url_normalizes_neon_connection(monkeypatch):
    """
    Verifies that Neon connection strings provided for migrations
    are properly normalized for asyncpg without unsupported libpq query parameters.
    """
    from app.core.config import Settings, normalize_database_url
    from sqlalchemy.engine.url import make_url
    from sqlalchemy.dialects.postgresql.asyncpg import PGDialect_asyncpg

    neon_url = "postgresql://alex:AbC123dEf@ep-cool-fog-123456.us-east-2.aws.neon.tech:5432/neondb?sslmode=require&channel_binding=require"
    monkeypatch.setenv("DATABASE_URL", neon_url)

    custom_settings = Settings(database_url=neon_url)
    resolved = custom_settings.async_database_url
    assert resolved.startswith("postgresql+asyncpg://")
    assert "sslmode" not in resolved
    assert "channel_binding" not in resolved
    assert "ssl=require" in resolved

    # Verify normalize_database_url directly matches
    assert normalize_database_url(neon_url) == resolved

    url_obj = make_url(resolved)
    cargs, cparams = PGDialect_asyncpg().create_connect_args(url_obj)
    assert cparams["host"] == "ep-cool-fog-123456.us-east-2.aws.neon.tech"
    assert cparams["database"] == "neondb"
    assert cparams["ssl"] == "require"
    assert "sslmode" not in cparams
    assert "channel_binding" not in cparams

