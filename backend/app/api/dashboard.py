from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.stats import ads_summary, daily_series
from app.api.serializers import content_dict
from app.core.database import get_db
from app.core.timeutil import local_tz, to_local, utcnow
from app.models import ContentItem, PendingAction

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(days: int = 14, db: Session = Depends(get_db)):
    tz = local_tz()
    today = to_local(utcnow()).date()

    def utc(d, t=time.min):
        return datetime.combine(d, t, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)

    t0, t1 = utc(today), utc(today + timedelta(days=1))
    week_start = today - timedelta(days=today.weekday())
    w0, w1 = utc(week_start), utc(week_start + timedelta(days=7))

    def count(*conds):
        return db.scalar(select(func.count()).select_from(ContentItem).where(*conds)) or 0

    today_scheduled = db.scalars(
        select(ContentItem).where(ContentItem.status == "SCHEDULED", ContentItem.scheduled_at >= t0, ContentItem.scheduled_at < t1).order_by(ContentItem.scheduled_at)
    ).all()
    ads7 = ads_summary(db, today - timedelta(days=6), today)
    return {
        "today": today.isoformat(),
        "cards": {
            "today_scheduled": len(today_scheduled),
            "published_today": count(ContentItem.status == "PUBLISHED", ContentItem.published_at >= t0, ContentItem.published_at < t1),
            "failed": count(ContentItem.status == "FAILED"),
            "pending_review": count(ContentItem.status == "READY_FOR_REVIEW"),
            "week_content": count(
                ContentItem.status.in_(["SCHEDULED", "PUBLISHED", "FAILED"]),
                func.coalesce(ContentItem.published_at, ContentItem.scheduled_at) >= w0,
                func.coalesce(ContentItem.published_at, ContentItem.scheduled_at) < w1,
            ),
            "pending_ad_actions": db.scalar(select(func.count()).select_from(PendingAction).where(PendingAction.status == "PENDING")) or 0,
        },
        "ads_7d": ads7,
        "today_items": [content_dict(c) for c in today_scheduled],
        "series": daily_series(db, days),
    }
