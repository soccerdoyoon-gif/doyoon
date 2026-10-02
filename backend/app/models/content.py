from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.timeutil import utcnow


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    platform: Mapped[str] = mapped_column(String(20), index=True)
    content_type: Mapped[str] = mapped_column(String(40), default="post")
    title: Mapped[str] = mapped_column(String(300), default="")
    idea: Mapped[str] = mapped_column(Text, default="")
    hook: Mapped[str] = mapped_column(Text, default="")
    caption: Mapped[str] = mapped_column(Text, default="")
    script: Mapped[str] = mapped_column(Text, default="")
    structure: Mapped[list] = mapped_column(JSON, default=list)
    thread: Mapped[list] = mapped_column(JSON, default=list)
    cta: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    media_idea: Mapped[str] = mapped_column(Text, default="")
    media_path: Mapped[str] = mapped_column(String(500), default="")
    media_url: Mapped[str] = mapped_column(String(1000), default="")
    language: Mapped[str] = mapped_column(String(10), default="ja")
    idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id"), nullable=True, index=True)
    style: Mapped[str] = mapped_column(String(40), default="")
    thumbnail_text: Mapped[str] = mapped_column(String(200), default="")
    video_title: Mapped[str] = mapped_column(String(300), default="")  # YouTube Shorts 등 영상 제목
    scenes: Mapped[list] = mapped_column(JSON, default=list)  # 숏폼 장면 정보
    video_prompt: Mapped[str] = mapped_column(Text, default="")  # 외부 영상 생성 AI 용 프롬프트
    music_style: Mapped[str] = mapped_column(String(200), default="")
    guardian: Mapped[dict] = mapped_column(JSON, default=dict)  # Brand Guardian 검사 결과
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    score_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_note: Mapped[str] = mapped_column(Text, default="")
    suggested_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    external_id: Mapped[str] = mapped_column(String(200), default="")
    external_url: Mapped[str] = mapped_column(String(1000), default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(20), default="ai")  # ai / manual / mock_ai
    batch_id: Mapped[str] = mapped_column(String(64), default="")
    review_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    attempts: Mapped[list["PostAttempt"]] = relationship(
        back_populates="content", cascade="all, delete-orphan", order_by="PostAttempt.id"
    )
    metrics: Mapped[list["PostMetrics"]] = relationship(
        back_populates="content", cascade="all, delete-orphan", order_by="PostMetrics.id"
    )
    assets: Mapped[list["GeneratedAsset"]] = relationship(cascade="all, delete-orphan", order_by="GeneratedAsset.order")


class ContentIdea(Base):
    """하나의 아이디어 → 플랫폼별 콘텐츠 패키지 (Instagram / TikTok / X / Ads)."""

    __tablename__ = "content_ideas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    concept: Mapped[str] = mapped_column(Text, default="")
    angle: Mapped[str] = mapped_column(Text, default="")
    style: Mapped[str] = mapped_column(String(40), default="")
    trend_refs: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(10), default="ja")
    pipeline_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="ai")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class GeneratedAsset(Base):
    """AI/서버가 생성한 이미지·영상·썸네일·음성·자막 파일 (assets/generated/...)."""

    __tablename__ = "generated_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int | None] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=True, index=True)
    ad_creative_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    idea_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # image / video / thumbnail / subtitle / scenes
    purpose: Mapped[str] = mapped_column(String(30), default="")  # feed / story / carousel / ad_banner / reel / tiktok ...
    path: Mapped[str] = mapped_column(String(500))  # assets/ 기준 상대 경로
    aspect: Mapped[str] = mapped_column(String(10), default="")
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)
    provider: Mapped[str] = mapped_column(String(30), default="template")
    prompt: Mapped[str] = mapped_column(Text, default="")
    overlay_text: Mapped[str] = mapped_column(String(200), default="")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PipelineRun(Base):
    """에이전트 파이프라인 실행 기록 (진행 상황 표시용)."""

    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING")  # RUNNING / DONE / ERROR
    steps: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PostAttempt(Base):
    __tablename__ = "post_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")
    response: Mapped[dict] = mapped_column(JSON, default=dict)

    content: Mapped[ContentItem] = relationship(back_populates="attempts")


class PostMetrics(Base):
    """게시물 성과 스냅샷. 플랫폼이 제공하지 않는 값은 NULL (추정하지 않음)."""

    __tablename__ = "post_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    saves: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    followers_gained: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="api")  # api / mock

    content: Mapped[ContentItem] = relationship(back_populates="metrics")
