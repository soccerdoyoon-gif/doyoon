"""매일 콘텐츠 후보 생성 + 내부 점수 평가.

입력: 브랜드 프로필, 과거 게시물/성과, 최신 AI 분석, 전략, 경쟁사 분석, 진행 중 캠페인
출력: ContentItem (READY_FOR_REVIEW, 자동승인 플랫폼은 SCHEDULED)
점수는 '우선순위 정렬용 내부 지표' 이며 실제 성과를 보장하지 않습니다.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import mock_ai
from app.ai.client import AIError, get_ai
from app.ai.prompts import COMMON_RULES, as_json, brand_context, language_guide
from app.ai.schemas import CONTENT_CANDIDATES, CONTENT_SCORES
from app.analytics.stats import content_performance, rank_content
from app.core.timeutil import local_tz, to_local, utcnow
from app.models import BrandProfile, Campaign, ContentItem, Insight
from app.models.enums import ContentStatus as S
from app.services import content_service
from app.services.app_settings import get_setting
from app.services.events import log_event

PLATFORM_TYPES = {
    "instagram": ["post", "reel", "carousel"],
    "facebook": ["post"],
    "tiktok": ["short_video"],
    "x": ["tweet", "info_tweet", "thread", "ad_tweet"],
}
TYPE_GUIDE = {
    "post": "Instagram/Facebook 피드 게시물: idea, hook(첫 줄), caption, cta, hashtags(5-15개), media_idea(이미지 연출)",
    "carousel": "Instagram 캐러셀: structure 에 슬라이드별 문구, caption, cta, hashtags",
    "reel": "Instagram Reel: hook(첫 3초), structure(장면 순서), script(대사/자막), caption, cta, hashtags",
    "short_video": "TikTok 숏폼: hook(첫 3초), structure(영상 구성), script(대사/스크립트), caption, cta, hashtags(3-6개)",
    "tweet": "X 일반 게시물: caption 은 280자 이내",
    "info_tweet": "X 정보성 게시물: caption 280자 이내, 유용한 정보 중심",
    "ad_tweet": "X 짧은 광고성 게시물: caption 280자 이내, 명확한 CTA",
    "thread": "X Thread: thread 배열에 각 트윗(각 280자 이내, 3-7개), caption 은 첫 트윗과 동일",
}
SCORE_KEYS = ("hook_strength", "target_audience_fit", "brand_consistency", "cta_quality", "originality", "expected_engagement")
HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def plan_slots(platforms: list[str], count: int) -> list[dict]:
    platforms = [p for p in platforms if p in PLATFORM_TYPES] or ["instagram"]
    count = max(5, count)
    used = {p: 0 for p in platforms}
    slots = []
    for i in range(count):
        p = platforms[i % len(platforms)]
        types = PLATFORM_TYPES[p]
        slots.append({"slot": i, "platform": p, "content_type": types[used[p] % len(types)]})
        used[p] += 1
    return slots


def _latest_insight(db: Session, kind: str) -> Insight | None:
    return db.scalars(select(Insight).where(Insight.kind == kind).order_by(Insight.id.desc()).limit(1)).first()


def build_context(db: Session) -> dict:
    since = utcnow() - timedelta(days=30)
    rows = content_performance(db, since)
    best, worst = rank_content(rows, 5)
    recent_titles = [
        t for (t,) in db.execute(
            select(ContentItem.title).where(ContentItem.created_at >= utcnow() - timedelta(days=14)).order_by(ContentItem.id.desc()).limit(40)
        )
    ]
    ctx = {
        "past_best_content": best,
        "past_low_content": worst,
        "recent_titles_to_avoid_repeating": recent_titles,
        "active_campaigns": [
            {"id": c.id, "name": c.name, "objective": c.objective, "notes": c.notes}
            for c in db.scalars(select(Campaign).where(Campaign.is_active.is_(True))).all()
        ],
    }
    for kind in ("content", "strategy", "competitor", "ads"):
        ins = _latest_insight(db, kind)
        if ins:
            ctx[f"latest_{kind}_insight"] = {"created_at": ins.created_at, "source": ins.source, **ins.data}
    return ctx


def _suggested_time(target_day: date, platform: str, candidate_time: str, idx: int, posting_times: dict) -> datetime:
    m = HHMM.match(candidate_time or "")
    if m:
        hh, mm = int(m.group(1)), int(m.group(2))
    else:
        options = posting_times.get(platform) or ["12:00"]
        hh, mm = map(int, options[idx % len(options)].split(":"))
    local = datetime.combine(target_day, time(hh, mm), tzinfo=local_tz())
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _clamp(v) -> int:
    try:
        return max(1, min(10, int(v)))
    except (TypeError, ValueError):
        return 5


def generate_content(
    db: Session,
    count: int | None = None,
    platforms: list[str] | None = None,
    theme: str = "",
    target_day: date | None = None,
    campaign_id: int | None = None,
) -> dict:
    brand = db.query(BrandProfile).first()
    if brand is None:
        raise ValueError("먼저 브랜드 프로필을 등록하세요 (설치 마법사 또는 Brand Profile 메뉴).")
    gen_cfg = get_setting(db, "generation")
    enabled = get_setting(db, "platforms_enabled")
    platforms = platforms or [p for p, on in enabled.items() if on]
    count = max(5, count or gen_cfg.get("daily_count", 6))
    slots = plan_slots(platforms, count)
    target_day = target_day or (to_local(utcnow()).date() + timedelta(days=1))
    lang = brand.language or "ko"
    ai = get_ai()
    batch_id = uuid.uuid4().hex[:12]
    source = "ai" if ai.is_available() else "mock_ai"

    if ai.is_available():
        ctx = build_context(db)
        system = (
            "당신은 SNS 마케팅 콘텐츠 기획자이자 카피라이터입니다. 브랜드 프로필과 과거 성과 데이터를 바탕으로 "
            "각 플랫폼 문화에 맞는 콘텐츠를 만듭니다.\n" + COMMON_RULES + "\n" + language_guide(lang)
        )
        prompt = (
            f"{brand_context(brand)}\n\n<context>\n{as_json(ctx)}\n</context>\n\n"
            f"게시 예정일: {target_day.isoformat()} ({brand.country})\n"
            + (f"이번 주제/요청: {theme}\n" if theme else "")
            + "아래 슬롯마다 정확히 1개씩 콘텐츠 후보를 만드세요. slot 번호와 platform, content_type 을 그대로 유지하세요.\n"
            + as_json(slots)
            + "\n\n형식 가이드:\n"
            + "\n".join(f"- {k}: {v}" for k, v in TYPE_GUIDE.items())
            + "\n해당 형식에 쓰지 않는 필드는 빈 문자열/빈 배열로 두세요. suggested_time_local 은 'HH:MM' (최신 분석의 좋은 게시 시간 참고, 모르면 빈 문자열)."
            + "\n과거 성과 좋은 패턴은 반영하되 문구를 복사하지 말고, 최근 제목과 겹치지 않게 다양하게 만드세요."
        )
        try:
            data = ai.generate_json("content_generation", system, prompt, CONTENT_CANDIDATES, max_tokens=32000)
            candidates = data.get("candidates", [])
        except AIError as exc:
            log_event("api_error", f"AI 콘텐츠 생성 실패 → Mock 으로 대체: {exc}", level="WARNING", db=db)
            candidates, source = mock_ai.content_candidates(brand, slots, lang), "mock_ai"
    else:
        candidates = mock_ai.content_candidates(brand, slots, lang)

    # --- scoring ---------------------------------------------------------
    score_rows: list[dict] = []
    if source == "ai":
        try:
            sdata = ai.generate_json(
                "content_scoring",
                "당신은 엄격한 SNS 콘텐츠 리뷰어입니다. 각 후보를 1-10 정수로 평가하세요. "
                "이 점수는 내부 우선순위용이며 실제 성과 예측이 아닙니다. 후하게 주지 마세요.",
                f"{brand_context(brand)}\n\n<candidates>\n{as_json([{'index': i, **c} for i, c in enumerate(candidates)])}\n</candidates>\n"
                "항목: hook_strength, target_audience_fit, brand_consistency, cta_quality, originality, expected_engagement. note 는 한 줄 개선 팁.",
                CONTENT_SCORES,
            )
            score_rows = sdata.get("scores", [])
        except AIError as exc:
            log_event("api_error", f"AI 점수 평가 실패 → 규칙 기반 점수: {exc}", level="WARNING", db=db)
    if not score_rows:
        score_rows = mock_ai.scores(candidates)
    score_by_idx = {s.get("index"): s for s in score_rows}

    auto = get_setting(db, "auto_approve")
    posting_times = get_setting(db, "posting_times")
    created = []
    for i, c in enumerate(candidates):
        platform = c.get("platform") if c.get("platform") in PLATFORM_TYPES else slots[min(i, len(slots) - 1)]["platform"]
        sc = score_by_idx.get(i, {})
        scores = {k: _clamp(sc.get(k)) for k in SCORE_KEYS}
        item = ContentItem(
            platform=platform,
            content_type=c.get("content_type", "post"),
            title=(c.get("title") or "")[:300],
            idea=c.get("idea", ""),
            hook=c.get("hook", ""),
            caption=c.get("caption", ""),
            script=c.get("script", ""),
            structure=c.get("structure") or [],
            thread=c.get("thread") or [],
            cta=c.get("cta", ""),
            hashtags=c.get("hashtags") or [],
            media_idea=c.get("media_idea", ""),
            language=lang,
            campaign_id=campaign_id,
            scores=scores,
            score_total=round(sum(scores.values()) / len(scores), 1),
            score_note=sc.get("note", ""),
            suggested_time=_suggested_time(target_day, platform, c.get("suggested_time_local", ""), i, posting_times),
            status=S.READY_FOR_REVIEW,
            source=source,
            batch_id=batch_id,
        )
        db.add(item)
        db.flush()
        bad = content_service.find_forbidden(brand, item)
        if bad:
            item.status = S.DRAFT
            item.review_note = f"금지어 포함으로 DRAFT 처리: {', '.join(bad)} — 수정 후 검토 요청하세요."
        elif auto.get(platform):
            content_service.approve(db, item)
            log_event("approval", f"콘텐츠 #{item.id} 자동 승인 ({platform} 자동승인 설정)", db=db)
        created.append(item.id)

    log_event(
        "ai_generation",
        f"콘텐츠 후보 {len(created)}개 생성 ({source})",
        {"batch_id": batch_id, "platforms": platforms, "target_day": target_day.isoformat()},
        db=db,
    )
    db.commit()
    return {"batch_id": batch_id, "created_ids": created, "source": source, "target_day": target_day.isoformat()}
