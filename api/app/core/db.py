from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from api.app.core.config import get_settings


def create_sync_engine() -> Engine:
    """Create a synchronous SQLAlchemy 2.0 engine.

    Production Postgres URLs should use psycopg 3, for example:
    `postgresql+psycopg://loadstar:loadstar@localhost:5432/loadstar`.
    """

    return create_engine(get_settings().database_url, future=True)
