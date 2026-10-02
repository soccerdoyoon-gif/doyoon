from datetime import timedelta

from app.connectors import registry
from app.connectors.mock import MockConnector
from app.core.timeutil import utcnow
from app.models import ContentItem, EventLog, PostMetrics
from app.scheduler import jobs
from app.scheduler.runner import build_scheduler
from app.services.metrics_collector import collect_metrics
from app.services.publisher import publish_due


def _scheduled(db, platform="instagram", minutes_ago=1):
    item = ContentItem(platform=platform, title="t", caption="c", status="SCHEDULED", scheduled_at=utcnow() - timedelta(minutes=minutes_ago))
    db.add(item)
    db.commit()
    return item


def test_scheduler_has_all_jobs():
    sched = build_scheduler()
    ids = {j.id for j in sched.get_jobs()}
    assert {"publish_due", "collect_metrics", "daily_generation", "daily_analysis", "sync_ads", "ads_analysis", "daily_report", "weekly_report", "refresh_tokens"} <= ids


def test_publish_due_publishes_only_due_items(db):
    due = _scheduled(db)
    future = ContentItem(platform="x", title="f", caption="c", status="SCHEDULED", scheduled_at=utcnow() + timedelta(hours=2))
    approved = ContentItem(platform="x", title="a", caption="c", status="APPROVED")
    db.add_all([future, approved])
    db.commit()
    assert publish_due(db) == [due.id]
    db.refresh(due); db.refresh(future); db.refresh(approved)
    assert due.status == "PUBLISHED" and due.is_dry_run
    assert future.status == "SCHEDULED" and approved.status == "APPROVED"


def test_retry_backoff_1_5_15_then_stop(db):
    registry.set_override("instagram", MockConnector("instagram", fail_times=99))
    item = _scheduled(db)
    now = utcnow()
    expected = [1, 5, 15]
    for i, minutes in enumerate(expected, start=1):
        publish_due(db, now)
        db.refresh(item)
        assert item.status == "FAILED" and item.retry_count == i
        assert item.next_retry_at == now + timedelta(minutes=minutes)
        assert "임시 오류" in item.last_error
        now = item.next_retry_at
    publish_due(db, now)  # 4번째 실패 → 최종 실패
    db.refresh(item)
    assert item.retry_count == 4 and item.next_retry_at is None and item.status == "FAILED"
    assert publish_due(db, now + timedelta(days=1)) == []  # 무한 반복하지 않음
    assert len(item.attempts) == 4 and not any(a.success for a in item.attempts)


def test_retry_then_success(db):
    registry.set_override("x", MockConnector("x", fail_times=1))
    item = _scheduled(db, "x")
    now = utcnow()
    publish_due(db, now)
    db.refresh(item)
    assert item.status == "FAILED"
    publish_due(db, now + timedelta(minutes=1))
    db.refresh(item)
    assert item.status == "PUBLISHED" and item.last_error == ""


def test_collect_metrics_and_interval(db):
    item = _scheduled(db)
    publish_due(db)
    r1 = collect_metrics(db, now=utcnow() + timedelta(hours=5))
    assert r1["collected"] == 1
    r2 = collect_metrics(db, now=utcnow() + timedelta(hours=5, minutes=10))
    assert r2["skipped"] == 1
    m = db.query(PostMetrics).filter_by(content_id=item.id).one()
    assert m.source == "mock"  # dry run 게시물은 mock 성과


def test_jobs_run_and_errors_are_logged(db, brand, monkeypatch):
    jobs.job_publish_due()
    jobs.job_daily_generation()  # setup 미완료 → 아무것도 안 함
    assert db.query(ContentItem).count() == 0

    import app.services.publisher as pub

    def boom(db):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(pub, "publish_due", boom)
    jobs.job_publish_due()  # 예외가 밖으로 새지 않음
    assert db.query(EventLog).filter(EventLog.message.contains("kaboom")).count() == 1


def test_daily_generation_job_after_setup(db, brand):
    from app.services.app_settings import set_setting

    set_setting(db, "setup_completed", True)
    db.commit()
    jobs.job_daily_generation()
    assert db.query(ContentItem).count() >= 5
