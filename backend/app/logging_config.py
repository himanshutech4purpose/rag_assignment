"""Structured logging configuration for the application."""

import logging
import sys

from app.config import get_settings


def configure_logging() -> None:
    """Configure root logger with a consistent format and level."""
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Use a simple but informative format. In production this could be replaced
    # with a JSON formatter for better observability.
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(log_level)
    root.handlers = [handler]

    # Reduce noise from third-party libraries.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance for the given module name."""
    return logging.getLogger(name)
