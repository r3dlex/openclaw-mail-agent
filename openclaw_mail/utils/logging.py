"""Centralized logging setup.

All loggers write to both stdout and a file in ``logs/``.  A shared
``openclaw.log`` aggregates all modules; per-module files (e.g.
``tidy.log``) are optional.

→ Log directory: managed via LOG_DIR in config.py
"""

import logging
import sys

from openclaw_mail.config import LOG_DIR, LOG_LEVEL

_MAIN_LOG_FILE = "openclaw.log"  # Aggregate log for all modules


def get_logger(name: str, log_file: str | None = None) -> logging.Logger:
    """Create a logger that writes to stdout and file(s).

    Parameters
    ----------
    name:
        Logger name (shown in log lines, e.g. ``"tidy"``, ``"himalaya"``).
    log_file:
        Optional per-module log file (e.g. ``"tidy.log"``).  When provided
        the logger writes to *both* this file and the shared
        ``openclaw.log``.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))
    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handlers — always write to the shared openclaw.log
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    main_fh = logging.FileHandler(LOG_DIR / _MAIN_LOG_FILE)
    main_fh.setFormatter(fmt)
    logger.addHandler(main_fh)

    # Per-module log file (optional, in addition to the shared one)
    if log_file and log_file != _MAIN_LOG_FILE:
        fh = logging.FileHandler(LOG_DIR / log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    return logger
