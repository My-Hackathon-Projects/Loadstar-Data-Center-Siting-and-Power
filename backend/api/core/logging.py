"""Application logging configuration."""

import logging


def configure_logging(level_name: str) -> None:
    """Configure process logging from settings."""

    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=level,
    )
