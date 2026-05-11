"""
Shell Logger - Unified Logging System
---------------------------------------
Call setup_logging() once at startup, then use get_logger(__name__) everywhere.
Existing logging.basicConfig() calls in other modules become no-ops automatically.

Usage:
    from shell_logger import get_logger
    logger = get_logger(__name__)
    logger.info("Tool executed successfully")
"""

import sys
import logging
from logging.handlers import RotatingFileHandler

_initialized = False


def setup_logging(
    level: str = "INFO",
    log_file: str = "shell_ai.log",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 3,
    console: bool = True,
):
    """Configure root logger once. Idempotent — safe to call multiple times."""
    global _initialized
    if _initialized:
        return

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicates
    root.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    if console:
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(numeric_level)
        ch.setFormatter(formatter)
        try:
            ch.stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass  # Not all streams support reconfigure
        root.addHandler(ch)

    # Rotating file handler
    try:
        fh = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        fh.setLevel(numeric_level)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    except (OSError, PermissionError) as e:
        # If we can't write to log file, just use console
        if console:
            root.handlers[0].setLevel(numeric_level)
        root.warning(f"Could not create log file {log_file}: {e}")

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Works even if setup_logging() hasn't been called."""
    return logging.getLogger(name)
