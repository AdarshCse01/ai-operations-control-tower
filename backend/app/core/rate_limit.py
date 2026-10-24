"""
Rate limiting configuration using slowapi.
Uses client IP as key. Attempts connection to Redis if configured;
falls back safely to in-memory storage for local offline development.
"""
import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import settings

logger = logging.getLogger(__name__)


_active_storage_type: str = "memory"


def _resolve_storage_uri() -> str:
    """
    Checks if configured Redis instance is accessible.
    If unreachable (e.g. native Windows development without Redis running),
    safely falls back to in-memory storage.
    """
    global _active_storage_type
    if settings.redis_url:
        try:
            import redis
            client = redis.Redis.from_url(settings.redis_url, socket_timeout=0.5)
            client.ping()
            _active_storage_type = "redis"
            logger.info("Connected to Redis for rate limiting at %s", settings.redis_url)
            return settings.redis_url
        except Exception as exc:
            logger.info(
                "Redis server not reachable at %s (%s). Using in-memory limiter.",
                settings.redis_url,
                exc.__class__.__name__,
            )
            _active_storage_type = "memory"
            return "memory://"
    _active_storage_type = "memory"
    return "memory://"


_resolved_uri = _resolve_storage_uri()

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.rate_limit_enabled,
    storage_uri=_resolved_uri,
)


def get_limiter_storage_type() -> str:
    """Returns 'redis' if Redis backend is active, or 'memory' if in-memory fallback is active."""
    return _active_storage_type
