"""Claude 구조화 출력용 JSON Schema (모든 필드 required, additionalProperties=false)."""
from __future__ import annotations

CONTENT_TYPES = [
    "post", "carousel", "reel", "story", "short_video", "tweet", "ad_tweet", "info_tweet", "thread",
]
PLATFORMS = ["instagram", "facebook", "tiktok", "x"]


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


S = {"type": "string"}
SL = {"type": "array", "items": {"type": "string"}}
I = {"type": "integer"}
N = {"type": "number"}

CONTENT_CANDIDATES = _obj({
    "candidates": {
        "type": "array",
        "items": _obj({
            "slot": I,
            "platform": {"type": "string", "enum": PLATFORMS},
            "content_type": {"type": "string", "enum": CONTENT_TYPES},
            "title": S,
            "idea": S,
            "hook": S,
            "caption": S,
            "script": S,
            "structure": SL,
            "thread": SL,
            "cta": S,
            "hashtags": SL,
            "media_idea": S,
            "suggested_time_local": S,
            "rationale": S,
        }),
    }
})

CONTENT_SCORES = _obj({
    "scores": {
        "type": "array",
        "items": _obj({
            "index": I,
            "hook_strength": I,
            "target_audience_fit": I,
            "brand_consistency": I,
            "cta_quality": I,
            "originality": I,
            "expected_engagement": I,
            "note": S,
        }),
    }
})

CONTENT_ANALYSIS = _obj({
    "summary": S,
    "top_content": SL,
    "low_content": SL,
    "hook_patterns": SL,
    "caption_patterns": SL,
    "cta_patterns": SL,
    "topics": SL,
    "best_posting_times": SL,
    "platform_differences": SL,
    "recommendations_for_next_content": SL,
    "data_limitations": S,
})

ADS_ANALYSIS = _obj({
    "summary": S,
    "ads": {
        "type": "array",
        "items": _obj({
            "ad_id": S,
            "name": S,
            "verdict": {"type": "string", "enum": ["good", "watch", "poor", "insufficient_data"]},
            "findings": SL,
            "recommendation": S,
        }),
    },
    "proposed_actions": {
        "type": "array",
        "items": _obj({
            "action_type": {"type": "string", "enum": ["budget_change", "pause", "resume"]},
            "target_level": {"type": "string", "enum": ["campaign", "adset", "ad"]},
            "target_id": S,
            "new_daily_budget": N,
            "reason": S,
        }),
    },
    "creative_directions": SL,
    "data_limitations": S,
})

AD_CREATIVES = _obj({
    "creatives": {
        "type": "array",
        "items": _obj({
            "hook": S,
            "primary_text": S,
            "headline": S,
            "description": S,
            "cta": S,
            "video_idea": S,
            "image_idea": S,
            "target_message": S,
            "rationale": S,
        }),
    }
})

COMPETITOR_ANALYSIS = _obj({
    "summary": S,
    "competitor_patterns": SL,
    "gaps_and_opportunities": SL,
    "differentiation_ideas": SL,
    "avoid": SL,
})

STRATEGY = _obj({
    "summary": S,
    "content_pillars": SL,
    "weekly_plan": SL,
    "platform_strategy": SL,
    "kpis_to_watch": SL,
})

REPORT_INSIGHTS = _obj({
    "insights": SL,
    "tomorrow_plan": SL,
    "best_patterns": SL,
    "worst_patterns": SL,
    "ideas_to_test": SL,
})

AB_INTERPRETATION = _obj({"interpretation": S, "next_steps": SL})
