"""게시된 콘텐츠 성과 주기적 수집. 제공되지 않는 지표는 null 로 저장."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.mock import MockConnector
from app.connectors.registry import get_connector
from app.core.timeutil import utcnow
from app.models import ContentItem, PostMetrics
from app.services.events import log_event

MIN_INTERVAL = timedelta(minutes=55)
LOOKBACK = timedelta(days=30)


def collect_metrics(db: Session, now=None, force: bool = False) -> dict:
    now = now or utcnow()
    items = db.scalars(
        select(ContentItem).where(ContentItem.status == "PUBLISHED", ContentItem.published_at >= now - LOOKBACK)
    ).all()
    collected, skipped, errors = 0, 0, 0
    for item in items:
        last = item.metrics[-1] if item.metrics else None
        if not force and last and now - last.collected_at < MIN_INTERVAL:
            skipped += 1
            continue
        connector = get_connector(item.platform)
        if item.is_dry_run or connector.mode == "mock":
            connector = MockConnector(item.platform)
        hours = max(0.0, (now - item.published_at).total_seconds() / 3600)
        try:
            m = connector.get_metrics(item.external_id, hours_since_publish=hours)
        except ConnectorError as exc:
            errors += 1
            log_event("api_error", f"성과 수집 실패 #{item.id} {item.platform}: {exc}", {"response": exc.response}, level="WARNING", db=db)
            continue
        item.metrics.append(
            PostMetrics(
                collected_at=now,
                impressions=m.impressions,
                reach=m.reach,
                views=m.views,
                likes=m.likes,
                comments=m.comments,
                shares=m.shares,
                saves=m.saves,
                clicks=m.clicks,
                followers_gained=m.followers_gained,
                engagement_rate=m.engagement_rate,
                source="mock" if isinstance(connector, MockConnector) else m.source,
            )
        )
        collected += 1
    if collected or errors:
        log_event("api_response", f"성과 수집: {collected}건 저장, {errors}건 실패, {skipped}건 건너뜀", db=db)
    db.commit()
    return {"collected": collected, "skipped": skipped, "errors": errors}
