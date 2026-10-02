"""생성 파일 저장: assets/generated/{images,videos,thumbnails,audio,subtitles}/

파일 이름에 콘텐츠 ID 를 넣고(c{id}_...), DB(generated_assets)에도 연결 정보를 저장합니다.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import GeneratedAsset

FOLDERS = {"image": "images", "video": "videos", "thumbnail": "thumbnails", "audio": "audio", "subtitle": "subtitles", "scenes": "videos"}


def generated_root() -> Path:
    root = get_settings().assets_dir / "generated"
    for sub in set(FOLDERS.values()):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def new_file(kind: str, ext: str, *, content_id: int | None = None, ad_id: int | None = None, purpose: str = "") -> tuple[Path, str]:
    owner = f"c{content_id}" if content_id else f"ad{ad_id}" if ad_id else "x"
    name = f"{owner}_{purpose or kind}_{uuid.uuid4().hex[:8]}.{ext}"
    rel = f"{FOLDERS[kind]}/{name}"
    return generated_root() / rel, rel


def abs_path(rel: str) -> Path:
    return generated_root() / rel


def record(db: Session, kind: str, rel: str, **fields) -> GeneratedAsset:
    asset = GeneratedAsset(kind=kind, path=rel, **fields)
    db.add(asset)
    db.flush()
    return asset
