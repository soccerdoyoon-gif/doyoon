"""Event logging: logs/app.log + DB(event_logs). 비밀값은 자동 마스킹."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.core.redact import redact, redact_text
from app.models import EventLog

logger = get_logger("events")


def log_event(
    category: str,
    message: str,
    details: dict[str, Any] | None = None,
    level: str = "INFO",
    db: Session | None = None,
) -> None:
    safe_details = redact(details or {})
    safe_message = redact_text(message)
    getattr(logger, level.lower(), logger.info)(f"[{category}] {safe_message}")
    own = db is None
    session = db or SessionLocal()
    try:
        session.add(EventLog(category=category, level=level, message=safe_message, details=safe_details))
        if own:
            session.commit()
        else:
            session.flush()
    except Exception as exc:  # pragma: no cover - logging must never break the app
        logger.error(f"failed to write event log: {exc}")
        if own:
            session.rollback()
    finally:
        if own:
            session.close()
