from typing import Any

from fastapi import APIRouter

from api.app.core.config import get_settings
from api.app.services.meta_service import get_assumptions

router = APIRouter(tags=["meta"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return process health and active data mode."""

    return {"status": "ok", "data_mode": get_settings().data_mode}


@router.get("/assumptions")
def assumptions() -> dict[str, Any]:
    """Return the public assumptions used by the fixture skeleton."""

    return get_assumptions()
