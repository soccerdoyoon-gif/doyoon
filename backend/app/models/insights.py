from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.timeutil import utcnow


class Insight(Base):
    """AI 분석 결과. kind: content / ads / competitor / strategy."""

    __tablename__ = "insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(20), default="ai")  # ai / mock_ai
    period_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_type: Mapped[str] = mapped_column(String(20), index=True)  # daily / weekly
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    content_md: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    file_path: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ABTest(Base):
    __tablename__ = "ab_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(20), default="instagram")
    variable: Mapped[str] = mapped_column(String(40), default="hook")  # hook/caption/cta/thumbnail/video_opening
    metric: Mapped[str] = mapped_column(String(40), default="ctr")  # ctr / engagement_rate / conversion_rate
    hypothesis: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    variants: Mapped[list["ABVariant"]] = relationship(
        back_populates="test", cascade="all, delete-orphan", order_by="ABVariant.id"
    )


class ABVariant(Base):
    __tablename__ = "ab_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[int] = mapped_column(ForeignKey("ab_tests.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(20))  # A / B
    description: Mapped[str] = mapped_column(Text, default="")
    content_id: Mapped[int | None] = mapped_column(ForeignKey("content_items.id"), nullable=True)
    ad_external_id: Mapped[str] = mapped_column(String(100), default="")
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    engagements: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)

    test: Mapped[ABTest] = relationship(back_populates="variants")


class Competitor(Base):
    __tablename__ = "competitors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    platform: Mapped[str] = mapped_column(String(20), default="instagram")
    handle: Mapped[str] = mapped_column(String(200), default="")
    url: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    observations: Mapped[list["CompetitorObservation"]] = relationship(
        back_populates="competitor", cascade="all, delete-orphan", order_by="CompetitorObservation.id"
    )


class CompetitorObservation(Base):
    """사람이 공개 페이지에서 직접 확인해 입력하는 관찰 기록 (스크래핑 없음)."""

    __tablename__ = "competitor_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    competitor_id: Mapped[int] = mapped_column(ForeignKey("competitors.id", ondelete="CASCADE"), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    topic: Mapped[str] = mapped_column(Text, default="")
    content_format: Mapped[str] = mapped_column(String(100), default="")
    hook_pattern: Mapped[str] = mapped_column(Text, default="")
    public_reaction: Mapped[str] = mapped_column(Text, default="")
    posts_per_week: Mapped[float | None] = mapped_column(nullable=True)
    post_url: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    competitor: Mapped[Competitor] = relationship(back_populates="observations")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class EventLog(Base):
    """주요 이벤트 감사 로그. category: ai_generation / post_attempt / api_response /
    api_error / ad_data / approval / budget_change / system / dry_run"""

    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    level: Mapped[str] = mapped_column(String(10), default="INFO")
    message: Mapped[str] = mapped_column(Text, default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
