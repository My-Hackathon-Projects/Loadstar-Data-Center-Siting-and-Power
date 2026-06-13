"""Tests for the optimizer LRU cache.

Two identical POSTs must produce identical responses, but the underlying LP
solver must run only once. Cache hit/miss is asserted via `caplog` reading the
structured `optimize.solved` log records.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.api.services import optimizer_service
from backend.api.services.result_cache import (
    LruResultCache,
    get_result_cache,
    reset_result_cache_for_tests,
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_result_cache_for_tests()
    yield TestClient(app)
    reset_result_cache_for_tests()


def test_lru_cache_hits_on_repeated_optimize(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "cell_id": "8508c683fffffff",
        "load_mw": 280,
        "load_profile": "flat_24_7",
    }
    call_count = {"n": 0}
    real_solver = optimizer_service.optimize_supply_mix

    def counting_solver(*args, **kwargs):
        call_count["n"] += 1
        return real_solver(*args, **kwargs)

    monkeypatch.setattr(optimizer_service, "optimize_supply_mix", counting_solver)

    caplog.set_level(logging.INFO, logger="loadstar.optimizer")
    first = client.post("/optimize/supply-mix", json=payload)
    second = client.post("/optimize/supply-mix", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["cache_key"] == second.json()["cache_key"]
    # Solver invoked exactly once across two identical requests.
    assert call_count["n"] == 1

    cache_hits = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "optimize.solved"
        and getattr(record, "cache_hit", False) is True
    ]
    cache_misses = [
        record
        for record in caplog.records
        if getattr(record, "event", None) == "optimize.solved"
        and getattr(record, "cache_hit", False) is False
    ]
    assert len(cache_misses) == 1
    assert len(cache_hits) == 1


def test_lru_cache_evicts_least_recently_used() -> None:
    cache: LruResultCache = LruResultCache(maxsize=2)
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.get("a") == 1  # promotes "a"
    cache.set("c", 3)  # should evict "b" (least recently used)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_lru_cache_stats_increment() -> None:
    cache: LruResultCache = LruResultCache(maxsize=4)
    cache.set("k", "v")
    assert cache.get("k") == "v"
    assert cache.get("missing") is None
    stats = cache.stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["size"] == 1
    assert stats["maxsize"] == 4


def test_get_result_cache_returns_lru_when_redis_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    reset_result_cache_for_tests()
    cache = get_result_cache()
    assert isinstance(cache, LruResultCache)
