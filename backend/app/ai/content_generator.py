"""(호환용) 예전 generate_content → 에이전트 파이프라인으로 연결.

count 는 '아이디어 수' 입니다. 아이디어 1개 → 선택한 SNS 별 콘텐츠 + 광고안 패키지.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.agents.pipeline import run_pipeline


def generate_content(
    db: Session,
    count: int | None = None,
    platforms: list[str] | None = None,
    theme: str = "",
    target_day: date | None = None,
    campaign_id: int | None = None,
    **kwargs,
) -> dict:
    return run_pipeline(db, platforms=platforms, idea_count=count, theme=theme, start_day=target_day, campaign_id=campaign_id, **kwargs)
