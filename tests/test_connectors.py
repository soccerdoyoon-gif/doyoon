"""Connector 테스트 — httpx.MockTransport 로 공식 API 응답을 흉내냅니다 (실제 호출 없음)."""
import json
from datetime import date

import httpx
import pytest

from app.connectors.base import ConnectorError, PublishRequest
from app.connectors.facebook import FacebookConnector
from app.connectors.instagram import InstagramConnector
from app.connectors.meta_ads import MetaAdsConnector, MockMetaAdsConnector, parse_insight_row
from app.connectors.mock import MockConnector
from app.connectors.registry import get_ads_connector, get_connector
from app.connectors.tiktok import TikTokConnector
from app.connectors.x import XConnector


def client(handler, log):
    def wrapped(request: httpx.Request):
        log.append(request)
        return handler(request)

    return httpx.Client(transport=httpx.MockTransport(wrapped))


@pytest.fixture
def live(settings_env):
    return settings_env(
        dry_run="false",
        instagram_access_token="ig-token-abcdef",
        instagram_user_id="1784",
        facebook_page_id="55",
        facebook_page_access_token="fb-token-abcdef",
        tiktok_access_token="tt-token-abcdef",
        x_access_token="x-token-abcdef",
        meta_ads_access_token="ads-token-abcdef",
        meta_ad_account_id="999",
    )


def test_registry_uses_mock_without_credentials():
    assert isinstance(get_connector("instagram"), MockConnector)
    assert isinstance(get_connector("x"), MockConnector)
    assert isinstance(get_ads_connector(), MockMetaAdsConnector)
    with pytest.raises(ValueError):
        get_connector("myspace")


def test_registry_uses_real_connector_when_configured(live):
    assert isinstance(get_connector("instagram"), InstagramConnector)
    assert isinstance(get_ads_connector(), MetaAdsConnector)


def test_instagram_publish_flow(live):
    log = []

    def handler(req):
        path = req.url.path
        if path.endswith("/1784/media"):
            assert req.url.params["image_url"] == "https://cdn.example.com/a.jpg"
            assert "#matcha" in req.url.params["caption"]
            return httpx.Response(200, json={"id": "c1"})
        if path.endswith("/c1"):
            return httpx.Response(200, json={"status_code": "FINISHED"})
        if path.endswith("/media_publish"):
            return httpx.Response(200, json={"id": "m1"})
        if path.endswith("/m1"):
            return httpx.Response(200, json={"permalink": "https://instagram.com/p/xyz"})
        return httpx.Response(404, json={})

    c = InstagramConnector(http=client(handler, log))
    res = c.publish(PublishRequest(1, "instagram", caption="hi", hashtags=["matcha"], media_url="https://cdn.example.com/a.jpg"))
    assert res.success and res.external_id == "m1" and res.url.endswith("xyz") and not res.dry_run
    assert log[0].url.host == "graph.instagram.com" and "/v26.0/" in log[0].url.path


def test_instagram_requires_media(live):
    c = InstagramConnector(http=client(lambda r: httpx.Response(500), []))
    with pytest.raises(ConnectorError) as e:
        c.publish(PublishRequest(1, "instagram", caption="hi"))
    assert e.value.retryable is False


def test_instagram_metrics_missing_values_are_null(live):
    def handler(req):
        return httpx.Response(200, json={"data": [
            {"name": "reach", "values": [{"value": 1000}]},
            {"name": "likes", "values": [{"value": 50}]},
            {"name": "saved", "total_value": {"value": 7}},
        ]})

    m = InstagramConnector(http=client(handler, [])).get_metrics("m1")
    assert m.reach == 1000 and m.likes == 50 and m.saves == 7
    assert m.impressions is None and m.clicks is None and m.comments is None
    assert m.engagement_rate == round(57 / 1000 * 100, 3)


def test_http_error_is_redacted_and_classified(live):
    def handler(req):
        return httpx.Response(400, json={"error": {"message": "bad", "access_token": "ig-token-abcdef"}})

    with pytest.raises(ConnectorError) as e:
        InstagramConnector(http=client(handler, [])).publish(PublishRequest(1, "instagram", media_url="https://a/b.jpg"))
    assert e.value.retryable is False and e.value.status_code == 400
    assert "ig-token-abcdef" not in json.dumps(e.value.response)


def test_rate_limit_is_retryable(live):
    with pytest.raises(ConnectorError) as e:
        FacebookConnector(http=client(lambda r: httpx.Response(429, json={"error": {"message": "slow down"}}), [])).publish(
            PublishRequest(1, "facebook", caption="hi"))
    assert e.value.retryable is True


def test_facebook_text_post(live):
    log = []
    res = FacebookConnector(http=client(lambda r: httpx.Response(200, json={"id": "55_1"}), log)).publish(
        PublishRequest(1, "facebook", caption="hello"))
    assert res.external_id == "55_1" and log[0].url.path.endswith("/55/feed")


def test_x_thread_posting(live):
    log = []
    counter = iter(range(100, 200))

    def handler(req):
        return httpx.Response(201, json={"data": {"id": str(next(counter))}})

    res = XConnector(http=client(handler, log)).publish(PublishRequest(1, "x", content_type="thread", thread=["one", "two", "three"]))
    bodies = [json.loads(r.content) for r in log]
    assert res.external_id == "100" and res.raw["thread_ids"] == ["100", "101", "102"]
    assert "reply" not in bodies[0] and bodies[1]["reply"]["in_reply_to_tweet_id"] == "100"
    assert log[0].headers["authorization"] == "Bearer x-token-abcdef"
    assert str(log[0].url) == "https://api.x.com/2/tweets"


def test_x_rejects_long_text(live):
    with pytest.raises(ConnectorError):
        XConnector(http=client(lambda r: httpx.Response(201), [])).publish(PublishRequest(1, "x", caption="a" * 300))


def test_x_metrics(live):
    def handler(req):
        return httpx.Response(200, json={"data": {"id": "1", "public_metrics": {"like_count": 5, "reply_count": 1, "retweet_count": 2, "quote_count": 1, "bookmark_count": 3, "impression_count": 400}}})

    m = XConnector(http=client(handler, [])).get_metrics("1")
    assert (m.likes, m.comments, m.shares, m.saves, m.impressions) == (5, 1, 3, 3, 400)
    assert m.reach is None


def test_tiktok_pull_from_url_flow(live):
    log = []

    def handler(req):
        p = req.url.path
        if p.endswith("creator_info/query/"):
            return httpx.Response(200, json={"data": {"privacy_level_options": ["SELF_ONLY"]}, "error": {"code": "ok"}})
        if p.endswith("video/init/"):
            body = json.loads(req.content)
            assert body["source_info"]["source"] == "PULL_FROM_URL" and body["post_info"]["privacy_level"] == "SELF_ONLY"
            return httpx.Response(200, json={"data": {"publish_id": "pub1"}, "error": {"code": "ok"}})
        if p.endswith("status/fetch/"):
            return httpx.Response(200, json={"data": {"status": "PUBLISH_COMPLETE", "publicaly_available_post_id": [7300]}, "error": {"code": "ok"}})
        return httpx.Response(404)

    res = TikTokConnector(http=client(handler, log)).publish(
        PublishRequest(1, "tiktok", content_type="short_video", caption="c", media_url="https://cdn.example.com/v.mp4"))
    assert res.external_id == "7300"
    assert log[0].url.host == "open.tiktokapis.com"


def test_tiktok_requires_video(live):
    with pytest.raises(ConnectorError) as e:
        TikTokConnector(http=client(lambda r: httpx.Response(200), [])).publish(PublishRequest(1, "tiktok", caption="text only"))
    assert e.value.retryable is False


def test_tiktok_api_error_code(live):
    def handler(req):
        return httpx.Response(200, json={"data": {}, "error": {"code": "spam_risk_too_many_posts", "message": "too many"}})

    with pytest.raises(ConnectorError) as e:
        TikTokConnector(http=client(handler, [])).publish(PublishRequest(1, "tiktok", content_type="short_video", media_url="https://a/v.mp4"))
    assert "spam_risk" in str(e.value)


def test_meta_ads_parse_insight_row():
    row = parse_insight_row({
        "ad_id": "1", "ad_name": "A", "campaign_id": "c", "adset_id": "s", "date_start": "2026-09-30",
        "spend": "1000", "impressions": "5000", "clicks": "100", "ctr": "2.0", "cpc": "10", "cpm": "200",
        "actions": [{"action_type": "link_click", "value": "100"}, {"action_type": "purchase", "value": "4"}],
        "action_values": [{"action_type": "purchase", "value": "12000"}],
    })
    assert row["date"] == date(2026, 9, 30)
    assert row["conversions"] == 4 and row["cpa"] == 250 and row["roas"] == 12.0
    assert row["reach"] is None


def test_meta_ads_fetch(live):
    def handler(req):
        p = req.url.path
        if p.endswith("/campaigns"):
            return httpx.Response(200, json={"data": [{"id": "c1", "name": "C", "status": "ACTIVE", "daily_budget": "5000"}]})
        if p.endswith("/adsets"):
            return httpx.Response(200, json={"data": [{"id": "s1", "name": "S", "status": "ACTIVE", "campaign_id": "c1"}]})
        if p.endswith("/ads"):
            return httpx.Response(200, json={"data": [{"id": "a1", "name": "Ad", "status": "ACTIVE", "adset_id": "s1"}]})
        if p.endswith("/insights"):
            assert req.url.params["level"] == "ad"
            return httpx.Response(200, json={"data": [{"ad_id": "a1", "date_start": "2026-10-01", "spend": "300"}]})
        return httpx.Response(404)

    snap = MetaAdsConnector(http=client(handler, []), currency="JPY").fetch(date(2026, 10, 1), date(2026, 10, 1))
    camp = [e for e in snap.entities if e["level"] == "campaign"][0]
    assert camp["daily_budget"] == 5000.0  # JPY 는 소수 단위 없음
    assert snap.insights[0]["spend"] == 300.0 and snap.insights[0]["conversions"] is None


def test_mock_metrics_are_marked_mock():
    m = MockConnector("instagram").get_metrics("x1", 24)
    assert m.source == "mock" and m.likes is not None and m.followers_gained is None
