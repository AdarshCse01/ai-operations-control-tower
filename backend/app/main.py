import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.config import settings
from app.core.database import (
    check_database_connection,
    dispose_engine,
    enable_sqlite_fallback,
    get_active_backend,
    get_database_diagnostics,
    is_fallback_active,
)
from app.core.rate_limit import get_limiter_storage_type, limiter
from app.api.v1.router import api_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Verify primary database; fail fast in production or activate dev SQLite fallback
    db_ok, db_msg = await check_database_connection(timeout_seconds=2.0)
    if not db_ok:
        if settings.app_env.lower() in ("production", "staging") or not settings.allow_sqlite_fallback:
            logger.critical(
                "FATAL: Primary database connection failed in %s mode (%s). "
                "Startup aborted to prevent silent database switching and data divergence.",
                settings.app_env,
                db_msg,
            )
            raise RuntimeError(
                f"Database connection failed in {settings.app_env} mode: {db_msg}. "
                f"Halting startup. SQLite fallback is disabled in {settings.app_env}."
            )
        logger.warning(
            "OPERATIONAL NOTICE: Primary database connection unavailable (%s). "
            "Activating local persistent SQLite fallback database for development.",
            db_msg,
        )
        await enable_sqlite_fallback()
    yield
    # Shutdown: Clean up any active database connection pools.
    await dispose_engine()


app = FastAPI(
    title="AI Operations Control Tower",
    description="Operations risk detection and human-approved recommendations.",
    version="0.1.0",
    lifespan=lifespan,
)

# Attach slowapi rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers_and_logging_middleware(request: Request, call_next):
    """
    Applies defense-in-depth HTTP security headers and records structured request logs.
    Strictly excludes credentials, tokens, cookies, and sensitive payload bodies from logs.
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Add standard OWASP security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    # Disable deprecated legacy browser XSS auditor in favor of robust Content Security Policy
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' http: https: ws: wss:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    client_ip = request.client.host if request.client else "unknown"
    logger.info(
        'HTTP %s "%s %s" %d (%.2fms) [client=%s]',
        request.scope.get("http_version", "1.1"),
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        client_ip,
    )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Ensures unhandled server errors return clean JSON responses through CORSMiddleware without exposing stack traces."""
    logger.exception("Unhandled server exception: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please check database configuration or logs."},
    )


# Configure TrustedHostMiddleware if configured
if "*" not in settings.allowed_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

# Configure CORS with credentials support for session cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["system"])
async def health():
    """Liveness probe: verifies service process is active."""
    return {
        "status": "ok",
        "service": "operations-control-tower",
        "environment": settings.app_env,
    }


@app.get("/ready", tags=["system"])
async def ready(response: Response):
    """
    Readiness probe: verifies operational dependencies.
    Returns HTTP 200 if connected or running valid dev fallback, or HTTP 503 if unavailable.
    """
    db_ok, db_msg = await check_database_connection(timeout_seconds=1.5)
    fallback = is_fallback_active()
    active_backend = get_active_backend()
    is_ready = db_ok or fallback

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    storage_type = get_limiter_storage_type()

    return {
        "status": "ready" if is_ready else "unavailable",
        "environment": settings.app_env,
        "backend": active_backend,
        "fallback_active": fallback,
        "dependencies": {
            "database": "connected" if db_ok else ("sqlite-fallback" if fallback else "unreachable"),
            "backend": active_backend,
            "rate_limiter": storage_type,
            "database_error": db_msg if not is_ready else None,
        },
    }


@app.get("/health/diagnostics", tags=["system"])
async def diagnostics():
    """Safe operational diagnostic endpoint without exposing credentials or internal paths."""
    return {
        "environment": settings.app_env,
        "database": get_database_diagnostics(),
        "rate_limiter": {"storage": get_limiter_storage_type()},
        "security": {
            "cookie_secure": settings.cookie_secure,
            "cookie_samesite": settings.cookie_samesite,
            "demo_logins_enabled": settings.enable_demo_logins and settings.app_env.lower() not in ("production", "staging"),
            "sqlite_fallback_allowed": settings.allow_sqlite_fallback,
        },
    }

