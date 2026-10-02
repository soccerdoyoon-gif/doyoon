from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_or_404
from app.api.schemas import ScheduleIn
from app.api.serializers import content_dict
from app.core.database import get_db
from app.core.timeutil import to_naive_utc
from app.models import Campaign, ContentItem
from app.services import content_service as cs

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("")
def calendar(start: datetime, end: datetime, db: Session = Depends(get_db)):
    s, e = to_naive_utc(start), to_naive_utc(end)
    q = select(ContentItem).where(
        ContentItem.status != "REJECTED",
        or_(
            and_(ContentItem.published_at >= s, ContentItem.published_at < e),
            and_(ContentItem.published_at.is_(None), ContentItem.scheduled_at >= s, ContentItem.scheduled_at < e),
            and_(ContentItem.scheduled_at.is_(None), ContentItem.published_at.is_(None), ContentItem.suggested_time >= s, ContentItem.suggested_time < e),
        ),
    )
    campaigns = {c.id: c.name for c in db.query(Campaign).all()}
    out = []
    for c in db.scalars(q).all():
        d = content_dict(c)
        d["calendar_time"] = d["published_at"] or d["scheduled_at"] or d["suggested_time"]
        d["campaign_name"] = campaigns.get(c.campaign_id)
        out.append(d)
    out.sort(key=lambda x: x["calendar_time"] or "")
    return out


@router.patch("/{cid}")
def move(cid: int, body: ScheduleIn, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    try:
        cs.reschedule(db, item, body.scheduled_at)
    except cs.WorkflowError as exc:
        raise HTTPException(400, str(exc)) from exc
    db.commit()
    return content_dict(item)
