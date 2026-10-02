from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.timeutil import utcnow


class AdEntity(Base):
    """Meta 광고 구조 (campaign / adset / ad) 의 로컬 사본."""

    __tablename__ = "ad_entities"
    __table_args__ = (UniqueConstraint("level", "external_id", name="uq_ad_entity"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), default="meta")
    level: Mapped[str] = mapped_column(String(20))  # campaign / adset / ad
    external_id: Mapped[str] = mapped_column(String(100), index=True)
    parent_external_id: Mapped[str] = mapped_column(String(100), default="")
    name: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(40), default="")
    objective: Mapped[str] = mapped_column(String(100), default="")
    daily_budget: Mapped[float | None] = mapped_column(Float, nullable=True)  # 통화 단위 (예: 엔)
    creative_summary: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="api")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class AdInsightDaily(Base):
    __tablename__ = "ad_insights_daily"
    __table_args__ = (UniqueConstraint("level", "external_id", "date", name="uq_ad_insight_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(20))
    external_id: Mapped[str] = mapped_column(String(100), index=True)
    campaign_external_id: Mapped[str] = mapped_column(String(100), default="")
    adset_external_id: Mapped[str] = mapped_column(String(100), default="")
    name: Mapped[str] = mapped_column(String(300), default="")
    date: Mapped[date] = mapped_column(Date, index=True)
    spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpc: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversions: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpa: Mapped[float | None] = mapped_column(Float, nullable=True)
    roas: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversion_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="api")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class PendingAction(Base):
    """승인이 필요한 광고 작업 (예산 변경, 중지, 삭제, 캠페인 생성 등)."""

    __tablename__ = "pending_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_type: Mapped[str] = mapped_column(String(40))
    target_level: Mapped[str] = mapped_column(String(20), default="")
    target_external_id: Mapped[str] = mapped_column(String(100), default="")
    target_name: Mapped[str] = mapped_column(String(300), default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    guard_result: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by: Mapped[str] = mapped_column(String(20), default="user")  # user / ai
    result: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AdCreativeDraft(Base):
    __tablename__ = "ad_creative_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hook: Mapped[str] = mapped_column(Text, default="")
    primary_text: Mapped[str] = mapped_column(Text, default="")
    headline: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    cta: Mapped[str] = mapped_column(String(100), default="")
    video_idea: Mapped[str] = mapped_column(Text, default="")
    image_idea: Mapped[str] = mapped_column(Text, default="")
    target_message: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    based_on: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(10), default="ko")
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT/APPROVED/REJECTED
    source: Mapped[str] = mapped_column(String(20), default="ai")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
