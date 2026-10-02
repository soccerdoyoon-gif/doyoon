import pytest

from app.models import AdEntity, AdInsightDaily, PendingAction
from app.services.ads_service import approve_action, local_today, reject_action, request_action, sync_ads
from app.services.app_settings import set_setting
from app.services.budget_guard import evaluate_action

CFG = {"daily_budget_limit": 10000, "max_budget_change_percent": 10, "approval_required_above": 1000, "ads_auto_execute": True}


def test_small_change_can_auto_execute():
    d = evaluate_action("budget_change", CFG, current_budget=5000, new_budget=5500, current_total_daily_budget=5000)
    assert d.allowed and not d.requires_approval and d.change_percent == 10.0


def test_change_over_10_percent_needs_approval():
    d = evaluate_action("budget_change", CFG, current_budget=5000, new_budget=5600, current_total_daily_budget=5000)
    assert d.allowed and d.requires_approval


def test_decrease_over_10_percent_needs_approval():
    d = evaluate_action("budget_change", CFG, current_budget=5000, new_budget=4000, current_total_daily_budget=5000)
    assert d.requires_approval


def test_over_daily_limit_is_blocked():
    d = evaluate_action("budget_change", CFG, current_budget=5000, new_budget=5400, current_total_daily_budget=9800)
    assert not d.allowed and d.requires_approval


def test_increase_blocked_when_spend_reached_limit():
    d = evaluate_action("budget_change", CFG, current_budget=1000, new_budget=1050, current_total_daily_budget=2000, today_spend=10000)
    assert not d.allowed


def test_absolute_amount_threshold():
    d = evaluate_action("budget_change", {**CFG, "approval_required_above": 100}, current_budget=5000, new_budget=5300, current_total_daily_budget=5000)
    assert d.requires_approval


def test_auto_execute_off_by_default_requires_approval():
    d = evaluate_action("budget_change", {**CFG, "ads_auto_execute": False}, current_budget=5000, new_budget=5100, current_total_daily_budget=5000)
    assert d.allowed and d.requires_approval


@pytest.mark.parametrize("action", ["pause", "delete", "create_campaign", "billing_change", "resume"])
def test_risky_actions_always_need_approval(action):
    d = evaluate_action(action, {**CFG, "ads_auto_execute": True})
    assert d.requires_approval


def test_invalid_budget_blocked():
    assert not evaluate_action("budget_change", CFG, current_budget=100, new_budget=-5).allowed


# ---- service level (mock ads) --------------------------------------------
def test_request_and_approve_budget_change_dry_run(db):
    sync_ads(db, days=3)
    adset = db.query(AdEntity).filter_by(external_id="mock_as1").one()
    assert adset.daily_budget == 3000
    a = request_action(db, "budget_change", "adset", "mock_as1", new_budget=3300, reason="성과 양호")
    assert a.status == "PENDING"  # 기본: 자동 실행 꺼짐 → 승인 필요
    a = approve_action(db, a)
    assert a.status == "EXECUTED"
    assert "3,000" in a.result and "3,300" in a.result and "했을 것" in a.result
    db.refresh(adset)
    assert adset.daily_budget == 3000  # dry run 에서는 실제 값 변경 없음


def test_auto_execute_within_guard(db):
    sync_ads(db, days=1)
    set_setting(db, "budget_guard", {"ads_auto_execute": True})
    db.commit()
    a = request_action(db, "budget_change", "adset", "mock_as2", new_budget=2100)
    assert a.status == "EXECUTED"
    big = request_action(db, "budget_change", "adset", "mock_as2", new_budget=4000)
    assert big.status == "PENDING"


def test_over_limit_blocked_even_if_approved_later(db):
    sync_ads(db, days=1)
    set_setting(db, "budget_guard", {"daily_budget_limit": 6000})
    db.commit()
    a = request_action(db, "budget_change", "adset", "mock_as1", new_budget=3500)  # total 5500 → OK, but >10% → pending
    assert a.status == "PENDING"
    set_setting(db, "budget_guard", {"daily_budget_limit": 5200})  # 한도를 줄임
    db.commit()
    a = approve_action(db, a)
    assert a.status == "BLOCKED"
    blocked = request_action(db, "budget_change", "adset", "mock_as1", new_budget=9000)
    assert blocked.status == "BLOCKED"


def test_delete_is_never_executed_automatically(db):
    sync_ads(db, days=1)
    a = request_action(db, "delete", "ad", "mock_ad2")
    assert a.status == "PENDING"
    a = approve_action(db, a)
    assert a.status == "APPROVED" and "Ads Manager" in a.result


def test_reject_action(db):
    sync_ads(db, days=1)
    a = request_action(db, "pause", "ad", "mock_ad2")
    a = reject_action(db, a, "아직 유지")
    assert a.status == "REJECTED"
    with pytest.raises(ValueError):
        approve_action(db, a)


def test_sync_ads_is_idempotent(db):
    sync_ads(db, days=3)
    n = db.query(AdInsightDaily).count()
    sync_ads(db, days=3)
    assert db.query(AdInsightDaily).count() == n == 9
    assert db.query(AdInsightDaily).filter_by(date=local_today()).count() == 3
