"""설치 마법사 API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import SetupIn
from app.api.serializers import to_dict
from app.core.config import get_settings
from app.core.database import get_db
from app.core.secret_store import save_secrets
from app.models import BrandProfile, Competitor
from app.services.app_settings import get_setting, set_setting
from app.services.events import log_event

router = APIRouter(prefix="/api/setup", tags=["setup"])


@router.get("")
def get_setup(db: Session = Depends(get_db)):
    brand = db.query(BrandProfile).first()
    return {
        "setup_completed": bool(get_setting(db, "setup_completed")),
        "brand": to_dict(brand) if brand else None,
        "dry_run": get_settings().dry_run,
    }


@router.post("")
def complete_setup(body: SetupIn, db: Session = Depends(get_db)):
    try:
        saved = save_secrets(body.secrets) if body.secrets else []
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    brand = db.query(BrandProfile).first()
    if brand is None:
        brand = BrandProfile(**body.brand.model_dump())
        db.add(brand)
    else:
        for k, v in body.brand.model_dump().items():
            setattr(brand, k, v)
    existing = {c.name for c in db.query(Competitor).all()}
    for name in body.brand.competitors:
        if name and name not in existing:
            db.add(Competitor(name=name))
    if body.platforms_enabled:
        set_setting(db, "platforms_enabled", {**get_setting(db, "platforms_enabled"), **body.platforms_enabled})
    set_setting(db, "ads_enabled", body.ads_enabled)
    guard = get_setting(db, "budget_guard")
    guard.update({"daily_budget_limit": body.daily_budget_limit, "currency": body.currency.upper()})
    set_setting(db, "budget_guard", guard)
    set_setting(db, "setup_completed", True)
    log_event("system", "설치 마법사 완료", {"secrets_saved": saved, "ads_enabled": body.ads_enabled}, db=db)
    db.commit()
    return {"ok": True, "secrets_saved": saved}
