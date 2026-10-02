"""광고 데이터 동기화 + 승인 기반 광고 작업 실행.

실제 돈이 쓰이는 작업은 Budget Guard 를 통과하고, 기본적으로 사용자 승인 후에만 실행됩니다.
삭제 / 캠페인 생성 / 결제 설정 변경은 이 시스템에서 API 로 실행하지 않습니다 (Ads Manager 에서 직접).
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError
from app.connectors.registry import get_ads_connector
from app.core.timeutil import to_local, utcnow
from app.models import AdEntity, AdInsightDaily, PendingAction
from app.models.enums import ActionStatus as A
from app.models.enums import AdActionType
from app.services.app_settings import get_setting
from app.services.budget_guard import evaluate_action
from app.services.events import log_event

MANUAL_ONLY = {AdActionType.DELETE.value, AdActionType.CREATE_CAMPAIGN.value, AdActionType.BILLING_CHANGE.value}


def local_today() -> date:
    return to_local(utcnow()).date()


def sync_ads(db: Session, days: int = 14) -> dict:
    guard = get_setting(db, "budget_guard")
    connector = get_ads_connector(guard.get("currency", "JPY"))
    until = local_today()
    since = until - timedelta(days=days - 1)
    try:
        snap = connector.fetch(since, until)
    except ConnectorError as exc:
        log_event("api_error", f"광고 데이터 수집 실패: {exc}", {"response": exc.response}, level="ERROR", db=db)
        db.commit()
        raise
    for e in snap.entities:
        row = db.scalar(select(AdEntity).where(AdEntity.level == e["level"], AdEntity.external_id == e["external_id"]))
        if row is None:
            row = AdEntity(level=e["level"], external_id=e["external_id"])
            db.add(row)
        for k in ("parent_external_id", "name", "status", "objective", "daily_budget", "creative_summary"):
            if k in e:
                setattr(row, k, e[k] if e[k] is not None or k == "daily_budget" else getattr(row, k))
        row.source = snap.source
    for r in snap.insights:
        row = db.scalar(
            select(AdInsightDaily).where(
                AdInsightDaily.level == r["level"], AdInsightDaily.external_id == r["external_id"], AdInsightDaily.date == r["date"]
            )
        )
        if row is None:
            row = AdInsightDaily(level=r["level"], external_id=r["external_id"], date=r["date"])
            db.add(row)
        for k, v in r.items():
            if k not in ("level", "external_id", "date"):
                setattr(row, k, v)
        row.source = snap.source
    log_event(
        "ad_data",
        f"광고 데이터 업데이트: 구조 {len(snap.entities)}건, 일별 성과 {len(snap.insights)}건 ({snap.source})",
        {"since": since.isoformat(), "until": until.isoformat()},
        db=db,
    )
    db.commit()
    return {"entities": len(snap.entities), "insights": len(snap.insights), "source": snap.source}


def budget_state(db: Session) -> tuple[float, float]:
    total = db.scalar(
        select(func.coalesce(func.sum(AdEntity.daily_budget), 0)).where(
            AdEntity.status == "ACTIVE", AdEntity.daily_budget.is_not(None)
        )
    )
    spend = db.scalar(select(func.coalesce(func.sum(AdInsightDaily.spend), 0)).where(AdInsightDaily.date == local_today()))
    return float(total or 0), float(spend or 0)


def _find_entity(db: Session, level: str, external_id: str) -> AdEntity | None:
    q = select(AdEntity).where(AdEntity.external_id == external_id)
    if level:
        q = q.where(AdEntity.level == level)
    return db.scalar(q)


def _evaluate(db: Session, action: PendingAction) -> dict:
    guard_cfg = get_setting(db, "budget_guard")
    total, spend = budget_state(db)
    entity = _find_entity(db, action.target_level, action.target_external_id)
    current = action.payload.get("current_budget")
    if entity is not None and entity.daily_budget is not None:
        current = entity.daily_budget
    decision = evaluate_action(
        action.action_type,
        guard_cfg,
        current_budget=current,
        new_budget=action.payload.get("new_budget"),
        current_total_daily_budget=total,
        today_spend=spend,
    )
    result = decision.to_dict()
    result["current_budget"] = current
    return result


def request_action(
    db: Session,
    action_type: str,
    target_level: str,
    target_external_id: str,
    new_budget: float | None = None,
    reason: str = "",
    requested_by: str = "user",
) -> PendingAction:
    entity = _find_entity(db, target_level, target_external_id)
    payload = {"new_budget": new_budget, "current_budget": entity.daily_budget if entity else None}
    action = PendingAction(
        action_type=action_type,
        target_level=target_level,
        target_external_id=target_external_id,
        target_name=entity.name if entity else "",
        payload=payload,
        reason=reason,
        requested_by=requested_by,
    )
    db.add(action)
    db.flush()
    guard = _evaluate(db, action)
    action.guard_result = guard
    if not guard["allowed"]:
        action.status = A.BLOCKED
        log_event("budget_change", f"광고 작업 차단 #{action.id}: {'; '.join(guard['reasons'])}", {"payload": payload}, level="WARNING", db=db)
    elif guard["can_auto_execute"] and action_type not in MANUAL_ONLY:
        log_event("budget_change", f"Budget Guard 통과 — 자동 실행 #{action.id}", db=db)
        _execute(db, action)
    else:
        action.status = A.PENDING
        log_event("approval", f"광고 작업 승인 대기 #{action.id} ({action_type} {target_external_id})", {"reasons": guard["reasons"]}, db=db)
    db.commit()
    return action


def _execute(db: Session, action: PendingAction) -> None:
    guard_cfg = get_setting(db, "budget_guard")
    connector = get_ads_connector(guard_cfg.get("currency", "JPY"))
    try:
        if action.action_type == AdActionType.BUDGET_CHANGE.value:
            res = connector.update_budget(
                action.target_external_id, action.guard_result.get("current_budget"), float(action.payload["new_budget"])
            )
            if res.success and not res.dry_run:
                entity = _find_entity(db, action.target_level, action.target_external_id)
                if entity:
                    entity.daily_budget = float(action.payload["new_budget"])
        elif action.action_type == AdActionType.PAUSE.value:
            res = connector.set_status(action.target_external_id, "PAUSED")
        elif action.action_type == AdActionType.RESUME.value:
            res = connector.set_status(action.target_external_id, "ACTIVE")
        else:
            action.status = A.APPROVED
            action.result = "이 작업은 안전을 위해 자동 실행하지 않습니다. Meta Ads Manager 에서 직접 진행하세요."
            return
    except ConnectorError as exc:
        action.status = A.FAILED
        action.result = str(exc)
        log_event("api_error", f"광고 작업 실패 #{action.id}: {exc}", {"response": exc.response}, level="ERROR", db=db)
        return
    action.status = A.EXECUTED if res.success else A.FAILED
    action.executed_at = utcnow()
    action.result = res.message
    log_event("dry_run" if res.dry_run else "budget_change", res.message, {"action_id": action.id}, db=db)


def approve_action(db: Session, action: PendingAction) -> PendingAction:
    if action.status != A.PENDING:
        raise ValueError(f"승인 대기 상태가 아닙니다 ({action.status}).")
    # 승인 시점에 다시 한 번 Budget Guard 확인 (그 사이 예산/지출이 바뀌었을 수 있음)
    guard = _evaluate(db, action)
    action.guard_result = guard
    action.decided_at = utcnow()
    if not guard["allowed"]:
        action.status = A.BLOCKED
        log_event("budget_change", f"승인했지만 Budget Guard 한도 초과로 차단 #{action.id}", {"reasons": guard["reasons"]}, level="WARNING", db=db)
    else:
        log_event("approval", f"광고 작업 승인 #{action.id}", db=db)
        _execute(db, action)
    db.commit()
    return action


def reject_action(db: Session, action: PendingAction, note: str = "") -> PendingAction:
    if action.status != A.PENDING:
        raise ValueError(f"승인 대기 상태가 아닙니다 ({action.status}).")
    action.status = A.REJECTED
    action.decided_at = utcnow()
    action.result = note
    log_event("approval", f"광고 작업 거절 #{action.id}", {"note": note}, db=db)
    db.commit()
    return action
