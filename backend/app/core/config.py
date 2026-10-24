import json
from typing import Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import make_url


def normalize_database_url(raw_url: str) -> str:
    """
    Normalizes a database connection URL for SQLAlchemy async drivers (asyncpg/aiosqlite).
    - Translates 'postgresql://' and 'postgres://' prefixes to 'postgresql+asyncpg://'.
    - Translates 'sqlite:///' to 'sqlite+aiosqlite:///'.
    - Converts unsupported libpq query parameters (e.g. 'sslmode=require') to asyncpg's 'ssl=require'.
    - Strips unsupported libpq query parameters like 'channel_binding' and 'gssencmode'.
    - Preserves authentication credentials, host, port, database path, and TLS security requirements.
    """
    if not raw_url:
        return raw_url

    try:
        url_obj = make_url(raw_url)
    except Exception:
        # Fallback basic translation if make_url cannot parse the input string
        url = raw_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("sqlite:///") and not url.startswith("sqlite+aiosqlite:///"):
            url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return url

    driver = url_obj.drivername
    if driver in ("postgresql", "postgres"):
        url_obj = url_obj.set(drivername="postgresql+asyncpg")
    elif driver == "sqlite":
        url_obj = url_obj.set(drivername="sqlite+aiosqlite")

    if "asyncpg" in url_obj.drivername:
        query = dict(url_obj.query)

        # Convert libpq sslmode to asyncpg ssl parameter
        if "sslmode" in query:
            mode = query.pop("sslmode")
            if isinstance(mode, (list, tuple)):
                mode = mode[0] if mode else "require"
            if "ssl" not in query:
                mode_lower = mode.lower() if isinstance(mode, str) else str(mode).lower()
                if mode_lower in ("require", "verify-ca", "verify-full", "prefer", "allow", "disable"):
                    query["ssl"] = mode_lower
                elif mode_lower in ("true", "1"):
                    query["ssl"] = "require"
                elif mode_lower in ("false", "0"):
                    query["ssl"] = "disable"
                else:
                    query["ssl"] = mode

        # If Neon host is detected and ssl was not explicitly set, ensure TLS is enabled
        if "neon.tech" in (url_obj.host or "") and "ssl" not in query:
            query["ssl"] = "require"

        # Remove unsupported libpq query parameters that asyncpg.connect rejects
        query.pop("channel_binding", None)
        query.pop("gssencmode", None)

        url_obj = url_obj.set(query=query)

    return url_obj.render_as_string(hide_password=False)


class Settings(BaseSettings):
    app_env: str = "development"
    secret_key: str = "ops-control-tower-secure-dev-secret-key-32bytes"

    # Database configuration
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ops_control"
    postgres_server: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "ops_control"

    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False

    redis_url: str = "redis://localhost:6379/0"
    cors_origins: Union[list[str], str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.31.146:5173",
    ]
    cors_origin_regex: str | None = (
        r"^https?:\/\/(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+)(:\d+)?$"
    )
    access_token_expire_minutes: int = 30
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "ops-control-tower"
    jwt_issuer: str = "ops-control-tower-auth"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    rate_limit_enabled: bool = True

    # Operational safety controls
    allow_sqlite_fallback: bool = True
    enable_demo_logins: bool = True
    allowed_hosts: Union[list[str], str] = ["*"]

    ai_provider: str = "none"
    ai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        """
        Ensures the database connection URL is formatted for an async dialect.
        Translates 'postgresql://' to 'postgresql+asyncpg://' if needed,
        and sanitizes libpq parameters (e.g. sslmode, channel_binding) for asyncpg.
        """
        return normalize_database_url(self.database_url)

    @field_validator("cors_origins", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @field_validator("allowed_hosts", mode="after")
    @classmethod
    def assemble_allowed_hosts(cls, v: list[str] | str) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except Exception:
                    pass
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        """
        Enforces strict production security, secret management, and reliability rules.
        Fails fast if production mode has missing or insecure secrets, or permits fallback.
        """
        env_lower = self.app_env.lower()
        if env_lower in ("production", "staging"):
            env_label = "Production" if env_lower == "production" else "Staging"
            # 1. Fail startup on missing or insecure production/staging secrets
            insecure_keys = {
                "ops-control-tower-secure-dev-secret-key-32bytes",
                "secret",
                "changeme",
                "development-secret-key",
            }
            if not self.secret_key or self.secret_key in insecure_keys or len(self.secret_key) < 32:
                raise ValueError(
                    f"{env_label} configuration error: SECRET_KEY must be an explicitly configured, "
                    "cryptographically strong secret of at least 32 characters."
                )

            # 2. Prevent silent database switching in production/staging
            if self.allow_sqlite_fallback:
                raise ValueError(
                    f"{env_label} configuration error: allow_sqlite_fallback must be False in {env_lower} "
                    "to prevent silent database switching and data divergence."
                )

            # 3. Disable development demo-login shortcuts in production/staging
            if self.enable_demo_logins:
                raise ValueError(
                    f"{env_label} configuration error: enable_demo_logins must be False in {env_lower}."
                )

            # 4. Enforce secure cookies in production/staging
            if not self.cookie_secure:
                self.cookie_secure = True

        return self


settings = Settings()
