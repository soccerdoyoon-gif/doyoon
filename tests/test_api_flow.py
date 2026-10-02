"""전체 흐름 통합 테스트 (Mock connector + Mock/Fake AI)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.core.timeutil import utcnow
from app.main import app


@pytest.fixture
def api():
    with TestClient(app) as c:
        yield c


SETUP = {
    "brand": {
        "brand_name": "Sakura Tea", "brand_description": "京都の緑茶ブランド", "product_description": "抹茶", "target_customer": "日本在住の会社員",
        "country": "JP", "language": "ja", "brand_voice": "落ち着いた", "forbidden_words": ["最強"], "competitors": ["Matcha Co"],
        "main_goal": "sales", "main_products": "抹茶パウダー",
    },
    "platforms_enabled": {"instagram": True, "tiktok": True, "x": True, "facebook": False},
    "secrets": {},
    "ads_enabled": True,
    "daily_budget_limit": 8000,
    "currency": "JPY",
}


def test_full_loop(api):
    assert api.get("/api/setup").json()["setup_completed"] is False
    r = api.post("/api/setup", json=SETUP)
    assert r.status_code == 200
    assert api.get("/api/ads/budget-guard").json()["daily_budget_limit"] == 8000
    assert api.get("/api/competitors").json()[0]["name"] == "Matcha Co"

    gen = api.post("/api/content/generate", json={"count": 2}).json()
    run = api.get(f"/api/pipeline/runs/{gen['run_id']}").json()
    assert run["status"] == "DONE", run["error"]
    assert len(run["result"]["created_ids"]) == 6  # 아이디어 2개 × Instagram/TikTok/X
    queue = api.get("/api/content", params={"status": "READY_FOR_REVIEW"}).json()
    assert len(queue) == 6 and all(q["language"] == "ja" for q in queue)
    pkg = api.get(f"/api/ideas/{run['result']['idea_ids'][0]}").json()
    assert len(pkg["contents"]) == 3 and pkg["ads"][0]["assets"]
    tiktok = [q for q in queue if q["platform"] == "tiktok"][0]
    video = [a for a in tiktok["assets"] if a["kind"] == "video"][0]
    assert api.get(video["url"]).status_code == 200  # /generated/... 로 파일 제공
    scores = [q["score_total"] for q in queue]
    assert scores == sorted(scores, reverse=True)  # 점수순 정렬

    cid = queue[0]["id"]
    when = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    approved = api.post(f"/api/content/{cid}/approve", json={"schedule_at": when}).json()
    assert approved["status"] == "SCHEDULED" and approved["scheduled_at"].endswith("Z")

    # 캘린더 drag & drop
    start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    cal = api.get("/api/calendar", params={"start": start, "end": end}).json()
    assert any(c["id"] == cid for c in cal)
    moved = api.patch(f"/api/calendar/{cid}", json={"scheduled_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()}).json()
    assert moved["status"] == "SCHEDULED"

    # 지금 게시 (DRY RUN)
    pub = api.post(f"/api/content/{cid}/publish-now").json()
    assert pub["status"] == "PUBLISHED" and pub["is_dry_run"] and pub["attempts"][0]["success"]
    assert api.put(f"/api/content/{cid}", json={"caption": "x"}).status_code == 400  # 게시 후 수정 불가

    # 일괄 승인
    others = [q["id"] for q in queue[1:]]
    bulk = api.post("/api/content/bulk-approve", json={"ids": others}).json()
    assert len(bulk["approved"]) == 5

    assert api.post("/api/analytics/collect").json()["collected"] == 1
    analysis = api.post("/api/analytics/analyze").json()
    assert analysis["kind"] == "content" and analysis["source"] == "mock_ai"

    assert api.post("/api/ads/sync").json()["source"] == "mock"
    ov = api.get("/api/ads/overview").json()
    assert ov["totals"]["spend"] > 0 and len(ov["by_ad"]) == 3
    ads_an = api.post("/api/ads/analyze").json()
    verdicts = {a["verdict"] for a in ads_an["data"]["ads"]}
    assert verdicts <= {"good", "watch", "poor", "insufficient_data"}
    creatives = api.post("/api/ads/creatives/generate", json={"count": 2}).json()
    assert len(creatives) == 2

    act = api.post("/api/ads/actions", json={"action_type": "budget_change", "target_level": "adset", "target_external_id": "mock_as1", "new_budget": 3300}).json()
    assert act["status"] == "PENDING"
    done = api.post(f"/api/ads/actions/{act['id']}/approve").json()
    assert done["status"] == "EXECUTED"

    dash = api.get("/api/dashboard").json()
    assert dash["cards"]["published_today"] == 1
    assert dash["cards"]["pending_review"] == 0
    assert len(dash["series"]) == 14 and dash["ads_7d"]["mock_data"] is True

    daily = api.post("/api/reports/daily").json()
    md = daily["content_md"]
    for section in ("## TODAY", "## Instagram", "## TikTok", "## X", "## Ads", "## BEST CONTENT", "## WORST CONTENT", "## AD PERFORMANCE", "## AI INSIGHTS", "## TOMORROW PLAN"):
        assert section in md
    weekly = api.post("/api/reports/weekly").json()
    for key in ("Total posts", "Total impressions", "Total views", "Total engagement", "Follower growth", "Spend: ¥", "Clicks", "Conversions", "CPA", "ROAS", "来週テストするアイデア"):
        assert key in weekly["content_md"]
    assert len(api.get("/api/reports").json()) == 2

    chat = api.post("/api/chat", json={"session_id": "s1", "message": "이번 주 Instagram 성과 어때?"}).json()
    assert chat["mode"] == "mock_ai" and "[MOCK AI]" in chat["answer"] and "게시 1개" in chat["answer"]
    assert "None" not in chat["answer"]
    assert len(api.get("/api/chat/s1").json()) == 2

    logs = api.get("/api/logs").json()
    cats = {l["category"] for l in logs}
    assert {"ai_generation", "post_attempt", "approval", "ad_data", "dry_run", "system"} <= cats


def test_workflow_rules(api):
    api.post("/api/setup", json=SETUP)
    c = api.post("/api/content", json={"platform": "x", "caption": "hello", "content_type": "tweet"}).json()
    assert c["status"] == "DRAFT"
    assert api.post(f"/api/content/{c['id']}/schedule", json={"scheduled_at": utcnow().isoformat()}).status_code == 400
    assert api.post(f"/api/content/{c['id']}/publish-now").status_code == 400  # 승인 전 게시 불가
    assert api.post(f"/api/content/{c['id']}/submit").json()["status"] == "READY_FOR_REVIEW"
    a = api.post(f"/api/content/{c['id']}/approve", json={"use_suggested_time": False}).json()
    assert a["status"] == "APPROVED"
    # 승인 후 문구 수정 → 재승인 필요
    assert api.put(f"/api/content/{c['id']}", json={"caption": "changed"}).json()["status"] == "READY_FOR_REVIEW"
    # 금지어 포함 시 승인 거부
    api.put(f"/api/content/{c['id']}", json={"caption": "うちが最強"})
    r = api.post(f"/api/content/{c['id']}/approve", json={})
    assert r.status_code == 400 and "금지어" in r.json()["detail"]
    assert api.post(f"/api/content/{c['id']}/reject", json={"note": "no"}).json()["status"] == "REJECTED"


def test_secrets_are_masked(api, settings_env):
    r = api.post("/api/settings/secrets", json={"secrets": {"ANTHROPIC_API_KEY": "sk-ant-test-1234567890abcd"}})
    assert r.json()["saved"] == ["ANTHROPIC_API_KEY"]
    s = api.get("/api/settings").json()
    assert s["secrets"]["ANTHROPIC_API_KEY"] == {"configured": True, "masked": "****abcd"}
    import json as _j
    assert "sk-ant-test-1234567890abcd" not in _j.dumps(s)
    assert api.post("/api/settings/secrets", json={"secrets": {"PASSWORD": "x"}}).status_code == 400
    # 정리
    from app.core.config import get_settings, reload_settings
    get_settings().secrets_file.unlink()
    import os
    os.environ["ANTHROPIC_API_KEY"] = ""
    reload_settings()


def test_settings_auto_approve_toggle(api):
    r = api.put("/api/settings/auto_approve", json={"value": {"x": True}})
    assert r.json()["x"] is True and r.json()["instagram"] is False
    assert api.put("/api/settings/setup_completed", json={"value": True}).status_code == 400


def test_abtest_insufficient_data_no_winner(api):
    t = api.post("/api/abtests", json={"name": "Hook test", "variable": "hook", "metric": "ctr", "variant_a": "질문형", "variant_b": "숫자형"}).json()
    va, vb = t["variants"]
    api.put(f"/api/abtests/{t['id']}/variants/{va['id']}", json={"impressions": 300, "clicks": 9, "engagements": 0, "conversions": 0})
    api.put(f"/api/abtests/{t['id']}/variants/{vb['id']}", json={"impressions": 300, "clicks": 2, "engagements": 0, "conversions": 0})
    res = api.post(f"/api/abtests/{t['id']}/evaluate").json()
    assert res["result"]["verdict"] == "insufficient_data" and res["result"]["winner"] is None
    assert res["test"]["status"] == "RUNNING"
    api.put(f"/api/abtests/{t['id']}/variants/{va['id']}", json={"impressions": 10000, "clicks": 300, "engagements": 0, "conversions": 0})
    api.put(f"/api/abtests/{t['id']}/variants/{vb['id']}", json={"impressions": 10000, "clicks": 180, "engagements": 0, "conversions": 0})
    res = api.post(f"/api/abtests/{t['id']}/evaluate").json()
    assert res["result"]["verdict"] == "significant" and res["result"]["winner"] == "A"


def test_competitor_observation_and_analysis(api):
    c = api.post("/api/competitors", json={"name": "Matcha Co", "platform": "instagram"}).json()
    api.post(f"/api/competitors/{c['id']}/observations", json={"topic": "레시피", "content_format": "reel", "hook_pattern": "질문형", "posts_per_week": 4})
    ins = api.post("/api/competitors/analyze").json()
    assert ins["kind"] == "competitor" and ins["data"]["differentiation_ideas"]


def test_manager_uses_tools_with_claude(api, fake_ai):
    from conftest import _resp

    api.post("/api/setup", json=SETUP)
    tool_call = _resp([SimpleNamespace(type="tool_use", id="tu1", name="get_content_performance", input={"days": 7, "platform": "instagram"})], stop_reason="tool_use")
    final = _resp([SimpleNamespace(type="text", text="이번 주 Instagram 게시물이 없습니다.")])
    fake_ai.queue += [tool_call, final]
    res = api.post("/api/chat", json={"session_id": "s2", "message": "이번 주 Instagram 성과 어때?"}).json()
    assert res["tools_used"] == ["get_content_performance"]
    assert res["answer"] == "이번 주 Instagram 게시물이 없습니다."
    second = fake_ai.calls[1]["messages"]
    assert second[-2]["content"][0]["type"] == "tool_result" and '"post_count": 0' in second[-2]["content"][0]["content"]


def test_oauth_start_requires_client_id(api, settings_env):
    assert api.get("/api/oauth/x/start").status_code == 400
    settings_env(x_client_id="cid", public_base_url="http://localhost:8000")
    r = api.get("/api/oauth/x/start").json()
    assert r["authorize_url"].startswith("https://x.com/i/oauth2/authorize?") and "code_challenge_method=S256" in r["authorize_url"]
    assert r["redirect_uri"] == "http://localhost:8000/api/oauth/x/callback"
    bad = api.get("/api/oauth/x/callback", params={"code": "c", "state": "nope"}, follow_redirects=False)
    assert bad.status_code in (302, 307) and "status=error" in bad.headers["location"]


def test_system_status(api):
    s = api.get("/api/system/status").json()
    assert s["dry_run"] is True and s["ai_mode"] == "mock"
    assert s["connectors"]["tiktok"]["mode"] == "mock"
