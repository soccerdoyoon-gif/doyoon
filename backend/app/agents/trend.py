"""Trend Research Agent — 일본 시장 우선 트렌드 조사.

우선순위: 일본 TikTok → Instagram Reels → X → YouTube Shorts
- Claude 웹 검색(일본 위치)으로 최신 정보를 조사하고 출처 URL 을 저장합니다.
- 웹 검색이 꺼져 있거나 실패하면 '일반 지식(미검증)' 으로 표시합니다.
- 결과는 Insight(kind="trend") 로 저장하고 하루 동안 재사용합니다 (비용 절약).
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import mock_ja
from app.agents.base import as_json, brand_context, run_json, system_prompt
from app.agents.rules import overused_hashtags
from app.agents.schemas import TREND
from app.ai.client import AIError, get_ai
from app.analytics.stats import content_performance, rank_content
from app.core.config import get_settings
from app.core.timeutil import to_local, utcnow
from app.models import BrandProfile, Competitor, Insight
from app.services.events import log_event

CACHE_HOURS = 20
ROLE = "あなたは日本のSNSトレンドリサーチャーです。日本市場で実際に使えるかどうかを最優先に判断します。"


def _web_research(brand: BrandProfile | None, theme: str) -> tuple[str, list[dict]]:
    """Claude web_search 로 조사 → (요약 텍스트, 출처 목록). 실패 시 ("", [])."""
    ai = get_ai()
    today = to_local(utcnow()).strftime("%Y年%m月%d日")
    product = (brand.main_products or brand.product_description or brand.brand_name) if brand else ""
    prompt = (
        f"今日は{today}です。日本のSNSトレンドを調査してください。商材: {product}。" + (f"テーマ: {theme}。" if theme else "")
        + "\n優先順位: 1) 日本のTikTok 2) 日本のInstagram Reels 3) 日本のX 4) 日本のYouTube Shorts。"
        "\n調べること: 流行っているコンテンツ形式、反応の良いフック、よく使われる表現、よく使われるハッシュタグ、"
        "好まれる動画の長さ、反応の良いCTA、この商材カテゴリの日本の競合のスタイル。"
        "\n海外トレンドは参考程度にし、日本で実際に通用するかを判断してください。"
        "確認できなかった点は「未確認」と書いてください。日本語で箇条書きでまとめてください。"
    )
    tools = [{
        "type": "web_search_20260209", "name": "web_search", "max_uses": 5,
        "user_location": {"type": "approximate", "country": "JP", "timezone": "Asia/Tokyo"},
    }]
    messages: list[dict] = [{"role": "user", "content": prompt}]
    params = ai._base_params(16000)
    text_parts: list[str] = []
    sources: list[dict] = []
    for _ in range(3):  # pause_turn 이면 이어서 진행
        resp = ai.create("trend_research_web", system=system_prompt(ROLE), tools=tools, messages=messages, **params)
        for block in resp.content:
            btype = getattr(block, "type", "")
            if btype == "text":
                text_parts.append(block.text)
            elif btype == "web_search_tool_result" and isinstance(getattr(block, "content", None), list):
                for r in block.content:
                    url = getattr(r, "url", "")
                    if url and all(s["url"] != url for s in sources):
                        sources.append({"url": url, "title": getattr(r, "title", "")})
        if resp.stop_reason != "pause_turn":
            break
        messages = [messages[0], {"role": "assistant", "content": resp.content}]
    return "".join(text_parts).strip(), sources[:20]


def latest(db: Session) -> Insight | None:
    return db.scalars(select(Insight).where(Insight.kind == "trend").order_by(Insight.id.desc()).limit(1)).first()


def research(db: Session, theme: str = "", force: bool = False) -> Insight:
    cached = latest(db)
    if cached and not force and not theme and cached.created_at >= utcnow() - timedelta(hours=CACHE_HOURS):
        return cached
    brand = db.query(BrandProfile).first()
    ai = get_ai()
    web_text, sources = "", []
    if ai.is_available() and get_settings().trend_web_search:
        try:
            web_text, sources = _web_research(brand, theme)
        except AIError as exc:
            log_event("api_error", f"트렌드 웹 검색 실패 → 일반 지식으로 진행: {exc}", level="WARNING", db=db)
    best, _ = rank_content(content_performance(db, utcnow() - timedelta(days=30)), 5)
    comp = [
        {"name": c.name, "platform": c.platform, "observations": [
            {"topic": o.topic, "format": o.content_format, "hook": o.hook_pattern, "reaction": o.public_reaction} for o in c.observations[-5:]
        ]} for c in db.scalars(select(Competitor)).all()
    ]
    prompt = (
        f"{brand_context(brand)}\n\n"
        + (f"<web_research>\n{web_text}\n</web_research>\n" if web_text else "<web_research>ウェブ調査なし</web_research>\n")
        + f"<our_best_posts>\n{as_json(best)}\n</our_best_posts>\n<competitor_observations>\n{as_json(comp)}\n</competitor_observations>\n"
        + f"<recently_overused_hashtags>{as_json(overused_hashtags(db))}</recently_overused_hashtags>\n"
        + (f"テーマ: {theme}\n" if theme else "")
        + "日本市場のトレンドレポートを構造化してください。platform_trends は tiktok, instagram_reels, x, youtube_shorts の順。"
        "evidence は web_research がある場合のみ web_search、なければ general_knowledge。"
        "web_research にない具体的な数値や事実を作らないでください。不確かな点は data_limitations に書いてください。"
    )
    data, source = run_json("trend_research", system_prompt(ROLE), prompt, TREND, mock_ja.trend)
    if not web_text and data.get("evidence") == "web_search":
        data["evidence"] = "general_knowledge"
    data["sources"] = sources
    ins = Insight(kind="trend", summary=data.get("summary", ""), data=data, source=source)
    db.add(ins)
    log_event("ai_generation", f"트렌드 조사 완료 ({source}, evidence={data.get('evidence')}, 출처 {len(sources)}건)", db=db)
    db.commit()
    return ins
