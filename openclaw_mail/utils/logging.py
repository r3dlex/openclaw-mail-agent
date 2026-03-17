"""Centralized logging setup."""

import logging
import sys
from pathlib import Path

from openclaw_mail.config import LOG_DIR, LOG_LEVEL


def get_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """Create a logger that writes to stdout and optionally to a file."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    if log_file:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(LOG_DIR / log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
