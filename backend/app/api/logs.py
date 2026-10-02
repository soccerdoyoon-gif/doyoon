from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import to_dict
from app.core.database import get_db
from app.models import EventLog

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("")
def logs(category: str | None = None, level: str | None = None, limit: int = 200, db: Session = Depends(get_db)):
    q = select(EventLog).order_by(EventLog.id.desc()).limit(min(limit, 1000))
    if category:
        q = q.where(EventLog.category == category)
    if level:
        q = q.where(EventLog.level == level)
    return [to_dict(e) for e in db.scalars(q).all()]
