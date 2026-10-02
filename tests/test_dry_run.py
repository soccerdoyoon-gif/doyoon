import httpx

from app.connectors.base import PublishRequest
from app.connectors.instagram import InstagramConnector
from app.connectors.meta_ads import MetaAdsConnector
from app.connectors.x import XConnector
from app.core.config import get_settings
from app.models import ContentItem, EventLog
from app.services.publisher import publish_item


def _explode(request):
    raise AssertionError(f"DRY RUN 인데 외부 API 호출 발생: {request.url}")


def no_network():
    return httpx.Client(transport=httpx.MockTransport(_explode))


def test_dry_run_is_default():
    assert get_settings().dry_run is True


def test_configured_connector_does_not_call_api_in_dry_run(settings_env):
    settings_env(dry_run="true", instagram_access_token="tok-123456", instagram_user_id="1", x_access_token="tok-123456")
    for c in (InstagramConnector(http=no_network()), XConnector(http=no_network())):
        res = c.publish(PublishRequest(7, c.platform, caption="안녕하세요", media_url="https://a/b.jpg"))
        assert res.dry_run and res.simulated
        assert "게시했을 것" in res.message


def test_ads_budget_change_dry_run_message(settings_env):
    settings_env(dry_run="true", meta_ads_access_token="tok-123456", meta_ad_account_id="1")
    res = MetaAdsConnector(http=no_network(), currency="JPY").update_budget("123", 5000, 5500)
    assert res.dry_run
    assert res.message == "[DRY RUN] Meta 광고 예산을 5,000 JPY → 5,500 JPY 로 변경했을 것 (대상 123)"
    assert MetaAdsConnector(http=no_network()).set_status("123", "PAUSED").dry_run


def test_publisher_logs_dry_run_event(db, settings_env):
    settings_env(dry_run="true", instagram_access_token="tok-123456", instagram_user_id="1")
    item = ContentItem(platform="instagram", caption="hello", status="SCHEDULED", media_url="https://a/b.jpg")
    db.add(item)
    db.commit()
    publish_item(db, item)
    assert item.status == "PUBLISHED" and item.is_dry_run
    ev = db.query(EventLog).filter_by(category="dry_run").one()
    assert "Instagram".lower() in ev.message.lower() and "게시했을 것" in ev.message
