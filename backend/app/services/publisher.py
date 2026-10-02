"""예약 게시 실행기.

- SCHEDULED 이고 예약 시간이 지난 콘텐츠를 게시합니다.
- 실패 시 FAILED + 실패 이유 기록, exponential backoff (1분 → 5분 → 15분) 로 재시도.
- 재시도 횟수를 다 쓰면 더 이상 재시도하지 않습니다 (무한 반복 금지).
- DRY_RUN=true 이면 connector 가 실제 API 를 호출하지 않습니다.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.connectors.base import ConnectorError, PublishRequest
from app.connectors.registry import get_connector
from app.core.config import get_settings
from app.core.redact import redact
from app.core.timeutil import utcnow
from app.models import ContentItem, PostAttempt
from app.models.enums import ContentStatus as S
from app.services.events import log_event


def media_url_for(item: ContentItem) -> str:
    if item.media_url:
        return item.media_url
    base = get_settings().public_media_base_url.rstrip("/")
    if item.media_path and base:
        return f"{base}/media/{item.media_path.split('/')[-1]}"
    return ""


def build_request(item: ContentItem) -> PublishRequest:
    media_path = ""
    if item.media_path:
        media_path = str(get_settings().data_dir / "media" / item.media_path.split("/")[-1])
    return PublishRequest(
        content_id=item.id,
        platform=item.platform,
        content_type=item.content_type,
        title=item.title,
        caption=item.caption,
        hashtags=list(item.hashtags or []),
        thread=list(item.thread or []),
        media_url=media_url_for(item),
        media_path=media_path,
    )


def due_items(db: Session, now=None) -> list[ContentItem]:
    now = now or utcnow()
    max_retries = len(get_settings().retry_delays_minutes)
    q = select(ContentItem).where(
        or_(
            and_(ContentItem.status == S.SCHEDULED, ContentItem.scheduled_at <= now),
            and_(
                ContentItem.status == S.FAILED,
                ContentItem.next_retry_at.is_not(None),
                ContentItem.next_retry_at <= now,
                ContentItem.retry_count <= max_retries,
            ),
        )
    )
    return list(db.scalars(q.order_by(ContentItem.scheduled_at)).all())


def publish_item(db: Session, item: ContentItem, now=None) -> ContentItem:
    now = now or utcnow()
    settings = get_settings()
    delays = settings.retry_delays_minutes
    connector = get_connector(item.platform)
    req = build_request(item)
    try:
        result = connector.publish(req)
    except Exception as exc:  # ConnectorError 또는 예상치 못한 오류
        retryable = exc.retryable if isinstance(exc, ConnectorError) else True
        response = exc.response if isinstance(exc, ConnectorError) else None
        message = str(exc) or type(exc).__name__
        item.retry_count += 1
        item.status = S.FAILED
        item.last_error = message
        if retryable and item.retry_count <= len(delays):
            item.next_retry_at = now + timedelta(minutes=delays[item.retry_count - 1])
            note = f"{delays[item.retry_count - 1]}분 후 재시도 ({item.retry_count}/{len(delays)})"
        else:
            item.next_retry_at = None
            note = "재시도 없음 (최종 실패)" if retryable else "재시도해도 해결되지 않는 오류 — 내용을 수정하세요"
        db.add(PostAttempt(content_id=item.id, success=False, dry_run=settings.dry_run, error=message, response=redact(response or {})))
        log_event("post_attempt", f"게시 실패 #{item.id} {item.platform}: {message} — {note}", {"retryable": retryable}, level="WARNING", db=db)
        if response:
            log_event("api_error", f"{item.platform} API 오류 응답 (#{item.id})", {"response": response}, level="WARNING", db=db)
        db.commit()
        return item

    item.status = S.PUBLISHED
    item.published_at = now
    item.external_id = result.external_id
    item.external_url = result.url
    item.is_dry_run = bool(result.dry_run or result.simulated)
    item.last_error = ""
    item.next_retry_at = None
    db.add(PostAttempt(content_id=item.id, success=True, dry_run=item.is_dry_run, response=result.to_dict()))
    if item.is_dry_run:
        log_event("dry_run", result.message or f"[DRY RUN] {item.platform} 게시 시뮬레이션 #{item.id}", db=db)
    log_event(
        "post_attempt",
        f"게시 성공 #{item.id} {item.platform} ({'시뮬레이션' if item.is_dry_run else '실제 게시'})",
        {"external_id": result.external_id, "url": result.url},
        db=db,
    )
    db.commit()
    return item


def publish_due(db: Session, now=None) -> list[int]:
    done = []
    for item in due_items(db, now):
        publish_item(db, item, now)
        done.append(item.id)
    return done
