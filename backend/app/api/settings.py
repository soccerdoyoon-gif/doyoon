from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import SecretsIn, SettingValue
from app.core.config import get_settings
from app.core.database import get_db
from app.core.redact import mask_value
from app.core.secret_store import ALLOWED_SECRET_KEYS, save_secrets
from app.services.app_settings import DEFAULTS, get_all_settings, set_setting
from app.services.events import log_event

router = APIRouter(prefix="/api/settings", tags=["settings"])
EDITABLE = {"platforms_enabled", "auto_approve", "generation", "posting_times", "ads_enabled", "reports"}


@router.get("")
def get_all(db: Session = Depends(get_db)):
    s = get_settings()
    secrets = {k: {"configured": bool(getattr(s, k.lower(), "")), "masked": mask_value(getattr(s, k.lower(), ""))} for k in sorted(ALLOWED_SECRET_KEYS)}
    return {"settings": get_all_settings(db), "secrets": secrets, "dry_run": s.dry_run, "public_base_url": s.public_base_url}


@router.put("/{key}")
def put(key: str, body: SettingValue, db: Session = Depends(get_db)):
    if key not in EDITABLE:
        raise HTTPException(400, f"이 화면에서 바꿀 수 없는 설정입니다: {key}")
    if key in DEFAULTS and isinstance(DEFAULTS[key], dict) and not isinstance(body.value, dict):
        raise HTTPException(400, "객체 형태여야 합니다.")
    value = set_setting(db, key, body.value)
    if key == "generation":
        from app.scheduler.runner import reschedule_generation

        reschedule_generation(int(value.get("hour", 7)), int(value.get("minute", 0)))
    log_event("system", f"설정 변경: {key}", {"value": value}, db=db)
    db.commit()
    return value


@router.post("/secrets")
def put_secrets(body: SecretsIn):
    try:
        saved = save_secrets(body.secrets)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    log_event("system", "API Key/Token 저장", {"keys": saved})
    return {"saved": saved}
