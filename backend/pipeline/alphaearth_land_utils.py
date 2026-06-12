"""Small validation helpers for AlphaEarth JSON and numeric records."""

from __future__ import annotations


def required_string(value: object, field_name: str) -> str:
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"Expected non-empty string field {field_name}.")


def required_float(value: object, field_name: str) -> float:
    parsed = optional_float(value)
    if parsed is None:
        raise ValueError(f"Expected numeric field {field_name}.")
    return parsed


def required_binary(value: object, field_name: str) -> int:
    parsed = optional_int(value)
    if parsed in {0, 1}:
        return parsed
    raise ValueError(f"Expected binary field {field_name}.")


def optional_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def optional_string(value: object, default: str) -> str:
    return value if isinstance(value, str) and value else default


def clamp01(value: float) -> float:
    return min(max(value, 0.0), 1.0)
