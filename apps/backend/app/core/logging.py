"""Minimal shared application logging; never log learner content or credentials."""

import logging


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # SQL logs may include sensitive parameters; keep them disabled by default.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
