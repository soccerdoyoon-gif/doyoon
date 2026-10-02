from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.analyzer import analyze_content, generate_strategy
from app.analytics.stats import content_performance, platform_summary
from app.api.serializers import to_dict
from app.core.database import get_db
from app.core.timeutil import utcnow
from app.models import Insight
from app.services.metrics_collector import collect_metrics

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/content")
def content_analytics(days: int = 14, platform: str = "all", db: Session = Depends(get_db)):
    rows = content_performance(db, utcnow() - timedelta(days=days), utcnow(), platform)
    return {"rows": rows, "by_platform": platform_summary(rows)}


@router.post("/analytics/collect")
def collect(db: Session = Depends(get_db)):
    return collect_metrics(db, force=True)


@router.post("/analytics/analyze")
def analyze(days: int = 14, db: Session = Depends(get_db)):
    return to_dict(analyze_content(db, days))


@router.get("/insights")
def insights(kind: str | None = None, limit: int = 20, db: Session = Depends(get_db)):
    q = select(Insight).order_by(Insight.id.desc()).limit(min(limit, 100))
    if kind:
        q = q.where(Insight.kind == kind)
    return [to_dict(i) for i in db.scalars(q).all()]


@router.post("/strategy")
def strategy(db: Session = Depends(get_db)):
    try:
        return to_dict(generate_strategy(db))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
