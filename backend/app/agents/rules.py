"""규칙 기반 검사 (Brand Guardian 의 1차 필터) + 해시태그 정리 + X 글자 수 계산."""
from __future__ import annotations

import re
from collections import Counter
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import utcnow
from app.models import ContentItem

HANGUL = re.compile(r"[ᄀ-ᇿ㄰-㆏가-힯]")
# 경고 대상 (근거 없이 쓰면 景品表示法・薬機法 위험이 큰 표현)
RISKY_TERMS = ["絶対", "必ず", "100%", "１００％", "完全", "最安", "日本一", "No.1", "ナンバーワン", "業界初", "世界一",
               "治る", "治す", "完治", "痩せる", "やせる", "シミが消える", "若返る", "副作用なし", "永久"]
HASHTAG_LIMITS = {"instagram": 15, "tiktok": 5, "x": 2, "facebook": 3}
CAPTION_LIMITS = {"instagram": 2200, "tiktok": 2200, "facebook": 5000}


def x_weighted_length(text: str) -> int:
    """X 의 글자 수 규칙: 한자·가나 등은 2, 라틴 문자 등은 1, URL 은 23."""
    text = re.sub(r"https?://\S+", "x" * 23, text or "")
    n = 0
    for ch in text:
        o = ord(ch)
        light = o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037
        n += 1 if light else 2
    return n


def normalize_hashtags(tags: list[str], platform: str) -> list[str]:
    out: list[str] = []
    for t in tags or []:
        t = re.sub(r"\s+", "", str(t)).lstrip("#＃")
        if t and f"#{t}" not in out:
            out.append(f"#{t}")
    return out[: HASHTAG_LIMITS.get(platform, 10)]


def overused_hashtags(db: Session, days: int = 14, min_count: int = 3) -> list[str]:
    """최근 자주 쓴 해시태그 — 매번 같은 태그를 반복하지 않도록 AI 에게 알려줌."""
    rows = db.scalars(select(ContentItem.hashtags).where(ContentItem.created_at >= utcnow() - timedelta(days=days))).all()
    c = Counter(t for tags in rows for t in (tags or []))
    return [t for t, n in c.most_common(30) if n >= min_count]


def check(item: ContentItem, forbidden: list[str]) -> list[dict]:
    """issues: [{severity, field, message}] — error 가 있으면 승인 단계로 보내지 않음."""
    issues: list[dict] = []
    fields = {
        "hook": item.hook, "caption": item.caption, "cta": item.cta, "thumbnail_text": item.thumbnail_text,
        "thread": "\n".join(item.thread or []), "hashtags": " ".join(item.hashtags or []),
        "subtitles": "\n".join(s.get("subtitle", "") + s.get("voiceover", "") for s in (item.scenes or [])),
    }
    for name, text in fields.items():
        if not text:
            continue
        if item.language == "ja" and HANGUL.search(text):
            issues.append({"severity": "error", "field": name, "message": "韓国語（ハングル）が含まれています"})
        for w in forbidden or []:
            if w and w.lower() in text.lower():
                issues.append({"severity": "error", "field": name, "message": f"禁止ワード「{w}」が含まれています"})
        for w in RISKY_TERMS:
            if w in text:
                issues.append({"severity": "warning", "field": name, "message": f"「{w}」は根拠がないと景品表示法・薬機法上のリスクがあります"})
        if re.search(r"[!！]{3,}", text):
            issues.append({"severity": "warning", "field": name, "message": "感嘆符が多すぎます（押しが強すぎる印象）"})
    if item.platform == "x":
        for i, t in enumerate(item.thread or [item.caption]):
            n = x_weighted_length(t)
            if n > 280:
                issues.append({"severity": "error", "field": "caption" if not item.thread else f"thread[{i}]",
                               "message": f"Xの文字数制限を超えています（{n}/280、日本語は1文字=2カウント）"})
    limit = CAPTION_LIMITS.get(item.platform)
    full = f"{item.caption}\n\n{' '.join(item.hashtags or [])}"
    if limit and len(full) > limit:
        issues.append({"severity": "error", "field": "caption", "message": f"キャプションが長すぎます（{len(full)}/{limit}）"})
    if item.platform in ("tiktok",) or item.content_type in ("reel", "short_video"):
        if not item.scenes:
            issues.append({"severity": "warning", "field": "scenes", "message": "動画の台本（シーン）がありません"})
    return issues
