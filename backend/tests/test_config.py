"""Tests for database configuration, pydantic settings, and safe error handling."""
import pytest
from app.core.config import Settings
from app.core.database import check_database_connection


def test_settings_default_values():
    settings = Settings()
    assert settings.app_env == "development"
    assert "postgresql+asyncpg" in settings.async_database_url
    assert settings.db_pool_size > 0
    assert settings.db_max_overflow >= 0


def test_settings_url_translation():
    s1 = Settings(database_url="postgresql://user:pass@localhost:5432/testdb")
    assert s1.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

    s2 = Settings(database_url="postgres://user:pass@localhost:5432/testdb")
    assert s2.async_database_url == "postgresql+asyncpg://user:pass@localhost:5432/testdb"

    s3 = Settings(database_url="sqlite+aiosqlite:///./test.db")
    assert s3.async_database_url == "sqlite+aiosqlite:///./test.db"


def test_cors_origins_parsing():
    s1 = Settings(cors_origins="http://localhost:3000, http://localhost:5173")
    assert s1.cors_origins == ["http://localhost:3000", "http://localhost:5173"]

    s2 = Settings(cors_origins='["http://localhost:3000", "http://localhost:5173"]')
    assert s2.cors_origins == ["http://localhost:3000", "http://localhost:5173"]


@pytest.mark.asyncio
async def test_safe_database_connection_error_handling():
    """Verifies that an invalid/unreachable connection URL does not crash the app or throw unhandled exceptions."""
    # check_database_connection handles timeouts or connection failures safely
    ok, error_msg = await check_database_connection(timeout_seconds=0.5)
    # The result should be a tuple of (bool, str | None)
    assert isinstance(ok, bool)
    if not ok:
        assert error_msg is not None
        assert isinstance(error_msg, str)


def test_cors_origins_includes_lan_and_regex():
    s = Settings()
    assert "http://192.168.31.146:5173" in s.cors_origins
    assert "http://localhost:5173" in s.cors_origins
    assert s.cors_origin_regex is not None

    import re
    regex = re.compile(s.cors_origin_regex)
    assert regex.fullmatch("http://192.168.31.146:5173")
    assert regex.fullmatch("http://localhost:5173")
    assert regex.fullmatch("http://127.0.0.1:5173")
    assert not regex.fullmatch("http://malicious-site.com")


def test_production_config_rejects_insecure_defaults():
    """Fails fast when production mode has default dev secret."""
    with pytest.raises(ValueError, match="Production configuration error: SECRET_KEY"):
        Settings(
            app_env="production",
            secret_key="ops-control-tower-secure-dev-secret-key-32bytes",
            allow_sqlite_fallback=False,
            enable_demo_logins=False,
        )


def test_production_config_rejects_sqlite_fallback():
    """Fails fast when production mode allows SQLite fallback."""
    with pytest.raises(ValueError, match="allow_sqlite_fallback must be False in production"):
        Settings(
            app_env="production",
            secret_key="a" * 32,
            allow_sqlite_fallback=True,
            enable_demo_logins=False,
        )


def test_production_config_rejects_demo_logins():
    """Fails fast when production mode enables demo logins."""
    with pytest.raises(ValueError, match="enable_demo_logins must be False in production"):
        Settings(
            app_env="production",
            secret_key="a" * 32,
            allow_sqlite_fallback=False,
            enable_demo_logins=True,
        )


def test_production_config_valid_succeeds():
    """Succeeds when production mode provides compliant secrets and disables dev shortcuts."""
    s = Settings(
        app_env="production",
        secret_key="production-super-secret-cryptographic-key-32bytes",
        allow_sqlite_fallback=False,
        enable_demo_logins=False,
    )
    assert s.app_env == "production"
    assert s.allow_sqlite_fallback is False
    assert s.enable_demo_logins is False
    assert s.cookie_secure is True


@pytest.mark.asyncio
async def test_sqlite_fallback_refuses_production(monkeypatch):
    """Verifies that enable_sqlite_fallback refuses to activate in production."""
    from app.core.database import enable_sqlite_fallback
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "allow_sqlite_fallback", False)

    with pytest.raises(RuntimeError, match="SQLite fallback is forbidden in production"):
        await enable_sqlite_fallback()


@pytest.mark.asyncio
async def test_lifespan_aborts_in_production_when_db_fails(monkeypatch):
    """Verifies that FastAPI lifespan raises RuntimeError on startup in production when DB is unreachable."""
    from app.main import lifespan, app
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "allow_sqlite_fallback", False)

    async def mock_fail(timeout_seconds=2.0):
        return False, "Simulated PostgreSQL connection failure"

    monkeypatch.setattr("app.main.check_database_connection", mock_fail)

    with pytest.raises(RuntimeError, match="Halting startup. SQLite fallback is disabled in production"):
        async with lifespan(app):
            pass


def test_staging_config_rejects_insecure_defaults():
    """Fails fast when staging mode has default dev secret."""
    with pytest.raises(ValueError, match="Staging configuration error: SECRET_KEY"):
        Settings(
            app_env="staging",
            secret_key="ops-control-tower-secure-dev-secret-key-32bytes",
            allow_sqlite_fallback=False,
            enable_demo_logins=False,
        )


def test_staging_config_rejects_sqlite_fallback():
    """Fails fast when staging mode allows SQLite fallback."""
    with pytest.raises(ValueError, match="allow_sqlite_fallback must be False in staging"):
        Settings(
            app_env="staging",
            secret_key="b" * 32,
            allow_sqlite_fallback=True,
            enable_demo_logins=False,
        )


def test_staging_config_rejects_demo_logins():
    """Fails fast when staging mode enables demo logins."""
    with pytest.raises(ValueError, match="enable_demo_logins must be False in staging"):
        Settings(
            app_env="staging",
            secret_key="b" * 32,
            allow_sqlite_fallback=False,
            enable_demo_logins=True,
        )


def test_staging_config_valid_succeeds():
    """Succeeds when staging mode provides compliant secrets and disables dev shortcuts."""
    s = Settings(
        app_env="staging",
        secret_key="staging-super-secret-cryptographic-key-32bytes",
        allow_sqlite_fallback=False,
        enable_demo_logins=False,
    )
    assert s.app_env == "staging"
    assert s.allow_sqlite_fallback is False
    assert s.enable_demo_logins is False
    assert s.cookie_secure is True


@pytest.mark.asyncio
async def test_staging_lifespan_aborts_when_db_fails(monkeypatch):
    """Verifies that FastAPI lifespan raises RuntimeError on startup in staging when DB is unreachable."""
    from app.main import lifespan, app
    from app.core.config import settings

    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "allow_sqlite_fallback", False)

    async def mock_fail(timeout_seconds=2.0):
        return False, "Simulated PostgreSQL connection failure on staging"

    monkeypatch.setattr("app.main.check_database_connection", mock_fail)

    with pytest.raises(RuntimeError, match="Halting startup. SQLite fallback is disabled in staging"):
        async with lifespan(app):
            pass


