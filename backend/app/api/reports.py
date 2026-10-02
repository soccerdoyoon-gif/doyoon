from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_or_404
from app.api.serializers import to_dict
from app.core.database import get_db
from app.models import Report
from app.services.report_service import build_daily_report, build_weekly_report

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("")
def list_reports(report_type: str | None = None, db: Session = Depends(get_db)):
    q = select(Report).order_by(Report.id.desc()).limit(100)
    if report_type:
        q = q.where(Report.report_type == report_type)
    return [to_dict(r, exclude={"data", "content_md"}) for r in db.scalars(q).all()]


@router.get("/{rid}")
def get_report(rid: int, db: Session = Depends(get_db)):
    return to_dict(get_or_404(db, Report, rid))


@router.post("/daily")
def daily(db: Session = Depends(get_db)):
    return to_dict(build_daily_report(db))


@router.post("/weekly")
def weekly(db: Session = Depends(get_db)):
    return to_dict(build_weekly_report(db))
