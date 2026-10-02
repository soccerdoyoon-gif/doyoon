from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.ai.content_generator import generate_content
from app.api.deps import get_or_404
from app.api.schemas import ApproveIn, BulkIds, ContentIn, ContentUpdate, GenerateIn, NoteIn, ScheduleIn
from app.api.serializers import content_dict
from app.core.config import get_settings
from app.core.database import get_db
from app.core.timeutil import to_naive_utc, utcnow
from app.models import BrandProfile, ContentItem
from app.models.enums import ContentStatus as S
from app.services import content_service as cs
from app.services.events import log_event
from app.services.publisher import publish_item

router = APIRouter(prefix="/api/content", tags=["content"])
ALLOWED_MEDIA = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".m4v"}
MAX_MEDIA_BYTES = 300 * 1024 * 1024


def _wf(fn):
    try:
        return fn()
    except cs.WorkflowError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("")
def list_content(
    status: str | None = None,
    platform: str | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    order: str = "score",
    limit: int = 200,
    db: Session = Depends(get_db),
):
    q = select(ContentItem)
    if status:
        q = q.where(ContentItem.status.in_(status.split(",")))
    if platform:
        q = q.where(ContentItem.platform == platform)
    if start:
        q = q.where(ContentItem.created_at >= to_naive_utc(start))
    if end:
        q = q.where(ContentItem.created_at <= to_naive_utc(end))
    if order == "score":
        q = q.order_by(ContentItem.score_total.desc().nulls_last(), ContentItem.id.desc())
    else:
        q = q.order_by(ContentItem.id.desc())
    return [content_dict(c) for c in db.scalars(q.limit(min(limit, 500))).all()]


@router.get("/{cid}")
def get_content(cid: int, db: Session = Depends(get_db)):
    return content_dict(get_or_404(db, ContentItem, cid), with_children=True)


@router.post("")
def create_content(body: ContentIn, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["suggested_time"] = to_naive_utc(data["suggested_time"])
    item = ContentItem(**data, status=S.DRAFT, source="manual")
    db.add(item)
    db.commit()
    return content_dict(item)


@router.post("/generate")
def generate(body: GenerateIn, db: Session = Depends(get_db)):
    try:
        return generate_content(db, count=body.count, platforms=body.platforms, theme=body.theme, campaign_id=body.campaign_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/{cid}")
def update_content(cid: int, body: ContentUpdate, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    _wf(lambda: cs.update_fields(db, item, body.model_dump(exclude_unset=True)))
    db.commit()
    return content_dict(item)


@router.delete("/{cid}")
def delete_content(cid: int, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    if item.status == S.PUBLISHED:
        raise HTTPException(400, "게시 완료된 콘텐츠 기록은 삭제할 수 없습니다 (성과 기록 보존).")
    log_event("approval", f"콘텐츠 #{cid} 삭제", {"title": item.title}, db=db)
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/{cid}/submit")
def submit(cid: int, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    def run():
        bad = cs.find_forbidden(db.query(BrandProfile).first(), item)
        if bad:
            raise cs.WorkflowError(f"금지어가 포함되어 있습니다: {', '.join(bad)}")
        cs.transition(db, item, S.READY_FOR_REVIEW)
    _wf(run)
    db.commit()
    return content_dict(item)


@router.post("/{cid}/approve")
def approve(cid: int, body: ApproveIn, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    _wf(lambda: cs.approve(db, item, body.schedule_at, body.use_suggested_time))
    db.commit()
    return content_dict(item)


@router.post("/bulk-approve")
def bulk_approve(body: BulkIds, db: Session = Depends(get_db)):
    ok, errors = [], {}
    for cid in body.ids:
        item = db.get(ContentItem, cid)
        if item is None:
            errors[cid] = "not found"
            continue
        try:
            cs.approve(db, item, None, body.use_suggested_time)
            ok.append(cid)
        except cs.WorkflowError as exc:
            errors[cid] = str(exc)
    db.commit()
    return {"approved": ok, "errors": errors}


@router.post("/{cid}/reject")
def reject(cid: int, body: NoteIn, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    _wf(lambda: cs.transition(db, item, S.REJECTED, body.note))
    db.commit()
    return content_dict(item)


@router.post("/{cid}/schedule")
def schedule(cid: int, body: ScheduleIn, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    _wf(lambda: cs.schedule(db, item, body.scheduled_at))
    db.commit()
    return content_dict(item)


@router.post("/{cid}/unschedule")
def unschedule(cid: int, db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    def run():
        cs.transition(db, item, S.APPROVED)
        item.scheduled_at = None
    _wf(run)
    db.commit()
    return content_dict(item)


@router.post("/{cid}/publish-now")
def publish_now(cid: int, db: Session = Depends(get_db)):
    """승인된 콘텐츠를 지금 게시 (DRY_RUN=true 면 시뮬레이션)."""
    item = get_or_404(db, ContentItem, cid)
    if item.status not in (S.APPROVED, S.SCHEDULED, S.FAILED):
        raise HTTPException(400, "승인된 콘텐츠만 게시할 수 있습니다.")
    if item.status != S.SCHEDULED:
        _wf(lambda: cs.schedule(db, item, utcnow()))
    item.retry_count = 0
    db.commit()
    publish_item(db, item)
    return content_dict(item, with_children=True)


@router.post("/{cid}/media")
async def upload_media(cid: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    item = get_or_404(db, ContentItem, cid)
    if item.status == S.PUBLISHED:
        raise HTTPException(400, "게시 완료된 콘텐츠입니다.")
    ext = "." + (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ALLOWED_MEDIA:
        raise HTTPException(400, f"지원 형식: {', '.join(sorted(ALLOWED_MEDIA))}")
    folder = get_settings().data_dir / "media"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{ext}"
    size = 0
    with open(folder / name, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_MEDIA_BYTES:
                out.close()
                (folder / name).unlink(missing_ok=True)
                raise HTTPException(400, "파일이 너무 큽니다 (최대 300MB).")
            out.write(chunk)
    item.media_path = name
    db.commit()
    return content_dict(item)


@router.get("/search/text")
def search(q: str, db: Session = Depends(get_db)):
    like = f"%{q}%"
    rows = db.scalars(select(ContentItem).where(or_(ContentItem.title.ilike(like), ContentItem.caption.ilike(like))).limit(50)).all()
    return [content_dict(c) for c in rows]
