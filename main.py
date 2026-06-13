"""Repo-root entry point for `uvicorn main:app --reload`.

The FastAPI application is defined in `backend/api/main.py`; this module is a
one-line re-export so the canonical run command works from the project root:

    uvicorn main:app --reload

Keep the real application code under `backend/api/` — this file should not
grow logic of its own.
"""

from backend.api.main import app

__all__ = ["app"]
