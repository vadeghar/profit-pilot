"""
Redis-backed cache with graceful degradation: if Redis is disabled or
unreachable, every function here just behaves as a permanent cache miss /
no-op instead of raising, so the app always works whether or not Redis is
running -- cache is a performance layer, never a hard dependency.

Enable with CACHE_ENABLED=true and point REDIS_URL at your Redis instance
(see backend/.env.example). Defaults to disabled so local dev doesn't need
Redis just to run the app.
"""
import hashlib
import json
import logging
import os
from typing import Any, Optional

import redis

logger = logging.getLogger(__name__)

CACHE_ENABLED = os.getenv("CACHE_ENABLED", "false").lower() == "true"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_client: Optional["redis.Redis"] = None
_client_checked = False


def _get_client() -> Optional["redis.Redis"]:
    """Lazily create and health-check the Redis client. Returns None if the
    cache is disabled or Redis can't be reached -- callers treat None as
    "everything is a cache miss" rather than an error."""
    global _client, _client_checked
    if not CACHE_ENABLED:
        return None
    if _client_checked:
        return _client
    _client_checked = True
    try:
        client = redis.from_url(REDIS_URL, socket_connect_timeout=1, socket_timeout=1, decode_responses=True)
        client.ping()
        _client = client
    except Exception as exc:  # noqa: BLE001 -- cache must never break the app
        logger.warning("Redis unavailable (%s) -- continuing without cache", exc)
        _client = None
    return _client


def get_json(key: str) -> Optional[Any]:
    client = _get_client()
    if client is None:
        return None
    try:
        raw = client.get(key)
        return json.loads(raw) if raw is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis GET failed for %s: %s", key, exc)
        return None


def set_json(key: str, value: Any, ttl_seconds: Optional[int]) -> None:
    """ttl_seconds=None caches indefinitely -- use only for results that can
    never change (e.g. a backtest over a fully historical date range)."""
    client = _get_client()
    if client is None:
        return
    try:
        payload = json.dumps(value)
        if ttl_seconds is None:
            client.set(key, payload)
        else:
            client.set(key, payload, ex=ttl_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis SET failed for %s: %s", key, exc)


def acquire_lock(key: str, ttl_seconds: int = 30) -> bool:
    """Best-effort lock so concurrent identical requests don't all recompute
    the same expensive result. Returns True if the lock was acquired -- also
    returns True when Redis is unavailable, so callers always proceed rather
    than deadlock; this only protects an optimization, never correctness."""
    client = _get_client()
    if client is None:
        return True
    try:
        return bool(client.set(key, "1", nx=True, ex=ttl_seconds))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis lock failed for %s: %s", key, exc)
        return True


def release_lock(key: str) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.delete(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Redis unlock failed for %s: %s", key, exc)


def params_hash(**params: Any) -> str:
    """Short, stable, order-independent hash of arbitrary keyword params --
    e.g. margin_per_unit, units, target_pct, stop_pct -- for cache-key
    suffixes, so two different parameter sets never collide on one key."""
    canonical = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha1(canonical.encode()).hexdigest()[:10]
