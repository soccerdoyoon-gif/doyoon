"""File logging with credential redaction (logs/app.log)."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.config import get_settings
from app.core.redact import redact_text

_configured = False


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover
            return True
        record.msg = redact_text(msg)
        record.args = None
        return True


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root = logging.getLogger("app")
    root.setLevel(logging.INFO)
    file_handler = RotatingFileHandler(
        settings.log_dir / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.addFilter(RedactingFilter())
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.addFilter(RedactingFilter())
    root.addHandler(file_handler)
    root.addHandler(console)
    root.propagate = False
    # httpx logs full URLs (which may contain tokens) at INFO — keep it quiet.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"app.{name}")
