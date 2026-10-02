"""콘텐츠 자동 생성 파이프라인 (일본 시장 기본).

Trend Research → Content Strategist → Copywriter(+Hashtag) → Short-form Script → Creative Director
→ Brand Guardian(문구 검사·수정) → Image / Video Generation → READY_FOR_REVIEW (사용자 승인 대기)

※ Brand Guardian 의 문구 수정이 이미지·영상에 반영되도록, 문구 검사를 렌더링 전에 실행하고
   렌더링 후에 미디어 누락 여부를 한 번 더 확인합니다.
"""
from __future__ import annotations

import threading
import traceback
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import posting_times, rules, team, trend
from app.agents.rules import normalize_hashtags
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.timeutil import local_tz, to_local, utcnow
from app.media.creative import make_image
from app.media.video import VideoError, ffmpeg_available, render_video
from app.models import AdCreativeDraft, BrandProfile, Campaign, ContentIdea, ContentItem, Insight, PipelineRun
from app.models.enums import ContentStatus as S
from app.services import content_service
from app.services.app_settings import get_setting
from app.services.events import log_event

VIDEO_TYPES = {"reel", "short_video"}
SCORE_KEYS = ("hook_strength", "target_audience_fit", "brand_consistency", "cta_quality", "originality", "expected_engagement")


def _clamp(v) -> int:
    try:
        return max(1, min(10, int(v)))
    except (TypeError, ValueError):
        return 5


class Run:
    """진행 상황 기록 (화면에서 단계별 진행 표시)."""

    def __init__(self, db: Session, run: PipelineRun | None):
        self.db, self.run = db, run

    @contextmanager
    def step(self, name: str):
        entry = {"name": name, "status": "running", "started": utcnow().isoformat() + "Z", "note": ""}
        if self.run is not None:
            self.run.steps = [*self.run.steps, entry]
            self.db.commit()
        try:
            yield entry
            entry["status"] = "done"
        except Exception as exc:
            entry["status"] = "error"
            entry["note"] = str(exc)[:300]
            raise
        finally:
            entry["finished"] = utcnow().isoformat() + "Z"
            if self.run is not None:
                self.run.steps = [*self.run.steps[:-1], entry]
                self.db.commit()


def next_slots(db: Session, platform: str, n: int, start_day: date | None = None) -> list[datetime]:
    """JST 게시 슬롯 n 개 (지금부터 30분 이후, 학습된 시간 우선) → UTC naive."""
    tz = local_tz()
    slots = posting_times.slots_for(db, platform)
    earliest = datetime.now(timezone.utc) + timedelta(minutes=30)
    day = start_day or to_local(utcnow()).date()
    out: list[datetime] = []
    used: set[datetime] = set()
    taken = {c.scheduled_at or c.suggested_time for c in db.scalars(
        select(ContentItem).where(ContentItem.platform == platform, ContentItem.status.in_([S.SCHEDULED, S.READY_FOR_REVIEW, S.APPROVED]))
    ).all()}
    for d in range(30):
        for hhmm in sorted(set(slots)):
            hh, mm = map(int, hhmm.split(":"))
            local = datetime.combine(day + timedelta(days=d), time(hh, mm), tzinfo=tz)
            utc = local.astimezone(timezone.utc)
            naive = utc.replace(tzinfo=None)
            if utc < earliest or naive in used or naive in taken:
                continue
            out.append(naive)
            used.add(naive)
            if len(out) >= n:
                return out
    return out


def run_pipeline(
    db: Session,
    *,
    platforms: list[str] | None = None,
    idea_count: int | None = None,
    theme: str = "",
    style: str = "",
    language: str | None = None,
    with_images: bool | None = None,
    with_video: bool | None = None,
    include_ads: bool | None = None,
    start_day: date | None = None,
    campaign_id: int | None = None,
    run: PipelineRun | None = None,
) -> dict:
    s = get_settings()
    brand = db.query(BrandProfile).first()
    if brand is None:
        raise ValueError("먼저 브랜드 프로필을 등록하세요 (설치 마법사 또는 브랜드 메뉴).")
    media_cfg = get_setting(db, "media")
    enabled = get_setting(db, "platforms_enabled")
    platforms = [p for p in (platforms or [p for p, on in enabled.items() if on]) if p in ("instagram", "tiktok", "x", "facebook")] or ["instagram", "tiktok", "x"]
    language = language or brand.language or s.default_language
    with_images = media_cfg.get("generate_images", True) if with_images is None else with_images
    with_video = media_cfg.get("generate_videos", True) if with_video is None else with_video
    include_ads = media_cfg.get("include_ads", True) if include_ads is None else include_ads
    if idea_count is None:  # 매일 자동 생성: 최소 5개 콘텐츠 보장
        per_day = int(get_setting(db, "generation").get("ideas_per_day", 2))
        idea_count = max(per_day, -(-5 // len(platforms)))
    idea_count = max(1, min(10, idea_count))
    R = Run(db, run)
    seed = int(utcnow().timestamp()) % 1000

    with R.step("Trend Research") as st:
        tr = trend.research(db, theme=theme)
        st["note"] = f"{tr.source} / evidence={tr.data.get('evidence')} / 출처 {len(tr.data.get('sources', []))}건"
    analysis = db.scalars(select(Insight).where(Insight.kind == "content").order_by(Insight.id.desc()).limit(1)).first()

    with R.step("Content Strategist") as st:
        ideas, src_ideas = team.strategist(brand, tr.data, analysis.data if analysis else {}, idea_count, platforms, theme, style, language, seed)
        st["note"] = f"아이디어 {len(ideas)}개 ({src_ideas})"
    source = "ai" if src_ideas == "ai" else "mock_ai"

    with R.step("Copywriter / Hashtag") as st:
        packages, _ = team.copywriter(brand, ideas, platforms, tr.data, rules.overused_hashtags(db), language)
        pk = {p.get("idea_index", i): p for i, p in enumerate(packages)}
        st["note"] = f"패키지 {len(packages)}개"

    # --- 아이디어 / 콘텐츠 레코드 생성 ---------------------------------------
    items: dict[str, ContentItem] = {}
    idea_rows: list[ContentIdea] = []
    ads: dict[int, AdCreativeDraft] = {}
    for i, idea in enumerate(ideas):
        row = ContentIdea(title=idea.get("title", "")[:300], concept=idea.get("concept", ""), angle=idea.get("angle", ""),
                          style=idea.get("style") or style, trend_refs=idea.get("trend_refs", []), language=language,
                          pipeline_run_id=run.id if run else None, source=source)
        db.add(row)
        db.flush()
        idea_rows.append(row)
        p = pk.get(i) or {}
        common = dict(idea_id=row.id, style=row.style, language=language, source=source, campaign_id=campaign_id,
                      idea=idea.get("concept", ""), status=S.DRAFT)
        if "instagram" in platforms and p.get("instagram"):
            ig = p["instagram"]
            ctype = ig.get("content_type") or "post"
            items[f"{i}:instagram"] = ContentItem(
                platform="instagram", content_type=ctype, title=f"{row.title}｜IG", hook=ig.get("hook", ""), caption=ig.get("caption", ""),
                cta=ig.get("cta", ""), hashtags=normalize_hashtags(ig.get("hashtags"), "instagram"), thumbnail_text=ig.get("thumbnail_text", ""),
                structure=ig.get("carousel_slides", []) if ctype == "carousel" else [], **common)
        if "tiktok" in platforms and p.get("tiktok"):
            tt = p["tiktok"]
            items[f"{i}:tiktok"] = ContentItem(
                platform="tiktok", content_type="short_video", title=f"{row.title}｜TikTok", hook=tt.get("hook", ""), caption=tt.get("caption", ""),
                cta=tt.get("cta", ""), hashtags=normalize_hashtags(tt.get("hashtags"), "tiktok"), thumbnail_text=tt.get("thumbnail_text", ""),
                video_title=tt.get("youtube_shorts_title", ""), **common)
        if "x" in platforms and p.get("x"):
            x = p["x"]
            thread = [t for t in x.get("thread", []) if t.strip()] if x.get("post_type") == "thread" else []
            items[f"{i}:x"] = ContentItem(
                platform="x", content_type=x.get("post_type") or "tweet", title=f"{row.title}｜X", hook=(thread[0] if thread else x.get("post", ""))[:80],
                caption=thread[0] if thread else x.get("post", ""), thread=thread, hashtags=[], **common)
        if "facebook" in platforms and p.get("facebook"):
            fb = p["facebook"]
            items[f"{i}:facebook"] = ContentItem(platform="facebook", content_type="post", title=f"{row.title}｜FB", caption=fb.get("post", ""),
                                                 hashtags=normalize_hashtags(fb.get("hashtags"), "facebook"), **common)
        if include_ads and p.get("ads") and p["ads"].get("headline"):
            a = p["ads"]
            ads[i] = AdCreativeDraft(hook=a.get("image_text", ""), primary_text=a.get("primary_text", ""), headline=a.get("headline", ""),
                                     description=a.get("description", ""), cta=a.get("cta", ""), target_message=idea.get("target_insight", ""),
                                     rationale=idea.get("concept", ""), based_on=[], language=language, source=source, idea_id=row.id)
    for it in items.values():
        db.add(it)
    for a in ads.values():
        db.add(a)
    db.flush()

    with R.step("Short-form Script") as st:
        targets = [{"item_key": k, "platform": it.platform, "idea": ideas[int(k.split(':')[0])], "hook": it.hook, "cta": it.cta}
                   for k, it in items.items() if it.content_type in VIDEO_TYPES]
        scripts, _ = team.script_writer(brand, targets, language)
        for k, sc in scripts.items():
            if k in items:
                items[k].scenes = [{**x, "scene_id": x.get("scene_id", n + 1)} for n, x in enumerate(sc.get("scenes", []))]
                items[k].script = "\n".join(f"[{x.get('duration')}s] {x.get('voiceover', '')}" for x in sc.get("scenes", []))
                items[k].structure = [f"{x.get('purpose')}: {x.get('visual')}" for x in sc.get("scenes", [])]
                items[k].video_prompt = sc.get("video_prompt", "")
                items[k].music_style = sc.get("music_style", "")
        st["note"] = f"영상 스크립트 {len(scripts)}개"

    with R.step("Creative Director") as st:
        ctargets = []
        for k, it in items.items():
            purposes = {"post": ["feed", "story"], "carousel": ["feed"], "reel": ["thumbnail"], "short_video": ["thumbnail"]}.get(it.content_type, [])
            if it.platform == "instagram" and purposes:
                ctargets.append({"item_key": k, "platform": it.platform, "content_type": it.content_type, "hook": it.hook,
                                 "caption": it.caption[:200], "thumbnail_text": it.thumbnail_text, "purposes": purposes})
        for i, a in ads.items():
            ctargets.append({"item_key": f"{i}:ads", "platform": "meta_ads", "content_type": "ad", "hook": a.headline,
                             "caption": a.primary_text[:200], "thumbnail_text": a.hook, "purposes": ["ad_banner", "story"]})
        briefs, _ = team.creative_director(brand, ctargets, language) if with_images else ({}, "skip")
        st["note"] = f"브리프 {len(briefs)}개"

    with R.step("Brand Guardian") as st:
        forbidden = brand.forbidden_words or []
        review_in = []
        for k, it in items.items():
            review_in.append({"item_key": k, "platform": it.platform, "content_type": it.content_type, "hook": it.hook, "caption": it.caption,
                              "cta": it.cta, "hashtags": it.hashtags, "thread": it.thread, "thumbnail_text": it.thumbnail_text,
                              "subtitles": [x.get("subtitle", "") for x in it.scenes or []], "rule_issues": rules.check(it, forbidden)})
        reviews, _ = team.guardian_review(brand, review_in, language)
        counts = {"pass": 0, "fix": 0, "reject": 0}
        for k, it in items.items():
            rv = reviews.get(k, {})
            verdict = rv.get("verdict", "pass")
            changed = team.apply_corrections(it, rv.get("corrected", {})) if verdict == "fix" else []
            it.hashtags = normalize_hashtags(it.hashtags, it.platform)
            final_rule_issues = rules.check(it, forbidden)
            sc = rv.get("scores") or {}
            if sc:
                it.scores = {key: _clamp(sc.get(key)) for key in SCORE_KEYS}
                it.score_total = round(sum(it.scores.values()) / len(it.scores), 1)
                it.score_note = rv.get("score_note", "")
            errors = [x for x in final_rule_issues if x["severity"] == "error"]
            it.guardian = {"verdict": verdict, "ai_issues": rv.get("issues", []), "rule_issues": final_rule_issues, "corrected_fields": changed}
            if verdict == "reject" or errors:
                it.status = S.DRAFT
                reasons = [x["message"] for x in (rv.get("issues", []) if verdict == "reject" else errors)][:3]
                it.review_note = "Brand Guardian: 승인 단계로 보내지 않음 — " + " / ".join(reasons)
            else:
                it.status = S.READY_FOR_REVIEW
            counts[verdict if verdict in counts else "pass"] += 1
        st["note"] = f"통과 {counts['pass']} · 수정 {counts['fix']} · 반려 {counts['reject']}"

    # --- 이미지 / 영상 생성 ---------------------------------------------------
    voice_cfg = get_setting(db, "voice")
    with R.step("Image / Video Generation") as st:
        n_img = n_vid = 0
        notes: list[str] = []
        for k, it in items.items():
            if it.status == S.DRAFT and it.review_note.startswith("Brand Guardian"):
                continue
            b = briefs.get(k, {})
            imgs = {x["purpose"]: x for x in b.get("images", [])}
            try:
                if with_images and it.platform == "instagram" and it.content_type == "post":
                    for n, purpose in enumerate(["feed", "story"]):
                        br = imgs.get(purpose, {})
                        make_image(db, purpose, br.get("overlay_text") or it.thumbnail_text or it.hook, sub_text=br.get("sub_text", ""),
                                   visual_prompt=br.get("visual_prompt", ""), brand_name=brand.brand_name, style=it.style,
                                   seed=it.idea_id or it.id, content_id=it.id, idea_id=it.idea_id, order=n)
                        n_img += 1
                elif with_images and it.content_type == "carousel":
                    slides = [x for x in (it.structure or []) if x.strip()][:10] or [it.hook]
                    vp = imgs.get("feed", {}).get("visual_prompt", "")
                    for n, text in enumerate(slides):
                        make_image(db, "carousel", text, visual_prompt=vp if n == 0 else "", brand_name=brand.brand_name, style=it.style,
                                   seed=it.idea_id or it.id, content_id=it.id, idea_id=it.idea_id, order=n, page_label=f"{n + 1}/{len(slides)}")
                        n_img += 1
                elif it.content_type in VIDEO_TYPES and with_video and it.scenes and s.video_provider == "slideshow":
                    render_video(db, it, brand_name=brand.brand_name, voice_cfg=voice_cfg, ai_scene_images=media_cfg.get("ai_scene_images", False))
                    n_vid += 1
            except (VideoError, OSError) as exc:
                notes.append(f"#{it.id}: {exc}")
                it.review_note = (it.review_note + " / " if it.review_note else "") + f"미디어 생성 실패: {str(exc)[:150]}"
        for i, a in ads.items():
            b = briefs.get(f"{i}:ads", {})
            imgs = {x["purpose"]: x for x in b.get("images", [])}
            if with_images:
                for n, purpose in enumerate(["ad_banner", "story"]):
                    br = imgs.get(purpose, {})
                    asset = make_image(db, purpose, br.get("overlay_text") or a.hook or a.headline, sub_text=br.get("sub_text", ""),
                                       visual_prompt=br.get("visual_prompt", ""), brand_name=brand.brand_name, style=idea_rows[i].style,
                                       seed=idea_rows[i].id, ad_id=a.id, idea_id=a.idea_id, order=n)
                    if purpose == "ad_banner":
                        a.image_asset_id = asset.id
                    a.image_idea = br.get("visual_prompt", "") or a.image_idea
                    n_img += 1
            tt = items.get(f"{i}:tiktok") or items.get(f"{i}:instagram")
            if tt is not None:
                vids = [x for x in tt.assets if x.kind == "video"]
                a.video_asset_id = vids[0].id if vids else None
                a.video_idea = tt.script or tt.video_prompt
        if with_video and not ffmpeg_available():
            notes.append("ffmpeg 미설치 → 영상 파일 대신 장면 정보/프롬프트만 저장")
        st["note"] = f"이미지 {n_img}장 · 영상 {n_vid}개" + (f" · {'; '.join(notes)[:200]}" if notes else "")
        # 미디어가 필요한데 없는 경우 경고
        for it in items.values():
            needs = it.platform == "tiktok" or it.content_type in ("reel", "carousel", "post") and it.platform == "instagram"
            has = any(x.kind in ("image", "video") for x in it.assets) or it.media_url or it.media_path
            if needs and not has and it.status == S.READY_FOR_REVIEW:
                it.guardian = {**it.guardian, "media_missing": True}
                it.review_note = (it.review_note + " / " if it.review_note else "") + "게시용 미디어가 없습니다 — 업로드하거나 다시 생성하세요."

    # --- 제안 시간 / 자동 승인 --------------------------------------------------
    auto = get_setting(db, "auto_approve")
    by_platform: dict[str, list[ContentItem]] = {}
    for it in items.values():
        by_platform.setdefault(it.platform, []).append(it)
    for platform, lst in by_platform.items():
        for it, when in zip(lst, next_slots(db, platform, len(lst), start_day)):
            it.suggested_time = when
    for it in items.values():
        if auto.get(it.platform) and it.status == S.READY_FOR_REVIEW and not it.guardian.get("media_missing"):
            content_service.approve(db, it)
            log_event("approval", f"콘텐츠 #{it.id} 자동 승인 ({it.platform} 자동승인 설정)", db=db)

    result = {
        "source": source,
        "language": language,
        "platforms": platforms,
        "idea_ids": [r.id for r in idea_rows],
        "created_ids": [it.id for it in items.values()],
        "ad_creative_ids": [a.id for a in ads.values()],
        "ready_for_review": [it.id for it in items.values() if it.status == S.READY_FOR_REVIEW],
        "held_as_draft": [it.id for it in items.values() if it.status == S.DRAFT],
    }
    log_event("ai_generation", f"콘텐츠 패키지 생성: 아이디어 {len(idea_rows)} · 콘텐츠 {len(items)} · 광고안 {len(ads)} ({source})", result, db=db)
    db.commit()
    return result


def _thread_main(run_id: int, params: dict) -> None:
    db = SessionLocal()
    try:
        run = db.get(PipelineRun, run_id)
        try:
            run.result = run_pipeline(db, run=run, **params)
            run.status = "DONE"
        except Exception as exc:  # 실패해도 서버는 계속 동작
            db.rollback()
            run = db.get(PipelineRun, run_id)
            run.status = "ERROR"
            run.error = f"{type(exc).__name__}: {exc}"[:1000]
            log_event("system", f"파이프라인 실패 #{run_id}: {exc}", {"trace": traceback.format_exc()[-1500:]}, level="ERROR")
        run.finished_at = utcnow()
        db.commit()
    finally:
        db.close()


def start_run(db: Session, params: dict, background: bool = True) -> PipelineRun:
    clean = {k: (v.isoformat() if isinstance(v, date) else v) for k, v in params.items()}
    run = PipelineRun(request=clean, status="RUNNING", steps=[])
    db.add(run)
    db.commit()
    if background and get_settings().pipeline_background:
        threading.Thread(target=_thread_main, args=(run.id, params), daemon=True, name=f"pipeline-{run.id}").start()
    else:
        _thread_main(run.id, params)
        db.refresh(run)
    return run


def campaign_exists(db: Session, cid: int | None) -> bool:
    return cid is None or db.get(Campaign, cid) is not None
