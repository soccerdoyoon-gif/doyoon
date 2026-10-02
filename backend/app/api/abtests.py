from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.analyzer import interpret_ab_test
from app.analytics.abtest import VariantStat, compare, trials_successes
from app.analytics.stats import latest_metrics
from app.api.deps import get_or_404
from app.api.schemas import ABTestIn, ABVariantUpdate
from app.api.serializers import to_dict
from app.core.database import get_db
from app.models import ABTest, ABVariant

router = APIRouter(prefix="/api/abtests", tags=["abtests"])


def _dict(t: ABTest) -> dict:
    d = to_dict(t)
    d["variants"] = [to_dict(v) for v in t.variants]
    return d


def _sync_from_content(db: Session, t: ABTest) -> None:
    """변형이 콘텐츠와 연결되어 있으면 최신 성과로 수치를 갱신."""
    ids = [v.content_id for v in t.variants if v.content_id]
    metrics = latest_metrics(db, ids)
    for v in t.variants:
        m = metrics.get(v.content_id) if v.content_id else None
        if m:
            v.impressions = m.impressions or m.views or m.reach or 0
            v.clicks = m.clicks or 0
            v.engagements = sum(x or 0 for x in (m.likes, m.comments, m.shares, m.saves))


@router.get("")
def list_tests(db: Session = Depends(get_db)):
    return [_dict(t) for t in db.scalars(select(ABTest).order_by(ABTest.id.desc())).all()]


@router.post("")
def create_test(body: ABTestIn, db: Session = Depends(get_db)):
    t = ABTest(name=body.name, platform=body.platform, variable=body.variable, metric=body.metric, hypothesis=body.hypothesis)
    t.variants = [
        ABVariant(label="A", description=body.variant_a, content_id=body.content_id_a),
        ABVariant(label="B", description=body.variant_b, content_id=body.content_id_b),
    ]
    db.add(t)
    db.commit()
    return _dict(t)


@router.put("/{tid}/variants/{vid}")
def update_variant(tid: int, vid: int, body: ABVariantUpdate, db: Session = Depends(get_db)):
    v = get_or_404(db, ABVariant, vid)
    if v.test_id != tid:
        raise HTTPException(404, "variant not in test")
    for k, val in body.model_dump().items():
        setattr(v, k, val)
    db.commit()
    return to_dict(v)


@router.post("/{tid}/evaluate")
def evaluate(tid: int, use_ai: bool = True, db: Session = Depends(get_db)):
    t = get_or_404(db, ABTest, tid)
    _sync_from_content(db, t)
    if len(t.variants) < 2:
        raise HTTPException(400, "변형이 2개 필요합니다.")
    a, b = t.variants[0], t.variants[1]
    stats = [VariantStat(v.label, *trials_successes(t.metric, v.impressions, v.clicks, v.engagements, v.conversions)) for v in (a, b)]
    result = compare(*stats)
    interp = interpret_ab_test(db, t, result) if use_ai else {"interpretation": result.message, "next_steps": []}
    t.conclusion = interp.get("interpretation", result.message)
    if result.verdict == "significant":
        t.status = "COMPLETED"
    db.commit()
    return {"test": _dict(t), "result": result.to_dict(), "ai": interp}


@router.delete("/{tid}")
def delete_test(tid: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, ABTest, tid))
    db.commit()
    return {"ok": True}
