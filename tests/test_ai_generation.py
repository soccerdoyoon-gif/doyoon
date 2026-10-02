from app.ai.client import AIError
from app.ai.content_generator import generate_content, plan_slots
from app.models import ContentItem, Insight
from app.services.app_settings import set_setting


def test_plan_slots_minimum_five_and_rotation():
    slots = plan_slots(["instagram", "tiktok", "x"], 3)
    assert len(slots) == 5
    assert {s["platform"] for s in slots} == {"instagram", "tiktok", "x"}
    ig = [s["content_type"] for s in plan_slots(["instagram"], 6)]
    assert ig[:2] == ["post", "reel"]


def test_mock_generation_without_api_key(db, brand):
    res = generate_content(db, count=6)
    assert res["source"] == "mock_ai"
    items = db.query(ContentItem).all()
    assert len(items) >= 5
    for it in items:
        assert it.status == "READY_FOR_REVIEW"  # 바로 게시하지 않음
        assert it.score_total is not None and 1 <= it.score_total <= 10
        assert set(it.scores) == {"hook_strength", "target_audience_fit", "brand_consistency", "cta_quality", "originality", "expected_engagement"}
        assert it.suggested_time is not None


def test_generation_requires_brand(db):
    import pytest

    with pytest.raises(ValueError):
        generate_content(db)


def test_claude_generation_uses_brand_and_previous_insights(db, brand, fake_ai):
    db.add(Insight(kind="content", summary="s", data={"hook_patterns": ["질문형 훅이 잘 됨"]}))
    db.commit()
    res = generate_content(db, count=5, platforms=["instagram", "x"])
    assert res["source"] == "ai"
    gen_call = fake_ai.calls[0]
    prompt = gen_call["messages"][0]["content"]
    assert "Sakura Tea" in prompt and "질문형 훅이 잘 됨" in prompt  # 분석 결과가 다음 생성에 반영
    assert gen_call["output_config"]["format"]["type"] == "json_schema"
    assert gen_call["fallbacks"] == "default"
    items = db.query(ContentItem).order_by(ContentItem.id).all()
    assert len(items) == 5
    assert items[0].score_total == round((9 + 8 + 8 + 7 + 6 + 8) / 6, 1)
    assert all(i.source == "ai" for i in items)


def test_forbidden_words_go_to_draft(db, brand, fake_ai):
    from conftest import text_resp

    def bad(params):
        import json, re
        slots = json.loads(re.search(r"(\[\{\"slot\".*?\}\])", params["messages"][0]["content"], re.S).group(1))
        return text_resp({"candidates": [{"slot": s["slot"], "platform": s["platform"], "content_type": s["content_type"], "title": "t",
                                          "idea": "", "hook": "우리가 최고", "caption": "c", "script": "", "structure": [], "thread": [],
                                          "cta": "", "hashtags": [], "media_idea": "", "suggested_time_local": "", "rationale": ""} for s in slots]})

    fake_ai.queue.append(bad)
    generate_content(db, count=5)
    assert {i.status for i in db.query(ContentItem).all()} == {"DRAFT"}


def test_auto_approve_platform(db, brand):
    set_setting(db, "auto_approve", {"x": True})
    db.commit()
    generate_content(db, count=6, platforms=["instagram", "x"])
    statuses = {(i.platform, i.status) for i in db.query(ContentItem).all()}
    assert ("x", "SCHEDULED") in statuses
    assert ("instagram", "READY_FOR_REVIEW") in statuses
    assert ("instagram", "SCHEDULED") not in statuses


def test_ai_error_falls_back_to_mock(db, brand, fake_ai):
    import app.ai.client as client_mod

    orig = client_mod.ClaudeClient.create

    def create(self, purpose, **params):
        if purpose == "content_generation":
            raise AIError("down")
        return orig(self, purpose, **params)

    client_mod.ClaudeClient.create = create
    try:
        res = generate_content(db, count=5)
    finally:
        client_mod.ClaudeClient.create = orig
    assert res["source"] == "mock_ai"
    assert db.query(ContentItem).count() == 5


def test_refusal_raises_ai_error(fake_ai):
    import pytest
    from types import SimpleNamespace

    from app.ai.client import get_ai

    fake_ai.queue.append(SimpleNamespace(content=[], stop_reason="refusal", model="m", usage=None))
    with pytest.raises(AIError):
        get_ai().generate_json("x", "s", "p", {"type": "object", "properties": {}, "required": [], "additionalProperties": False})
