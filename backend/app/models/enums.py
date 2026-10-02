from __future__ import annotations

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # pragma: no cover
        return self.value


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    X = "x"


class ContentStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    SCHEDULED = "SCHEDULED"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class ActionStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class AdActionType(StrEnum):
    BUDGET_CHANGE = "budget_change"
    PAUSE = "pause"
    RESUME = "resume"
    DELETE = "delete"
    CREATE_CAMPAIGN = "create_campaign"
    BILLING_CHANGE = "billing_change"


class MainGoal(StrEnum):
    SALES = "sales"
    FOLLOWERS = "followers"
    WEBSITE_TRAFFIC = "website_traffic"
    BRAND_AWARENESS = "brand_awareness"


SUPPORTED_LANGUAGES = {"ko": "한국어", "ja": "日本語", "en": "English"}
