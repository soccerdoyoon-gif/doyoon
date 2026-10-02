"""콘텐츠 상태 관리 (승인 시스템).

AI 생성 → READY_FOR_REVIEW → (사용자 승인) APPROVED → (예약) SCHEDULED → PUBLISHED / FAILED
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.timeutil import to_naive_utc, utcnow
from app.models import BrandProfile, ContentItem
from app.models.enums import ContentStatus as S
from app.services.events import log_event

TRANSITIONS: dict[str, set[str]] = {
    S.DRAFT: {S.READY_FOR_REVIEW, S.REJECTED},
    S.READY_FOR_REVIEW: {S.APPROVED, S.REJECTED, S.DRAFT},
    S.APPROVED: {S.SCHEDULED, S.READY_FOR_REVIEW, S.DRAFT},
    S.SCHEDULED: {S.APPROVED, S.PUBLISHED, S.FAILED},
    S.FAILED: {S.SCHEDULED, S.APPROVED, S.PUBLISHED, S.FAILED},
    S.REJECTED: {S.DRAFT, S.READY_FOR_REVIEW},
    S.PUBLISHED: set(),
}
TEXT_FIELDS = ("title", "idea", "hook", "caption", "script", "structure", "thread", "cta", "hashtags", "media_idea")


class WorkflowError(ValueError):
    pass


def find_forbidden(brand: BrandProfile | None, item: ContentItem) -> list[str]:
    if brand is None or not brand.forbidden_words:
        return []
    blob = " ".join(
        str(getattr(item, f) or "") if not isinstance(getattr(item, f), list) else " ".join(map(str, getattr(item, f)))
        for f in TEXT_FIELDS
    ).lower()
    return [w for w in brand.forbidden_words if w and w.lower() in blob]


def transition(db: Session, item: ContentItem, new_status: str, note: str = "") -> ContentItem:
    old = item.status
    if new_status not in TRANSITIONS.get(old, set()):
        raise WorkflowError(f"상태를 {old} → {new_status} 로 바꿀 수 없습니다.")
    item.status = new_status
    if note:
        item.review_note = note
    log_event("approval", f"콘텐츠 #{item.id} 상태 변경 {old} → {new_status}", {"note": note}, db=db)
    return item


def approve(db: Session, item: ContentItem, schedule_at: datetime | None = None, use_suggested: bool = True) -> ContentItem:
    brand = db.query(BrandProfile).first()
    bad = find_forbidden(brand, item)
    if bad:
        raise WorkflowError(f"금지어가 포함되어 승인할 수 없습니다: {', '.join(bad)}")
    transition(db, item, S.APPROVED)
    when = to_naive_utc(schedule_at) or (item.suggested_time if use_suggested else None)
    if when is not None:
        schedule(db, item, when)
    return item


def schedule(db: Session, item: ContentItem, when: datetime) -> ContentItem:
    when = to_naive_utc(when)
    if item.status not in (S.APPROVED, S.SCHEDULED, S.FAILED):
        raise WorkflowError("승인된 콘텐츠만 예약할 수 있습니다. 먼저 승인하세요.")
    if item.status != S.SCHEDULED:
        transition(db, item, S.SCHEDULED)
    item.scheduled_at = max(when, utcnow()) if when else utcnow()
    item.retry_count = 0
    item.next_retry_at = None
    log_event("approval", f"콘텐츠 #{item.id} 예약: {item.scheduled_at.isoformat()} UTC", db=db)
    return item


def reschedule(db: Session, item: ContentItem, when: datetime) -> ContentItem:
    """캘린더 drag & drop. 게시 완료 콘텐츠는 이동 불가."""
    if item.status == S.PUBLISHED:
        raise WorkflowError("이미 게시된 콘텐츠는 일정을 바꿀 수 없습니다.")
    when = to_naive_utc(when)
    if item.status in (S.SCHEDULED, S.FAILED, S.APPROVED):
        return schedule(db, item, when)
    # 아직 승인 전이면 제안 시간만 변경
    item.suggested_time = when
    return item


def update_fields(db: Session, item: ContentItem, changes: dict) -> ContentItem:
    if item.status == S.PUBLISHED:
        raise WorkflowError("게시 완료된 콘텐츠는 수정할 수 없습니다.")
    text_changed = False
    for k, v in changes.items():
        if v is None or not hasattr(item, k):
            continue
        if k in TEXT_FIELDS and getattr(item, k) != v:
            text_changed = True
        setattr(item, k, v)
    if text_changed and item.status in (S.APPROVED, S.SCHEDULED):
        item.status = S.READY_FOR_REVIEW
        item.scheduled_at = None
        item.review_note = "승인 후 내용이 수정되어 다시 승인이 필요합니다."
        log_event("approval", f"콘텐츠 #{item.id} 수정됨 → 재승인 필요", db=db)
    return item
