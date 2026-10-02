"""Analytics Agent — 일본 시간(JST) 기준 게시 시간 학습.

- 우리 계정 데이터에서 시간대별 평균 참여율을 계산
- 표본(게시 수)이 충분한 시간대만 '추천' 으로 사용 (기본 3건 이상)
- 데이터가 부족하면 일반적인 시간대(7-9시 / 12-13시 / 18-22시)를 '테스트 후보' 로 사용
- 추천 시간과 테스트 후보를 섞어서 계속 학습 (탐색 30%)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.stats import content_performance
from app.core.timeutil import utcnow
from app.models import Insight
from app.services.app_settings import get_setting
from app.services.events import log_event

MIN_POSTS = 3
CANDIDATE_HOURS = [7, 8, 12, 18, 19, 20, 21]


def learn(db: Session, days: int = 60) -> Insight:
    rows = content_performance(db, utcnow() - timedelta(days=days))
    defaults = get_setting(db, "posting_times")
    stats: dict[str, dict[int, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r.get("hour") is not None and r.get("engagement_rate") is not None and r.get("data_source") != "mock":
            stats[r["platform"]][r["hour"]].append(r["engagement_rate"])
    result: dict[str, dict] = {}
    for platform, base in defaults.items():
        hours = stats.get(platform, {})
        ranked = sorted(
            ((h, sum(v) / len(v), len(v)) for h, v in hours.items() if len(v) >= MIN_POSTS),
            key=lambda x: x[1], reverse=True,
        )
        recommended = [f"{h:02d}:00" for h, _, _ in ranked[:3]]
        tested = {h for h in hours}
        explore = [f"{h:02d}:00" for h in CANDIDATE_HOURS if h not in tested][:2]
        result[platform] = {
            "recommended": recommended,
            "test_candidates": base if not recommended else explore,
            "hour_stats": {f"{h:02d}": {"avg_er": round(sum(v) / len(v), 3), "posts": len(v)} for h, v in sorted(hours.items())},
            "status": "learned" if recommended else "testing",
        }
    ins = Insight(
        kind="posting_times",
        summary="JST 基準の投稿時間分析（自社アカウントの実データのみ使用。mock データは除外）",
        data={"platforms": result, "min_posts_per_hour": MIN_POSTS, "timezone": "Asia/Tokyo"},
        source="rules",
    )
    db.add(ins)
    log_event("ai_generation", "게시 시간 학습 완료 (JST)", {k: v["status"] for k, v in result.items()}, db=db)
    db.commit()
    return ins


def slots_for(db: Session, platform: str) -> list[str]:
    """다음 게시 시간 후보 (JST "HH:MM"). 학습된 추천 시간 + 테스트 후보를 섞음."""
    ins = db.scalars(select(Insight).where(Insight.kind == "posting_times").order_by(Insight.id.desc()).limit(1)).first()
    base = get_setting(db, "posting_times").get(platform) or ["12:00"]
    if not ins:
        return base
    p = ins.data.get("platforms", {}).get(platform, {})
    rec = p.get("recommended") or []
    if not rec:
        return p.get("test_candidates") or base
    explore = p.get("test_candidates") or []
    # 대략 3번 중 1번은 아직 데이터가 적은 시간대를 시험
    return rec + rec + explore[:1] if explore else rec
