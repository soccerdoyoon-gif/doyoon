"""에이전트 파이프라인 / 트렌드 / 게시 시간 / 아이디어 패키지 / 미디어 API."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents import pipeline, posting_times, trend
from app.agents.schemas import STYLES
from app.api.deps import get_or_404
from app.api.serializers import asset_dict, content_dict, to_dict
from app.core.database import get_db
from app.media.tts import get_tts
from app.models import AdCreativeDraft, BrandProfile, ContentIdea, ContentItem, GeneratedAsset, Insight, PipelineRun
from app.services.app_settings import get_setting

router = APIRouter(prefix="/api", tags=["pipeline"])


class PipelineIn(BaseModel):
    platforms: list[str] | None = None
    idea_count: int | None = Field(default=None, ge=1, le=10)
    theme: str = ""
    style: str = ""
    language: str | None = Field(default=None, pattern="^(ja|ko|en)$")  # 기본 일본어. ko/en 은 요청 시에만
    with_images: bool | None = None
    with_video: bool | None = None
    include_ads: bool | None = None
    campaign_id: int | None = None


def _params(body: PipelineIn) -> dict:
    return {k: v for k, v in body.model_dump().items() if v not in (None, "")}


@router.post("/pipeline/run")
def run(body: PipelineIn, db: Session = Depends(get_db)):
    if db.query(BrandProfile).first() is None:
        raise HTTPException(400, "먼저 브랜드 프로필을 등록하세요.")
    if body.style and body.style not in STYLES:
        raise HTTPException(400, f"style 은 다음 중 하나: {', '.join(STYLES)}")
    r = pipeline.start_run(db, _params(body), background=True)
    return to_dict(r)


@router.get("/pipeline/runs")
def runs(db: Session = Depends(get_db)):
    return [to_dict(r) for r in db.scalars(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(30)).all()]


@router.get("/pipeline/runs/{rid}")
def run_status(rid: int, db: Session = Depends(get_db)):
    return to_dict(get_or_404(db, PipelineRun, rid))


@router.get("/pipeline/styles")
def styles():
    return STYLES


@router.get("/ideas")
def ideas(limit: int = 30, db: Session = Depends(get_db)):
    rows = db.scalars(select(ContentIdea).order_by(ContentIdea.id.desc()).limit(min(limit, 100))).all()
    return [to_dict(i) for i in rows]


@router.get("/ideas/{iid}")
def idea_package(iid: int, db: Session = Depends(get_db)):
    """아이디어 1개의 콘텐츠 패키지 (플랫폼별 콘텐츠 + 광고안 + 생성 파일)."""
    idea = get_or_404(db, ContentIdea, iid)
    items = db.scalars(select(ContentItem).where(ContentItem.idea_id == iid)).all()
    ads = db.scalars(select(AdCreativeDraft).where(AdCreativeDraft.idea_id == iid)).all()
    ad_assets = db.scalars(select(GeneratedAsset).where(GeneratedAsset.ad_creative_id.in_([a.id for a in ads] or [-1]))).all()
    return {
        "idea": to_dict(idea),
        "contents": [content_dict(c) for c in items],
        "ads": [{**to_dict(a), "assets": [asset_dict(x) for x in ad_assets if x.ad_creative_id == a.id]} for a in ads],
    }


@router.get("/trends")
def latest_trend(db: Session = Depends(get_db)):
    t = trend.latest(db)
    return to_dict(t) if t else None


@router.post("/trends/research")
def research(theme: str = "", db: Session = Depends(get_db)):
    return to_dict(trend.research(db, theme=theme, force=True))


@router.get("/posting-times")
def get_posting_times(db: Session = Depends(get_db)):
    ins = db.scalars(select(Insight).where(Insight.kind == "posting_times").order_by(Insight.id.desc()).limit(1)).first()
    return {"learned": to_dict(ins) if ins else None, "candidates": get_setting(db, "posting_times")}


@router.post("/posting-times/learn")
def learn_posting_times(db: Session = Depends(get_db)):
    return to_dict(posting_times.learn(db))


@router.post("/content/{cid}/regenerate-media")
def regenerate_media(cid: int, db: Session = Depends(get_db)):
    """콘텐츠의 이미지/영상을 현재 문구로 다시 생성 (기존 파일 기록은 교체)."""
    from app.media.creative import make_image
    from app.media.video import VideoError, render_video

    item = get_or_404(db, ContentItem, cid)
    if item.status == "PUBLISHED":
        raise HTTPException(400, "게시 완료된 콘텐츠입니다.")
    brand = db.query(BrandProfile).first()
    name = brand.brand_name if brand else ""
    for a in list(item.assets):
        db.delete(a)
    db.flush()
    try:
        if item.content_type in ("reel", "short_video"):
            render_video(db, item, brand_name=name, voice_cfg=get_setting(db, "voice"))
        elif item.content_type == "carousel":
            slides = [x for x in item.structure or [] if x.strip()][:10] or [item.hook]
            for n, text in enumerate(slides):
                make_image(db, "carousel", text, brand_name=name, style=item.style, seed=item.idea_id or item.id,
                           content_id=item.id, idea_id=item.idea_id, order=n, page_label=f"{n + 1}/{len(slides)}")
        elif item.platform in ("instagram", "facebook"):
            for n, purpose in enumerate(["feed", "story"]):
                make_image(db, purpose, item.thumbnail_text or item.hook, brand_name=name, style=item.style,
                           seed=item.idea_id or item.id, content_id=item.id, idea_id=item.idea_id, order=n)
        else:
            raise HTTPException(400, "이 플랫폼/형식은 미디어를 생성하지 않습니다 (X 는 텍스트 게시).")
    except VideoError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    item.guardian = {**(item.guardian or {}), "media_missing": False}
    db.commit()
    db.refresh(item)
    return content_dict(item, with_children=True)


@router.get("/voice/speakers")
def voice_speakers():
    tts = get_tts()
    if not tts.is_available():
        return {"available": False, "speakers": [], "hint": "VOICEVOX_URL 을 설정하면 음성 목록을 볼 수 있습니다."}
    try:
        return {"available": True, "speakers": tts.speakers()}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "speakers": [], "hint": f"VOICEVOX 연결 실패: {type(exc).__name__}"}
