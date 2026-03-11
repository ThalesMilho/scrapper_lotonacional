"""
config/logging_setup.py
───────────────────────
Configures the root logger with:
  - Timestamp | Level | Logger name | Message format
  - Console handler (coloured via optional colorama)
  - File handler (UTF-8, rotating)
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False


class _ColourFormatter(logging.Formatter):
    _COLOURS = {
        logging.DEBUG:    "\x1b[37m",    # white
        logging.INFO:     "\x1b[32m",    # green
        logging.WARNING:  "\x1b[33m",    # yellow
        logging.ERROR:    "\x1b[31m",    # red
        logging.CRITICAL: "\x1b[41m",    # red background
    }
    _RESET = "\x1b[0m"

    def format(self, record: logging.LogRecord) -> str:
        colour = self._COLOURS.get(record.levelno, "")
        record.levelname = f"{colour}{record.levelname:<8}{self._RESET}"
        return super().format(record)


_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_DATE   = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO", log_file: str | None = None) -> None:
    """Call once at startup. Safe to call multiple times (idempotent)."""
    root = logging.getLogger()

    # Avoid adding duplicate handlers when called multiple times (e.g. in tests)
    if root.handlers:
        return

    root.setLevel(getattr(logging, level, logging.INFO))

    # ── Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(
        _ColourFormatter(_FORMAT, datefmt=_DATE)
        if _HAS_COLOR
        else logging.Formatter(_FORMAT, datefmt=_DATE)
    )
    root.addHandler(console)

    # ── File handler
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE))
        root.addHandler(fh)
