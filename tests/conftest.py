"""테스트 공통 설정 — 실제 SNS/Claude API 를 절대 호출하지 않습니다."""
from __future__ import annotations

import json
import os
import re
import tempfile
from types import SimpleNamespace

import pytest

_TMP = tempfile.mkdtemp(prefix="sns-ai-test-")
os.environ.update(
    {
        "DATA_DIR": os.path.join(_TMP, "data"),
        "LOG_DIR": os.path.join(_TMP, "logs"),
        "DATABASE_URL": "sqlite://",
        "SCHEDULER_ENABLED": "false",
        "DRY_RUN": "true",
        "TIMEZONE": "Asia/Tokyo",
        "ASSETS_DIR": os.path.join(_TMP, "assets"),
        "VOICEVOX_URL": "",
        "IMAGE_PROVIDER": "template",
        "OPENAI_API_KEY": "",
        "VIDEO_FPS": "24",
        "PIPELINE_BACKGROUND": "false",
        "VIDEO_PRESET": "ultrafast",
    }
)
# .env / data/secrets.env 에 실제 키가 있어도 테스트에서는 비활성화
for key in (
    "ANTHROPIC_API_KEY", "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID", "FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_ACCESS_TOKEN",
    "META_ADS_ACCESS_TOKEN", "META_AD_ACCOUNT_ID", "TIKTOK_ACCESS_TOKEN", "TIKTOK_REFRESH_TOKEN", "TIKTOK_CLIENT_KEY",
    "TIKTOK_CLIENT_SECRET", "X_ACCESS_TOKEN", "X_REFRESH_TOKEN", "X_CLIENT_ID", "X_CLIENT_SECRET",
    "SLACK_WEBHOOK_URL", "DISCORD_WEBHOOK_URL", "PUBLIC_MEDIA_BASE_URL", "INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET",
):
    os.environ[key] = ""

from app.core.config import reload_settings  # noqa: E402
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.ai.client import ClaudeClient, set_ai_override  # noqa: E402
from app.connectors import registry  # noqa: E402
from app.models import BrandProfile  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    from app import models  # noqa: F401

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    set_ai_override(None)
    registry._overrides.clear()
    from app.media.image_providers import set_image_override
    from app.media.tts import set_tts_override

    set_image_override(None)
    set_tts_override(None)


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def settings_env(monkeypatch):
    """환경변수를 바꾸고 설정을 다시 읽는 헬퍼."""

    def apply(**kwargs):
        for k, v in kwargs.items():
            monkeypatch.setenv(k.upper(), str(v))
        return reload_settings()

    yield apply
    monkeypatch.undo()  # 환경변수를 먼저 되돌린 뒤 설정을 다시 읽어야 다음 테스트에 새지 않음
    reload_settings()


@pytest.fixture
def brand(db):
    b = BrandProfile(
        brand_name="Sakura Tea",
        brand_description="京都のオーガニック緑茶ブランド",
        product_description="オーガニック抹茶パウダー",
        main_products="抹茶パウダー、ほうじ茶ティーバッグ",
        target_customer="日本在住の25〜39歳の健康志向の会社員",
        country="JP",
        language="ja",
        brand_voice="やさしく落ち着いた",
        forbidden_words=["最高級", "奇跡"],
        preferred_words=["オーガニック"],
        competitors=["Matcha Co"],
        main_goal="sales",
    )
    db.add(b)
    db.commit()
    return b


# ---------------------------------------------------------------------------
# Fake Claude SDK client
# ---------------------------------------------------------------------------
def _resp(content, stop_reason="end_turn"):
    return SimpleNamespace(
        content=content, stop_reason=stop_reason, model="fake-model",
        usage=SimpleNamespace(input_tokens=10, output_tokens=20),
    )


def text_resp(obj):
    return _resp([SimpleNamespace(type="text", text=json.dumps(obj, ensure_ascii=False))])


class FakeMessages:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **params):
        self.owner.calls.append(params)
        if self.owner.queue:
            item = self.owner.queue.pop(0)
            return item(params) if callable(item) else item
        return self.owner.default(params)


def fill(schema):
    """JSON schema 를 만족하는 기본값 (일본어 문자열)."""
    t = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if t == "object":
        return {k: fill(v) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return [fill(schema["items"])]
    if t == "integer":
        return 7
    if t == "number":
        return 2.0
    if t == "boolean":
        return True
    return "テスト"


def tagged_json(prompt, tag):
    m = re.search(rf"<{tag}>\s*(.*?)\s*</{tag}>", prompt, re.S)
    return json.loads(m.group(1)) if m else []


class FakeSDK:
    """anthropic.Anthropic 대체. 구조화 출력 스키마를 보고 그럴듯한 JSON 을 돌려줍니다."""

    def __init__(self):
        self.calls: list[dict] = []
        self.queue: list = []
        self.review_override = None  # callable(item) -> review dict
        self.messages = FakeMessages(self)
        self.beta = SimpleNamespace(messages=FakeMessages(self))

    def default(self, params):
        if params.get("tools") and params["tools"][0].get("type", "").startswith("web_search"):
            return _resp([
                SimpleNamespace(type="server_tool_use", id="s1", name="web_search", input={"query": "TikTok 日本 トレンド"}),
                SimpleNamespace(type="web_search_tool_result", tool_use_id="s1", content=[
                    SimpleNamespace(type="web_search_result", url="https://example.jp/trend", title="日本のTikTokトレンド")]),
                SimpleNamespace(type="text", text="・日本のTikTokでは正直レビュー形式が人気"),
            ])
        schema = params.get("output_config", {}).get("format", {}).get("schema", {})
        props = schema.get("properties", {})
        prompt = params["messages"][0]["content"] if params.get("messages") else ""
        if "ideas" in props:
            n = int(re.search(r"アイデアを(\d+)個", prompt).group(1))
            return text_resp({"ideas": [{"title": f"アイデア{i}", "concept": "朝のルーティン", "angle": "正直レビュー", "target_insight": "忙しい",
                                         "style": "親しみやすい", "trend_refs": ["正直レビュー"], "hook_direction": "これ、知らないと損。"} for i in range(n)]})
        if "packages" in props:
            ideas = tagged_json(prompt, "ideas")
            return text_resp({"packages": [{
                "idea_index": i,
                "instagram": {"content_type": "carousel" if i % 2 else "post", "hook": "これ、知らないと損。", "caption": "朝の一杯で気分が変わる。",
                              "cta": "保存して見返してね", "hashtags": ["おすすめ", "#暮らし", "#暮らし"], "carousel_slides": ["1枚目", "2枚目", "3枚目"],
                              "thumbnail_text": "知らないと損"},
                "tiktok": {"hook": "3秒だけ見て。", "caption": "朝のルーティン", "cta": "プロフから見てね", "hashtags": ["#おすすめ", "#購入品"],
                           "thumbnail_text": "3秒だけ見て", "youtube_shorts_title": "朝の一杯"},
                "x": {"post_type": "tweet", "post": "これ地味に便利。みんなはどうしてる？", "thread": []},
                "facebook": {"post": "テスト", "hashtags": []},
                "ads": {"headline": "毎朝を、ちょっと特別に", "primary_text": "テスト本文", "description": "説明", "cta": "詳しくはこちら", "image_text": "毎朝を特別に"},
            } for i, _ in enumerate(ideas)]})
        if "scripts" in props:
            vids = tagged_json(prompt, "videos")
            return text_resp({"scripts": [{"item_key": v["item_key"], "music_style": "lofi", "video_prompt": "vertical video, Tokyo",
                                           "scenes": [{"scene_id": 1, "duration": 1.0, "purpose": "hook", "visual": "東京の街を歩く若者", "camera": "寄り",
                                                       "voiceover": "これ、知ってる？", "subtitle": "これ、知ってる？", "music_style": ""},
                                                      {"scene_id": 2, "duration": 1.5, "purpose": "cta", "visual": "商品", "camera": "引き",
                                                       "voiceover": "保存してね。", "subtitle": "保存してね。", "music_style": ""}]} for v in vids]})
        if "briefs" in props:
            items = tagged_json(prompt, "items")
            return text_resp({"briefs": [{"item_key": it["item_key"], "color_mood": "ナチュラル",
                                          "images": [{"purpose": p, "overlay_text": "朝を変える", "sub_text": "", "visual_prompt": "matcha on a table"}
                                                     for p in it["purposes"]]} for it in items]})
        if "reviews" in props:
            items = tagged_json(prompt, "items")
            out = []
            for it in items:
                rv = {"item_key": it["item_key"], "verdict": "pass", "issues": [], "score_note": "良い",
                      "corrected": {"hook": "", "caption": "", "cta": "", "thumbnail_text": "", "hashtags": [], "thread": [], "subtitles": []},
                      "scores": {"hook_strength": 9, "target_audience_fit": 8, "brand_consistency": 8, "cta_quality": 7, "originality": 6, "expected_engagement": 8}}
                if self.review_override:
                    rv = self.review_override(it, rv)
                out.append(rv)
            return text_resp({"reviews": out})
        if "candidates" in props:
            slots = json.loads(re.search(r"(\[\{\"slot\".*?\}\])", prompt, re.S).group(1))
            return text_resp({"candidates": [{**fill(props["candidates"]["items"]), "slot": s["slot"], "platform": s["platform"], "content_type": s["content_type"]} for s in slots]})
        return text_resp(fill(schema) if schema else {})


@pytest.fixture
def fake_ai():
    sdk = FakeSDK()
    client = ClaudeClient(sdk_client=sdk)
    set_ai_override(client)
    return sdk
