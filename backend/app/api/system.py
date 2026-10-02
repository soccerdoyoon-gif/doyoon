from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.connectors.registry import connection_status
from app.core.config import get_settings
from app.core.database import get_db
from app.scheduler.jobs import JOBS
from app.scheduler.runner import job_status
from app.services.app_settings import get_setting
from app.services.events import log_event

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"ok": True}


@router.get("/system/status")
def status(db: Session = Depends(get_db)):
    s = get_settings()
    return {
        "dry_run": s.dry_run,
        "ai_mode": "claude" if s.ai_enabled else "mock",
        "claude_model": s.claude_model,
        "timezone": s.timezone,
        "currency": s.default_currency,
        "default_language": s.default_language,
        "ui_language": get_setting(db, "ui_language"),
        "setup_completed": bool(get_setting(db, "setup_completed")),
        "connectors": connection_status(),
        "scheduler": {"enabled": s.scheduler_enabled, "jobs": job_status()},
    }


@router.post("/system/run-job/{name}")
def run_job(name: str):
    fn = JOBS.get(name)
    if fn is None:
        raise HTTPException(404, f"알 수 없는 작업: {name}")
    log_event("system", f"수동 실행: {name}")
    fn()
    return {"ok": True, "job": name}
