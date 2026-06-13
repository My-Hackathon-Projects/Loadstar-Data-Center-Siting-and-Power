"""Tiny value-parsing utilities shared by `_feature_context.py` and
`_feature_blending.py`. Keeping these in their own module avoids a circular
import between the loader and the blender.
"""

from __future__ import annotations


def required_float(value: object, field_name: str) -> float:
    """Coerce to float or raise; bools are rejected so `True` is not silently 1.0."""

    parsed = optional_float(value)
    if parsed is None:
        raise ValueError(f"Expected numeric field {field_name}.")
    return parsed


def optional_float(value: object) -> float | None:
    """Coerce to float, returning None for missing/non-numeric values."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def optional_string(value: object, default: str) -> str:
    """Return `value` if it is a non-empty string, else `default`."""

    return value if isinstance(value, str) and value else default


def clamp01(value: float) -> float:
    """Clamp a float to the [0, 1] range, used after blending and normalization."""

    return min(max(value, 0.0), 1.0)
