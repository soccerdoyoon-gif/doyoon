from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.stats import ads_summary, daily_series
from app.api.serializers import content_dict
from app.core.database import get_db
from app.core.timeutil import local_tz, to_local, utcnow
from app.models import ContentItem, Insight, PendingAction

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

    def latest(kind):
        return db.scalars(select(Insight).where(Insight.kind == kind).order_by(Insight.id.desc()).limit(1)).first()

    content_ins, ads_ins, trend_ins = latest("content"), latest("ads"), latest("trend")
    next_actions = []
    if content_ins:
        next_actions += content_ins.data.get("recommendations_for_next_content", [])[:3]
    if ads_ins:
        next_actions += [f"{a.get('name')}: {a.get('recommendation')}" for a in ads_ins.data.get("ads", []) if a.get("verdict") in ("poor", "good")][:3]
    return {
        "ai": {
            "content_summary": content_ins.summary if content_ins else None,
            "ads_summary": ads_ins.summary if ads_ins else None,
            "trend_summary": trend_ins.summary if trend_ins else None,
            "source": content_ins.source if content_ins else None,
            "next_actions": next_actions,
        },
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
