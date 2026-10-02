"""에이전트 파이프라인 (일본 시장 기본) 테스트 — 실제 Claude/SNS/이미지 API 호출 없음."""
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from PIL import Image

from app.agents import pipeline, posting_times, rules
from app.agents.pipeline import next_slots, run_pipeline
from app.core.config import get_settings
from app.core.timeutil import utcnow
from app.media import storage
from app.media.video import split_subtitle
from app.models import AdCreativeDraft, ContentIdea, ContentItem, GeneratedAsset, Insight, PipelineRun, PostMetrics

JST = ZoneInfo("Asia/Tokyo")
from app.media.video import ffmpeg_available

needs_ffmpeg = pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg 없음")


def test_japan_defaults(db):
    s = get_settings()
    assert (s.default_country, s.default_language, s.default_currency, s.timezone) == ("JP", "ja", "JPY", "Asia/Tokyo")
    from app.models import BrandProfile
    from app.services.app_settings import get_setting

    b = BrandProfile(brand_name="x")
    db.add(b)
    db.commit()
    assert b.language == "ja" and b.country == "JP" and b.target_customer == "日本在住の消費者"
    assert get_setting(db, "budget_guard")["currency"] == "JPY"
    assert get_setting(db, "ui_language") == "ja"
    assert get_setting(db, "platforms_enabled") == {"instagram": True, "facebook": False, "tiktok": True, "x": True}


@needs_ffmpeg
def test_mock_pipeline_builds_japanese_packages_with_media(db, brand):
    res = run_pipeline(db)
    items = db.query(ContentItem).all()
    assert len(items) >= 5  # 하루 최소 5개
    assert {i.platform for i in items} == {"instagram", "tiktok", "x"}
    assert all(i.language == "ja" for i in items)
    assert all(not rules.HANGUL.search(i.caption + i.hook) for i in items)  # 한국어 섞이지 않음
    assert set(res["ready_for_review"]) == {i.id for i in items}
    ideas = db.query(ContentIdea).all()
    assert len(ideas) == len(res["idea_ids"]) == 2
    for idea in ideas:  # 아이디어 1개 → 플랫폼별 별도 콘텐츠
        per = [i for i in items if i.idea_id == idea.id]
        assert sorted(i.platform for i in per) == ["instagram", "tiktok", "x"]
        assert len({i.caption for i in per}) == 3  # 같은 문구 복사 금지
    for it in items:
        kinds = {a.kind for a in it.assets}
        if it.platform == "tiktok" or it.content_type == "reel":
            assert {"video", "subtitle", "thumbnail"} <= kinds
            assert len(it.scenes) >= 4 and it.video_prompt
            v = [a for a in it.assets if a.kind == "video"][0]
            assert (v.width, v.height, v.aspect) == (1080, 1920, "9:16")
            assert storage.abs_path(v.path).exists() and f"c{it.id}_" in v.path
            srt = storage.abs_path([a for a in it.assets if a.kind == "subtitle"][0].path).read_text(encoding="utf-8")
            lines = [l for l in srt.splitlines() if l and "-->" not in l and not l.isdigit()]
            assert lines and all(len(l) <= 14 for l in lines)  # 자막은 짧게
        elif it.platform == "instagram" and it.content_type == "post":
            purposes = {a.purpose for a in it.assets}
            assert {"feed", "story"} <= purposes
        elif it.content_type == "carousel":
            assert len([a for a in it.assets if a.purpose == "carousel"]) >= 3
        elif it.platform == "x":
            assert not it.assets
        assert it.suggested_time and it.suggested_time > utcnow()
    ads = db.query(AdCreativeDraft).all()
    assert len(ads) == 2 and all(a.image_asset_id and a.idea_id for a in ads)
    assert db.query(Insight).filter_by(kind="trend").count() == 1


def test_generated_image_is_jpeg_with_content_id(db, brand):
    from app.media.creative import make_image

    item = ContentItem(platform="instagram", content_type="post", hook="これ、知らないと損。")
    db.add(item)
    db.flush()
    a = make_image(db, "feed", item.hook, brand_name="Sakura Tea", content_id=item.id)
    img = Image.open(storage.abs_path(a.path))
    assert img.format == "JPEG" and img.size == (1080, 1350)  # Instagram 4:5, JPEG
    assert img.getexif()[0x010E] == f"content_id={item.id}"
    assert a.path.startswith("images/c")


@needs_ffmpeg
def test_video_with_japanese_tts(db, brand):
    import io
    import wave

    from app.media.tts import set_tts_override
    from app.media.video import render_video

    class FakeTTS:
        calls = []

        def is_available(self):
            return True

        def synthesize(self, text, speaker, tone="casual"):
            self.calls.append((text, speaker, tone))
            buf = io.BytesIO()
            with wave.open(buf, "wb") as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
                w.writeframes(b"\x00\x00" * 24000 * 2)  # 2초
            return buf.getvalue()

    tts = FakeTTS()
    set_tts_override(tts)
    item = ContentItem(platform="tiktok", content_type="short_video", hook="3秒だけ見て。", thumbnail_text="3秒だけ見て",
                       scenes=[{"scene_id": 1, "duration": 1, "voiceover": "これ、知ってる？", "subtitle": "これ、知ってる？"}])
    db.add(item)
    db.flush()
    voice = {"enabled": True, "gender": "male", "tone": "calm", "speakers": {"male": {"calm": 13}, "female": {"casual": 8}}}
    assets = render_video(db, item, brand_name="Sakura Tea", voice_cfg=voice)
    video = [a for a in assets if a.kind == "video"][0]
    assert tts.calls == [("これ、知ってる？", 13, "calm")]
    assert video.duration >= 2.0 and video.meta["voice"] is True
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json",
                            str(storage.abs_path(video.path))], capture_output=True, text=True)
    streams = json.loads(probe.stdout)["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}
    assert [s for s in streams if s["codec_type"] == "video"][0]["width"] == 1080


def test_subtitle_split_short_chunks():
    chunks = split_subtitle("これ、知らないと損。正直、最初は期待してなかったんだけど本当に毎日使ってる。")
    assert chunks[0] == "これ、知らないと損。"
    assert all(len(c) <= 14 for c in chunks)
    assert "".join(chunks) == "これ、知らないと損。正直、最初は期待してなかったんだけど本当に毎日使ってる。"


def test_claude_pipeline_prompts_are_japan_first(db, brand, fake_ai):
    res = run_pipeline(db, platforms=["tiktok", "x"], idea_count=2, with_video=False)
    assert res["source"] == "ai"
    systems = [c.get("system", "") for c in fake_ai.calls]
    assert all("日本" in sys for sys in systems if sys)
    web = [c for c in fake_ai.calls if c.get("tools")][0]
    assert web["tools"][0]["user_location"]["country"] == "JP"
    t = db.query(Insight).filter_by(kind="trend").one()
    assert t.data["sources"][0]["url"] == "https://example.jp/trend" and t.data["evidence"] == "テスト" or t.data["sources"]
    items = db.query(ContentItem).all()
    assert len(items) == 4 and all(i.status == "READY_FOR_REVIEW" for i in items)
    assert all(i.score_total == round((9 + 8 + 8 + 7 + 6 + 8) / 6, 1) for i in items)
    tt = [i for i in items if i.platform == "tiktok"][0]
    assert tt.video_title == "朝の一杯" and tt.scenes[0]["visual"] == "東京の街を歩く若者"
    assert tt.hashtags == ["#おすすめ", "#購入品"]


def test_trend_cached_for_the_day(db, brand, fake_ai):
    run_pipeline(db, platforms=["x"], idea_count=1)
    run_pipeline(db, platforms=["x"], idea_count=1)
    assert db.query(Insight).filter_by(kind="trend").count() == 1
    assert len([c for c in fake_ai.calls if c.get("tools")]) == 1


def test_guardian_fixes_and_rejects(db, brand, fake_ai):
    def review(it, rv):
        if it["platform"] == "x":
            return {**rv, "verdict": "reject", "issues": [{"severity": "error", "field": "caption", "message": "誇大表現"}]}
        if it["platform"] == "tiktok":
            return {**rv, "verdict": "fix", "corrected": {**rv["corrected"], "caption": "自然な日本語に修正", "hashtags": ["#話題"]}}
        return rv

    fake_ai.review_override = review
    run_pipeline(db, platforms=["tiktok", "x"], idea_count=1, with_video=False)
    x = db.query(ContentItem).filter_by(platform="x").one()
    tt = db.query(ContentItem).filter_by(platform="tiktok").one()
    assert x.status == "DRAFT" and "Brand Guardian" in x.review_note
    assert tt.status == "READY_FOR_REVIEW" and tt.caption == "自然な日本語に修正" and tt.hashtags == ["#話題"]
    assert tt.guardian["verdict"] == "fix" and "caption" in tt.guardian["corrected_fields"]


def test_rules_hangul_forbidden_risky_and_x_length():
    it = ContentItem(platform="x", language="ja", caption="これは絶対に効く！！！ 안녕", hashtags=[], thread=[], scenes=[])
    issues = rules.check(it, ["奇跡"])
    msgs = " ".join(i["message"] for i in issues)
    assert "韓国語" in msgs and "絶対" in msgs and "感嘆符" in msgs
    assert any(i["severity"] == "error" for i in issues)
    assert rules.x_weighted_length("あ" * 140) == 280
    long_x = ContentItem(platform="x", language="ja", caption="あ" * 141, hashtags=[], thread=[], scenes=[])
    assert any("280" in i["message"] for i in rules.check(long_x, []))
    assert rules.check(ContentItem(platform="x", language="ja", caption="奇跡の一杯", hashtags=[], thread=[], scenes=[]), ["奇跡"])[0]["severity"] == "error"


def test_hashtag_normalize_and_overuse(db):
    assert rules.normalize_hashtags(["おすすめ", "#おすすめ", "＃話題", " #新作 "], "tiktok") == ["#おすすめ", "#話題", "#新作"]
    assert len(rules.normalize_hashtags([f"#t{i}" for i in range(20)], "x")) == 2
    for _ in range(3):
        db.add(ContentItem(platform="instagram", hashtags=["#おすすめ", "#新作"]))
    db.commit()
    assert set(rules.overused_hashtags(db)) == {"#おすすめ", "#新作"}


def _published(db, platform, jst_hour, er, days_ago=1, source="api"):
    d = datetime.now(JST).replace(hour=jst_hour, minute=0, second=0, microsecond=0) - timedelta(days=days_ago)
    it = ContentItem(platform=platform, status="PUBLISHED", published_at=d.astimezone(timezone.utc).replace(tzinfo=None))
    it.metrics.append(PostMetrics(likes=10, reach=100, engagement_rate=er, source=source))
    db.add(it)


def test_posting_time_learning_jst(db):
    ins = posting_times.learn(db)
    assert ins.data["platforms"]["tiktok"]["status"] == "testing"  # 데이터 없음 → 테스트 후보만
    for d in range(1, 4):
        _published(db, "tiktok", 21, 9.0, d)
        _published(db, "tiktok", 12, 2.0, d)
        _published(db, "tiktok", 7, 50.0, d, source="mock")  # mock 은 학습 제외
    db.commit()
    ins = posting_times.learn(db)
    tk = ins.data["platforms"]["tiktok"]
    assert tk["status"] == "learned" and tk["recommended"][0] == "21:00"
    assert "07" not in tk["hour_stats"]
    assert "21:00" in posting_times.slots_for(db, "tiktok")


def test_next_slots_future_jst_and_unique(db):
    slots = next_slots(db, "x", 5)
    assert len(slots) == len(set(slots)) == 5
    now = utcnow()
    for s in slots:
        assert s > now
        local = s.replace(tzinfo=timezone.utc).astimezone(JST)
        assert local.strftime("%H:%M") in ["07:30", "12:00", "18:30", "21:30"]


@needs_ffmpeg
def test_manager_command_tiktok_videos_mock(db, brand, monkeypatch):
    import app.ai.manager as manager

    monkeypatch.setattr(manager, "_BACKGROUND", False)
    res = manager.ask(db, "s1", "오늘 일본 TikTok용 영상 3개 만들어줘.")
    assert "[MOCK AI]" in res["answer"] and "TikTok".lower() in res["answer"].lower()
    run = db.query(PipelineRun).one()
    assert run.status == "DONE", run.error
    db.expire_all()
    run = db.query(PipelineRun).one()
    assert all(s["status"] == "done" and s.get("finished") for s in run.steps)  # 마지막 단계까지 저장
    assert [s["name"] for s in run.steps] == ["Trend Research", "Content Strategist", "Copywriter / Hashtag", "Short-form Script",
                                               "Creative Director", "Brand Guardian", "Image / Video Generation"]
    items = db.query(ContentItem).all()
    assert len(items) == 3 and {i.platform for i in items} == {"tiktok"}
    assert all(i.status == "READY_FOR_REVIEW" and any(a.kind == "video" for a in i.assets) for i in items)
    assert all(i.caption and i.hashtags and i.hook for i in items)


def test_publisher_uses_generated_media(db, brand, settings_env):
    settings_env(public_media_base_url="https://cdn.example.jp")
    from app.media.creative import make_image
    from app.services.publisher import build_request

    car = ContentItem(platform="instagram", content_type="carousel", hook="h")
    vid = ContentItem(platform="tiktok", content_type="short_video")
    db.add_all([car, vid])
    db.flush()
    for n in range(3):
        make_image(db, "carousel", f"{n}", content_id=car.id, order=n)
    p, rel = storage.new_file("video", "mp4", content_id=vid.id, purpose="tiktok")
    p.write_bytes(b"x")
    storage.record(db, "video", rel, content_id=vid.id, purpose="tiktok")
    db.commit()
    db.refresh(car); db.refresh(vid)
    r = build_request(car)
    assert len(r.media_urls) == 3 and r.media_urls[0].startswith("https://cdn.example.jp/generated/images/c")
    r2 = build_request(vid)
    assert r2.media_path.endswith(".mp4") and r2.media_url.endswith(rel)


def test_instagram_carousel_publish_flow(settings_env):
    import httpx

    from app.connectors.base import PublishRequest
    from app.connectors.instagram import InstagramConnector

    settings_env(dry_run="false", instagram_access_token="tok-abcdef", instagram_user_id="17")
    calls = []

    def handler(req):
        calls.append((req.method, req.url.path, dict(req.url.params)))
        if req.url.path.endswith("/17/media"):
            if req.url.params.get("media_type") == "CAROUSEL":
                assert req.url.params["children"] == "i0,i1"
                return httpx.Response(200, json={"id": "car"})
            return httpx.Response(200, json={"id": f"i{sum(1 for c in calls if c[2].get('is_carousel_item')) - 1}"})
        if req.url.path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "m9"})
        return httpx.Response(200, json={"status_code": "FINISHED", "permalink": "https://instagram.com/p/x"})

    c = InstagramConnector(http=httpx.Client(transport=httpx.MockTransport(handler)))
    res = c.publish(PublishRequest(1, "instagram", content_type="carousel", caption="キャプション",
                                   media_urls=["https://a/1.jpg", "https://a/2.jpg"]))
    assert res.external_id == "m9"
    assert [c[2].get("is_carousel_item") for c in calls[:2]] == ["true", "true"]


def test_migration_adds_missing_columns():
    from sqlalchemy import create_engine, inspect, text

    from app.core.migrate import add_missing_columns

    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.execute(text("CREATE TABLE content_items (id INTEGER PRIMARY KEY, platform VARCHAR(20))"))
        conn.execute(text("INSERT INTO content_items (platform) VALUES ('x')"))
    added = add_missing_columns(eng)
    assert "content_items.scenes" in added and "content_items.idea_id" in added
    cols = {c["name"] for c in inspect(eng).get_columns("content_items")}
    assert {"guardian", "thumbnail_text", "video_title"} <= cols
    with eng.connect() as conn:
        assert conn.execute(text("SELECT platform FROM content_items")).scalar() == "x"  # 데이터 유지


def test_language_override_only_when_requested(db, brand, fake_ai):
    run_pipeline(db, platforms=["x"], idea_count=1)
    run_pipeline(db, platforms=["x"], idea_count=1, language="ko")
    items = db.query(ContentItem).order_by(ContentItem.id).all()
    assert [i.language for i in items] == ["ja", "ko"]
    ko_calls = [c for c in fake_ai.calls if "韓国語" in c.get("system", "")]
    assert ko_calls  # ko 는 명시적으로 요청했을 때만


@needs_ffmpeg
def test_video_uses_bundled_ffmpeg_when_system_has_none(db, brand, monkeypatch):
    pytest.importorskip("imageio_ffmpeg")
    import app.media.video as video

    monkeypatch.setattr(video.shutil, "which", lambda name: None)  # 시스템 ffmpeg 없음
    item = ContentItem(platform="tiktok", content_type="short_video", hook="3秒だけ見て。",
                       scenes=[{"scene_id": 1, "duration": 1, "voiceover": "", "subtitle": "3秒だけ見て。"}])
    db.add(item)
    db.flush()
    assets = video.render_video(db, item, brand_name="Sakura Tea", voice_cfg={"enabled": False})
    assert storage.abs_path([a for a in assets if a.kind == "video"][0].path).stat().st_size > 1000
