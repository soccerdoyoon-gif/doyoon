from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.analyzer import analyze_ads, generate_ad_creatives
from app.analytics.stats import ads_by_ad, ads_summary
from app.api.deps import get_or_404
from app.api.schemas import AdActionIn, CreativeGenIn, NoteIn, SettingValue
from app.api.serializers import to_dict
from app.connectors.base import ConnectorError
from app.core.database import get_db
from app.models import AdCreativeDraft, AdEntity, PendingAction
from app.services import ads_service
from app.services.app_settings import get_setting, set_setting
from app.services.events import log_event

router = APIRouter(prefix="/api/ads", tags=["ads"])


@router.post("/sync")
def sync(days: int = 14, db: Session = Depends(get_db)):
    try:
        return ads_service.sync_ads(db, days)
    except ConnectorError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.get("/overview")
def overview(days: int = 7, db: Session = Depends(get_db)):
    until = ads_service.local_today()
    since = until - timedelta(days=days - 1)
    total_budget, today_spend = ads_service.budget_state(db)
    return {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "totals": ads_summary(db, since, until),
        "by_ad": ads_by_ad(db, since, until),
        "entities": [to_dict(e) for e in db.scalars(select(AdEntity).order_by(AdEntity.level, AdEntity.name)).all()],
        "total_daily_budget": total_budget,
        "today_spend": today_spend,
        "budget_guard": get_setting(db, "budget_guard"),
    }


@router.post("/analyze")
def analyze(days: int = 7, db: Session = Depends(get_db)):
    return to_dict(analyze_ads(db, days))


@router.get("/creatives")
def list_creatives(db: Session = Depends(get_db)):
    return [to_dict(c) for c in db.scalars(select(AdCreativeDraft).order_by(AdCreativeDraft.id.desc()).limit(100)).all()]


@router.post("/creatives/generate")
def gen_creatives(body: CreativeGenIn, db: Session = Depends(get_db)):
    return [to_dict(c) for c in generate_ad_creatives(db, body.count, body.focus)]


@router.post("/creatives/{cid}/{decision}")
def decide_creative(cid: int, decision: str, db: Session = Depends(get_db)):
    if decision not in ("approve", "reject"):
        raise HTTPException(400, "approve 또는 reject")
    c = get_or_404(db, AdCreativeDraft, cid)
    c.status = "APPROVED" if decision == "approve" else "REJECTED"
    log_event("approval", f"광고 소재 #{cid} {c.status} (실제 광고 등록은 Ads Manager 에서 진행)", db=db)
    db.commit()
    return to_dict(c)


@router.get("/actions")
def list_actions(status: str | None = None, db: Session = Depends(get_db)):
    q = select(PendingAction).order_by(PendingAction.id.desc()).limit(200)
    if status:
        q = q.where(PendingAction.status == status)
    return [to_dict(a) for a in db.scalars(q).all()]


@router.post("/actions")
def request_action(body: AdActionIn, db: Session = Depends(get_db)):
    if body.action_type == "budget_change" and body.new_budget is None:
        raise HTTPException(400, "new_budget 이 필요합니다.")
    a = ads_service.request_action(db, body.action_type, body.target_level, body.target_external_id, body.new_budget, body.reason, "user")
    return to_dict(a)


@router.post("/actions/{aid}/approve")
def approve_action(aid: int, db: Session = Depends(get_db)):
    a = get_or_404(db, PendingAction, aid)
    try:
        return to_dict(ads_service.approve_action(db, a))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/actions/{aid}/reject")
def reject_action(aid: int, body: NoteIn, db: Session = Depends(get_db)):
    a = get_or_404(db, PendingAction, aid)
    try:
        return to_dict(ads_service.reject_action(db, a, body.note))
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/budget-guard")
def get_guard(db: Session = Depends(get_db)):
    return get_setting(db, "budget_guard")


@router.put("/budget-guard")
def put_guard(body: SettingValue, db: Session = Depends(get_db)):
    v = body.value
    if not isinstance(v, dict):
        raise HTTPException(400, "객체 형태여야 합니다.")
    pct = float(v.get("max_budget_change_percent", 10))
    if not 0 < pct <= 50:
        raise HTTPException(400, "max_budget_change_percent 는 0~50 사이여야 합니다.")
    if float(v.get("daily_budget_limit", 0)) < 0:
        raise HTTPException(400, "daily_budget_limit 는 0 이상이어야 합니다.")
    old = get_setting(db, "budget_guard")
    new = set_setting(db, "budget_guard", {**old, **v})
    log_event("budget_change", "Budget Guard 설정 변경", {"old": old, "new": new}, db=db)
    db.commit()
    return new
