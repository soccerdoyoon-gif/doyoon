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
    reload_settings()


@pytest.fixture
def brand(db):
    b = BrandProfile(
        brand_name="Sakura Tea",
        brand_description="교토의 유기농 녹차 브랜드",
        product_description="유기농 말차 파우더",
        main_products="말차 파우더, 호지차 티백",
        target_customer="25-39세 건강에 관심 많은 직장인",
        country="JP",
        language="ko",
        brand_voice="따뜻하고 차분한",
        forbidden_words=["최고", "100% 효과"],
        preferred_words=["유기농"],
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


class FakeSDK:
    """anthropic.Anthropic 대체. 구조화 출력 스키마를 보고 그럴듯한 JSON 을 돌려줍니다."""

    def __init__(self):
        self.calls: list[dict] = []
        self.queue: list = []
        self.messages = FakeMessages(self)
        self.beta = SimpleNamespace(messages=FakeMessages(self))

    def default(self, params):
        schema = params.get("output_config", {}).get("format", {}).get("schema", {})
        props = schema.get("properties", {})
        prompt = params["messages"][0]["content"] if params.get("messages") else ""
        if "candidates" in props:
            slots = json.loads(re.search(r"(\[\{\"slot\".*?\}\])", prompt, re.S).group(1))
            return text_resp({"candidates": [
                {"slot": s["slot"], "platform": s["platform"], "content_type": s["content_type"], "title": f"AI title {s['slot']}",
                 "idea": "idea", "hook": "강한 훅", "caption": "유기농 말차 이야기", "script": "", "structure": [], "thread": [],
                 "cta": "프로필 링크", "hashtags": ["#말차"], "media_idea": "photo", "suggested_time_local": "20:30", "rationale": "r"}
                for s in slots]})
        if "scores" in props:
            n = prompt.count('"index"')
            return text_resp({"scores": [{"index": i, "hook_strength": 9, "target_audience_fit": 8, "brand_consistency": 8,
                                          "cta_quality": 7, "originality": 6, "expected_engagement": 8, "note": "good"} for i in range(n)]})
        # generic: fill every required field with empty values of the right type
        def empty(p):
            t = p.get("type")
            return [] if t == "array" else 0 if t in ("integer", "number") else "AI summary" if t == "string" else {}
        return text_resp({k: empty(v) for k, v in props.items()})


@pytest.fixture
def fake_ai():
    sdk = FakeSDK()
    client = ClaudeClient(sdk_client=sdk)
    set_ai_override(client)
    return sdk
