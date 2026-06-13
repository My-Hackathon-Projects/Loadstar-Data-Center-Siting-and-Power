"""Result cache for the optimizer endpoint.

`build_cache_key("optimize.supply_mix", request, site)` already produces a
deterministic key on every request. This module wraps that key with an actual
storage layer so repeated identical requests skip the LP solve.

Two backends:

- `LruResultCache` (default): in-process `OrderedDict`, no TTL since results
  are deterministic by construction. Threadsafe for FastAPI's threadpool
  endpoints.
- `RedisResultCache`: lazy-imported `redis-py` adapter for multi-process
  deployments. Activates only when `REDIS_URL` is set; falls back to LRU on
  any connection error.

Public surface: `get_result_cache() -> ResultCache`. The factory is module-
level cached (`functools.lru_cache(maxsize=1)`) so every service shares the
same instance across requests.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from collections.abc import Callable
from functools import lru_cache
from threading import Lock
from typing import Any, Protocol, runtime_checkable

from backend.api.core.config import get_settings

logger = logging.getLogger("loadstar.cache")

# Bound the in-process cache so a long-running demo cannot grow unbounded.
# 256 entries comfortably covers the 280 MW × 7 layer × multiple workload
# combinations a judge might explore during a rehearsal.
_DEFAULT_LRU_MAX_SIZE = 256


@runtime_checkable
class ResultCache(Protocol):
    """Minimal cache contract used by the optimizer service."""

    def get(self, key: str) -> Any | None:
        """Return the cached value for `key`, or None on miss."""
        ...

    def set(self, key: str, value: Any) -> None:
        """Store `value` under `key`."""
        ...

    def stats(self) -> dict[str, int]:
        """Return hit/miss/size counters for diagnostics."""
        ...


class LruResultCache:
    """Thread-safe LRU cache backed by `OrderedDict`."""

    def __init__(self, maxsize: int = _DEFAULT_LRU_MAX_SIZE) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[str, Any] = OrderedDict()
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key not in self._store:
                self._misses += 1
                return None
            # Move to end so least-recently-used falls off first.
            self._store.move_to_end(key)
            self._hits += 1
            return self._store[key]

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = value
            self._store.move_to_end(key)
            while len(self._store) > self._maxsize:
                self._store.popitem(last=False)

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "hits": self._hits,
                "misses": self._misses,
                "size": len(self._store),
                "maxsize": self._maxsize,
            }


class RedisResultCache:  # pragma: no cover - exercised when REDIS_URL is set.
    """Redis-backed cache. Activated by setting `REDIS_URL` in `.env`."""

    def __init__(self, redis_url: str, prefix: str = "loadstar:") -> None:
        # Lazy import keeps `redis-py` an optional dep; users without Redis
        # never see the import. Cast to `Any` because redis-py does not ship
        # py.typed stubs that pyright recognizes in strict mode.
        from importlib import import_module

        redis_module: Any = import_module("redis")
        self._client: Any = redis_module.Redis.from_url(redis_url, decode_responses=False)
        self._prefix = prefix
        self._hits = 0
        self._misses = 0
        # Probe the connection up front so a mis-configured DSN fails the
        # factory, not the first cache get/set.
        self._client.ping()

    def get(self, key: str) -> Any | None:
        import pickle  # noqa: S403 - values are produced by us, not user input.

        raw: Any = self._client.get(self._prefix + key)
        if raw is None:
            self._misses += 1
            return None
        self._hits += 1
        return pickle.loads(raw)  # noqa: S301 - we control what we set.

    def set(self, key: str, value: Any) -> None:
        import pickle

        self._client.set(self._prefix + key, pickle.dumps(value))

    def stats(self) -> dict[str, int]:
        return {"hits": self._hits, "misses": self._misses}


def _build_cache(_factory: Callable[[], ResultCache] | None = None) -> ResultCache:
    """Choose the backend implementation based on Settings."""

    redis_url = get_settings().redis_url
    if not redis_url:
        return LruResultCache()
    try:
        return RedisResultCache(redis_url)
    except Exception as exc:  # noqa: BLE001 - logged + LRU fallback.
        logger.warning(
            "result_cache.redis_unreachable",
            extra={
                "event": "result_cache.redis_unreachable",
                "error": type(exc).__name__,
            },
        )
        return LruResultCache()


@lru_cache(maxsize=1)
def get_result_cache() -> ResultCache:
    """Return the process-wide result cache singleton."""

    return _build_cache()


def reset_result_cache_for_tests() -> None:
    """Clear the cached singleton so tests can install a fresh backend."""

    get_result_cache.cache_clear()
