from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_or_404
from app.api.schemas import BrandIn, CampaignIn
from app.api.serializers import to_dict
from app.core.database import get_db
from app.core.timeutil import to_naive_utc
from app.models import BrandProfile, Campaign
from app.services.events import log_event

router = APIRouter(prefix="/api", tags=["brand"])


@router.get("/brand")
def get_brand(db: Session = Depends(get_db)):
    brand = db.query(BrandProfile).first()
    return to_dict(brand) if brand else None


@router.put("/brand")
def put_brand(body: BrandIn, db: Session = Depends(get_db)):
    brand = db.query(BrandProfile).first()
    if brand is None:
        brand = BrandProfile(**body.model_dump())
        db.add(brand)
    else:
        for k, v in body.model_dump().items():
            setattr(brand, k, v)
    log_event("system", "브랜드 프로필 저장", db=db)
    db.commit()
    return to_dict(brand)


@router.get("/campaigns")
def list_campaigns(db: Session = Depends(get_db)):
    return [to_dict(c) for c in db.query(Campaign).order_by(Campaign.id.desc()).all()]


@router.post("/campaigns")
def create_campaign(body: CampaignIn, db: Session = Depends(get_db)):
    data = body.model_dump()
    data["start_date"] = to_naive_utc(data["start_date"])
    data["end_date"] = to_naive_utc(data["end_date"])
    c = Campaign(**data)
    db.add(c)
    db.commit()
    return to_dict(c)


@router.put("/campaigns/{cid}")
def update_campaign(cid: int, body: CampaignIn, db: Session = Depends(get_db)):
    c = get_or_404(db, Campaign, cid)
    for k, v in body.model_dump().items():
        setattr(c, k, to_naive_utc(v) if k.endswith("_date") else v)
    db.commit()
    return to_dict(c)


@router.delete("/campaigns/{cid}")
def delete_campaign(cid: int, db: Session = Depends(get_db)):
    c = get_or_404(db, Campaign, cid)
    if c.is_active:
        raise HTTPException(400, "진행 중인 캠페인은 먼저 비활성화하세요.")
    from app.models import ContentItem

    db.query(ContentItem).filter(ContentItem.campaign_id == cid).update({"campaign_id": None})
    db.delete(c)
    db.commit()
    return {"ok": True}
