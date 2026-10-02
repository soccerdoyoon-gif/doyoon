"""성과 집계 함수 — 대시보드, AI 분석, 리포트, AI Marketing Manager 가 공통으로 사용.

값이 없는(null) 지표는 0 으로 바꾸지 않고 그대로 None 으로 둡니다.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import to_local, utcnow
from app.models import AdEntity, AdInsightDaily, ContentItem, PostMetrics

METRIC_KEYS = ("impressions", "reach", "views", "likes", "comments", "shares", "saves", "clicks", "followers_gained")


def _sum(values: Iterable[float | int | None]) -> float | int | None:
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def _div(a: float | None, b: float | None, mult: float = 1.0, nd: int = 3) -> float | None:
    if a is None or not b:
        return None
    return round(a / b * mult, nd)


def latest_metrics(db: Session, content_ids: list[int]) -> dict[int, PostMetrics]:
    if not content_ids:
        return {}
    sub = (
        select(PostMetrics.content_id, func.max(PostMetrics.id).label("mid"))
        .where(PostMetrics.content_id.in_(content_ids))
        .group_by(PostMetrics.content_id)
        .subquery()
    )
    rows = db.scalars(select(PostMetrics).join(sub, PostMetrics.id == sub.c.mid)).all()
    return {m.content_id: m for m in rows}


def content_performance(
    db: Session, since: datetime, until: datetime | None = None, platform: str | None = None
) -> list[dict[str, Any]]:
    until = until or utcnow()
    q = select(ContentItem).where(
        ContentItem.status == "PUBLISHED",
        ContentItem.published_at >= since,
        ContentItem.published_at <= until,
    )
    if platform and platform != "all":
        q = q.where(ContentItem.platform == platform)
    items = db.scalars(q.order_by(ContentItem.published_at)).all()
    metrics = latest_metrics(db, [i.id for i in items])
    rows = []
    for it in items:
        m = metrics.get(it.id)
        local = to_local(it.published_at) if it.published_at else None
        row = {
            "id": it.id,
            "platform": it.platform,
            "content_type": it.content_type,
            "title": it.title,
            "hook": it.hook,
            "caption": (it.caption or "")[:300],
            "cta": it.cta,
            "hashtags": it.hashtags,
            "published_at_local": local.strftime("%Y-%m-%d %H:%M") if local else None,
            "weekday": local.strftime("%a") if local else None,
            "hour": local.hour if local else None,
            "is_dry_run": it.is_dry_run,
            "data_source": (m.source if m else None),
        }
        for k in METRIC_KEYS:
            row[k] = getattr(m, k) if m else None
        row["engagement_rate"] = m.engagement_rate if m else None
        rows.append(row)
    return rows


def platform_summary(rows: list[dict]) -> dict[str, dict[str, Any]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["platform"]].append(r)
    out = {}
    for platform, items in groups.items():
        summary: dict[str, Any] = {"posts": len(items)}
        for k in METRIC_KEYS:
            summary[k] = _sum(r[k] for r in items)
        ers = [r["engagement_rate"] for r in items if r["engagement_rate"] is not None]
        summary["avg_engagement_rate"] = round(sum(ers) / len(ers), 3) if ers else None
        summary["mock_data"] = any(r["data_source"] == "mock" for r in items)
        out[platform] = summary
    return out


def engagement_total(row: dict) -> int | None:
    return _sum(row.get(k) for k in ("likes", "comments", "shares", "saves"))


def rank_content(rows: list[dict], n: int = 3) -> tuple[list[dict], list[dict]]:
    scored = [r for r in rows if r.get("engagement_rate") is not None]
    scored.sort(key=lambda r: r["engagement_rate"], reverse=True)
    best = scored[:n]
    worst = list(reversed(scored[-n:])) if len(scored) > n else []
    return best, worst


def _ads_totals(rows: list[AdInsightDaily]) -> dict[str, Any]:
    spend = _sum(r.spend for r in rows)
    impressions = _sum(r.impressions for r in rows)
    clicks = _sum(r.clicks for r in rows)
    conversions = _sum(r.conversions for r in rows)
    value = _sum(r.conversion_value for r in rows)
    reach = _sum(r.reach for r in rows)
    return {
        "spend": spend,
        "impressions": impressions,
        "reach": reach,
        "clicks": clicks,
        "conversions": conversions,
        "conversion_value": value,
        "ctr": _div(clicks, impressions, 100),
        "cpc": _div(spend, clicks, 1, 2),
        "cpm": _div(spend, impressions, 1000, 2),
        "cpa": _div(spend, conversions, 1, 2),
        "roas": _div(value, spend, 1, 3),
        "mock_data": any(r.source == "mock" for r in rows),
    }


def ads_summary(db: Session, since: date, until: date) -> dict[str, Any]:
    rows = db.scalars(
        select(AdInsightDaily).where(AdInsightDaily.date >= since, AdInsightDaily.date <= until)
    ).all()
    return _ads_totals(list(rows))


def ads_by_ad(db: Session, since: date, until: date) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(AdInsightDaily).where(AdInsightDaily.date >= since, AdInsightDaily.date <= until)
    ).all()
    groups: dict[str, list[AdInsightDaily]] = defaultdict(list)
    for r in rows:
        groups[r.external_id].append(r)
    entities = {e.external_id: e for e in db.scalars(select(AdEntity).where(AdEntity.level == "ad")).all()}
    out = []
    for ext_id, items in groups.items():
        t = _ads_totals(items)
        e = entities.get(ext_id)
        t.update(
            {
                "ad_id": ext_id,
                "name": items[-1].name or (e.name if e else ext_id),
                "adset_id": items[-1].adset_external_id,
                "campaign_id": items[-1].campaign_external_id,
                "status": e.status if e else "",
                "creative": e.creative_summary if e else "",
                "days": len(items),
            }
        )
        out.append(t)
    out.sort(key=lambda x: x["spend"] or 0, reverse=True)
    return out


def daily_series(db: Session, days: int = 14) -> list[dict[str, Any]]:
    """대시보드 추이 차트용 (현지 날짜 기준)."""
    end = to_local(utcnow()).date()
    start = end - timedelta(days=days - 1)
    since = datetime.combine(start, datetime.min.time()) - timedelta(days=1)
    rows = content_performance(db, since)
    by_day: dict[date, list[dict]] = defaultdict(list)
    for r in rows:
        if r["published_at_local"]:
            by_day[date.fromisoformat(r["published_at_local"][:10])].append(r)
    ads = db.scalars(select(AdInsightDaily).where(AdInsightDaily.date >= start, AdInsightDaily.date <= end)).all()
    ads_by_day: dict[date, list[AdInsightDaily]] = defaultdict(list)
    for a in ads:
        ads_by_day[a.date].append(a)
    series = []
    for i in range(days):
        d = start + timedelta(days=i)
        items = by_day.get(d, [])
        ad_t = _ads_totals(ads_by_day.get(d, []))
        series.append(
            {
                "date": d.isoformat(),
                "posts": len(items),
                "impressions": _sum(r["impressions"] for r in items),
                "views": _sum(r["views"] for r in items),
                "engagement": _sum(engagement_total(r) for r in items),
                "ad_spend": ad_t["spend"],
                "ad_clicks": ad_t["clicks"],
                "ad_conversions": ad_t["conversions"],
            }
        )
    return series
