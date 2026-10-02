from app.models import ContentItem, EventLog, PostMetrics
from app.services.app_settings import get_setting, set_setting
from app.services.events import log_event


def test_brand_and_content_roundtrip(db, brand):
    item = ContentItem(platform="instagram", title="hello", hashtags=["#a"], scores={"hook_strength": 7})
    db.add(item)
    db.commit()
    db.add(PostMetrics(content_id=item.id, likes=10, reach=100, engagement_rate=10.0))
    db.commit()
    db.refresh(item)
    assert item.status == "DRAFT"
    assert item.metrics[0].likes == 10
    assert item.metrics[0].impressions is None  # 제공 안 된 값은 null


def test_settings_defaults_and_merge(db):
    guard = get_setting(db, "budget_guard")
    assert guard["max_budget_change_percent"] == 10
    assert guard["ads_auto_execute"] is False
    set_setting(db, "budget_guard", {"daily_budget_limit": 5000})
    merged = get_setting(db, "budget_guard")
    assert merged["daily_budget_limit"] == 5000
    assert merged["max_budget_change_percent"] == 10  # 기본값 유지


def test_event_log_redacts_secrets(db, settings_env):
    settings_env(instagram_access_token="IGQVJ-super-secret-token-123")
    log_event("api_error", "failed with IGQVJ-super-secret-token-123", {"access_token": "abc", "url": "https://x?access_token=zzz"}, db=db)
    db.commit()
    row = db.query(EventLog).first()
    assert "super-secret" not in row.message
    assert row.details["access_token"] == "***REDACTED***"
    assert "zzz" not in row.details["url"]
