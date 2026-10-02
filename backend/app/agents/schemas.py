"""에이전트 구조화 출력 스키마 (모든 필드 required, additionalProperties=false)."""
from __future__ import annotations

from app.ai.schemas import I, N, S, SL, _obj

STYLES = ["カジュアル", "親しみやすい", "シンプル", "高級感", "若者向け", "Z世代向け", "男性向け", "女性向け", "ストリート系", "ラグジュアリー系"]
STYLE = {"type": "string", "enum": STYLES}

TREND = _obj({
    "summary": S,
    "platform_trends": {"type": "array", "items": _obj({
        "platform": {"type": "string", "enum": ["tiktok", "instagram_reels", "x", "youtube_shorts"]},
        "formats": SL, "hooks": SL, "expressions": SL, "hashtags": SL,
        "ideal_video_length": S, "ctas": SL, "notes": S,
    })},
    "competitor_styles": SL,
    "global_trends_applicability": SL,
    "evidence": {"type": "string", "enum": ["web_search", "general_knowledge"]},
    "data_limitations": S,
})

IDEAS = _obj({"ideas": {"type": "array", "items": _obj({
    "title": S, "concept": S, "angle": S, "target_insight": S, "style": STYLE,
    "trend_refs": SL, "hook_direction": S,
})}})

COPY = _obj({"packages": {"type": "array", "items": _obj({
    "idea_index": I,
    "instagram": _obj({
        "content_type": {"type": "string", "enum": ["post", "carousel", "reel"]},
        "hook": S, "caption": S, "cta": S, "hashtags": SL, "carousel_slides": SL, "thumbnail_text": S,
    }),
    "tiktok": _obj({"hook": S, "caption": S, "cta": S, "hashtags": SL, "thumbnail_text": S, "youtube_shorts_title": S}),
    "x": _obj({"post_type": {"type": "string", "enum": ["tweet", "info_tweet", "ad_tweet", "thread"]}, "post": S, "thread": SL}),
    "facebook": _obj({"post": S, "hashtags": SL}),
    "ads": _obj({"headline": S, "primary_text": S, "description": S, "cta": S, "image_text": S}),
})}})

SCENE = _obj({
    "scene_id": I, "duration": N,
    "purpose": {"type": "string", "enum": ["hook", "curiosity", "value", "product", "cta"]},
    "visual": S, "camera": S, "voiceover": S, "subtitle": S, "music_style": S,
})
SCRIPTS = _obj({"scripts": {"type": "array", "items": _obj({
    "item_key": S, "music_style": S, "video_prompt": S, "scenes": {"type": "array", "items": SCENE},
})}})

BRIEFS = _obj({"briefs": {"type": "array", "items": _obj({
    "item_key": S, "color_mood": S,
    "images": {"type": "array", "items": _obj({
        "purpose": {"type": "string", "enum": ["feed", "story", "carousel", "thumbnail", "ad_banner"]},
        "overlay_text": S, "sub_text": S, "visual_prompt": S,
    })},
})}})

REVIEWS = _obj({"reviews": {"type": "array", "items": _obj({
    "item_key": S,
    "verdict": {"type": "string", "enum": ["pass", "fix", "reject"]},
    "issues": {"type": "array", "items": _obj({
        "severity": {"type": "string", "enum": ["info", "warning", "error"]}, "field": S, "message": S,
    })},
    "corrected": _obj({"hook": S, "caption": S, "cta": S, "thumbnail_text": S, "hashtags": SL, "thread": SL, "subtitles": SL}),
    "scores": _obj({"hook_strength": I, "target_audience_fit": I, "brand_consistency": I, "cta_quality": I, "originality": I, "expected_engagement": I}),
    "score_note": S,
})}})
