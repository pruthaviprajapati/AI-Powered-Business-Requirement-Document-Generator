"""
Centralized logging configuration.
Sets up file + console handlers so every module
imports the same configured logger.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.core.config import settings


def setup_logging() -> None:
    """Configure root logger with rotating file and console handlers."""
    # Ensure logs directory exists
    Path(settings.LOGS_DIR).mkdir(parents=True, exist_ok=True)

    log_format = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # ── Console handler ───────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)

    # ── Rotating file handler (5 MB × 5 backup files) ────────────
    file_handler = RotatingFileHandler(
        filename=settings.LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)

    # Avoid adding duplicate handlers on hot-reload
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (call after setup_logging has run)."""
    return logging.getLogger(name)
