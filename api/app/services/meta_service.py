from typing import Any

from engine.assumptions import ASSUMPTIONS


def get_assumptions() -> dict[str, Any]:
    """Return public assumptions for API consumers."""

    return ASSUMPTIONS
