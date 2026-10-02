from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BrandIn(BaseModel):
    brand_name: str = Field(min_length=1, max_length=200)
    brand_description: str = ""
    product_description: str = ""
    target_customer: str = ""
    country: str = "JP"
    language: str = Field(default="ko", pattern="^(ko|ja|en)$")
    brand_voice: str = ""
    brand_values: str = ""
    forbidden_words: list[str] = []
    preferred_words: list[str] = []
    competitors: list[str] = []
    main_goal: str = Field(default="sales", pattern="^(sales|followers|website_traffic|brand_awareness)$")
    main_products: str = ""
    website_url: str = ""


class SetupIn(BaseModel):
    brand: BrandIn
    platforms_enabled: dict[str, bool] = {}
    secrets: dict[str, str] = {}
    ads_enabled: bool = False
    daily_budget_limit: float = 10000
    currency: str = "JPY"


class CampaignIn(BaseModel):
    name: str
    objective: str = ""
    start_date: datetime | None = None
    end_date: datetime | None = None
    notes: str = ""
    is_active: bool = True


class ContentIn(BaseModel):
    platform: str = Field(pattern="^(instagram|facebook|tiktok|x)$")
    content_type: str = "post"
    title: str = ""
    idea: str = ""
    hook: str = ""
    caption: str = ""
    script: str = ""
    structure: list[str] = []
    thread: list[str] = []
    cta: str = ""
    hashtags: list[str] = []
    media_idea: str = ""
    media_url: str = ""
    campaign_id: int | None = None
    suggested_time: datetime | None = None


class ContentUpdate(BaseModel):
    title: str | None = None
    idea: str | None = None
    hook: str | None = None
    caption: str | None = None
    script: str | None = None
    structure: list[str] | None = None
    thread: list[str] | None = None
    cta: str | None = None
    hashtags: list[str] | None = None
    media_idea: str | None = None
    media_url: str | None = None
    campaign_id: int | None = None
    content_type: str | None = None


class GenerateIn(BaseModel):
    count: int | None = Field(default=None, ge=5, le=20)
    platforms: list[str] | None = None
    theme: str = ""
    campaign_id: int | None = None


class ApproveIn(BaseModel):
    schedule_at: datetime | None = None
    use_suggested_time: bool = True


class ScheduleIn(BaseModel):
    scheduled_at: datetime


class NoteIn(BaseModel):
    note: str = ""


class BulkIds(BaseModel):
    ids: list[int]
    use_suggested_time: bool = True


class AdActionIn(BaseModel):
    action_type: str = Field(pattern="^(budget_change|pause|resume|delete|create_campaign|billing_change)$")
    target_level: str = Field(default="adset", pattern="^(campaign|adset|ad)$")
    target_external_id: str
    new_budget: float | None = Field(default=None, ge=0)
    reason: str = ""


class CreativeGenIn(BaseModel):
    count: int = Field(default=3, ge=1, le=10)
    focus: str = ""


class ABTestIn(BaseModel):
    name: str
    platform: str = "instagram"
    variable: str = Field(default="hook", pattern="^(hook|caption|cta|thumbnail|video_opening)$")
    metric: str = Field(default="ctr", pattern="^(ctr|engagement_rate|conversion_rate)$")
    hypothesis: str = ""
    variant_a: str = ""
    variant_b: str = ""
    content_id_a: int | None = None
    content_id_b: int | None = None


class ABVariantUpdate(BaseModel):
    impressions: int = Field(ge=0)
    clicks: int = Field(ge=0)
    engagements: int = Field(ge=0)
    conversions: int = Field(ge=0)


class CompetitorIn(BaseModel):
    name: str
    platform: str = "instagram"
    handle: str = ""
    url: str = ""
    notes: str = ""


class ObservationIn(BaseModel):
    topic: str = ""
    content_format: str = ""
    hook_pattern: str = ""
    public_reaction: str = ""
    posts_per_week: float | None = None
    post_url: str = ""
    notes: str = ""


class ChatIn(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


class SettingValue(BaseModel):
    value: Any


class SecretsIn(BaseModel):
    secrets: dict[str, str]
