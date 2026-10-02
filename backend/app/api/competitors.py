from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.analyzer import analyze_competitors
from app.api.deps import get_or_404
from app.api.schemas import CompetitorIn, ObservationIn
from app.api.serializers import to_dict
from app.core.database import get_db
from app.models import Competitor, CompetitorObservation

router = APIRouter(prefix="/api/competitors", tags=["competitors"])


def _dict(c: Competitor) -> dict:
    d = to_dict(c)
    d["observations"] = [to_dict(o) for o in c.observations]
    return d


@router.get("")
def list_competitors(db: Session = Depends(get_db)):
    return [_dict(c) for c in db.scalars(select(Competitor).order_by(Competitor.name)).all()]


@router.post("")
def create(body: CompetitorIn, db: Session = Depends(get_db)):
    c = Competitor(**body.model_dump())
    db.add(c)
    db.commit()
    return _dict(c)


@router.put("/{cid}")
def update(cid: int, body: CompetitorIn, db: Session = Depends(get_db)):
    c = get_or_404(db, Competitor, cid)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    db.commit()
    return _dict(c)


@router.delete("/{cid}")
def delete(cid: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, Competitor, cid))
    db.commit()
    return {"ok": True}


@router.post("/{cid}/observations")
def add_observation(cid: int, body: ObservationIn, db: Session = Depends(get_db)):
    c = get_or_404(db, Competitor, cid)
    c.observations.append(CompetitorObservation(**body.model_dump()))
    db.commit()
    return _dict(c)


@router.delete("/observations/{oid}")
def delete_observation(oid: int, db: Session = Depends(get_db)):
    db.delete(get_or_404(db, CompetitorObservation, oid))
    db.commit()
    return {"ok": True}


@router.post("/analyze")
def analyze(db: Session = Depends(get_db)):
    return to_dict(analyze_competitors(db))
