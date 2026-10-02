from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.manager import ask
from app.api.schemas import ChatIn
from app.api.serializers import to_dict
from app.core.database import get_db
from app.models import ChatMessage

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("")
def chat(body: ChatIn, db: Session = Depends(get_db)):
    return ask(db, body.session_id, body.message)


@router.get("/{session_id}")
def history(session_id: str, db: Session = Depends(get_db)):
    rows = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id)).all()
    return [to_dict(m) for m in rows]
