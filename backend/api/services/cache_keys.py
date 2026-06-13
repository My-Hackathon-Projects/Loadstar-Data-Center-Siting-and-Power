"""Deterministic cache-key helpers for API service responses."""

import hashlib
import json
from collections.abc import Sequence
from typing import Any, cast

from pydantic import BaseModel


def build_cache_key(namespace: str, *parts: object) -> str:
    """Return a stable cache key for a deterministic API response."""

    payload = [_jsonable(part) for part in parts]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]
    return f"{namespace}:{digest}"


def _jsonable(value: object) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        return {str(key): _jsonable(item) for key, item in mapping.items()}
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, set):
        values = cast(set[object], value)
        return sorted(_jsonable(item) for item in values)
    if isinstance(value, Sequence):
        values = cast(Sequence[object], value)
        return [_jsonable(item) for item in values]
    return str(value)
