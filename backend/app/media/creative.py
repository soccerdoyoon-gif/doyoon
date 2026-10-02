"""Creative Director 의 브리프를 실제 이미지 파일로 만드는 함수들."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.media import image_render, storage
from app.media.image_providers import get_image_provider
from app.media.video import save_jpeg
from app.models import GeneratedAsset


def make_image(
    db: Session,
    purpose: str,
    overlay_text: str,
    *,
    visual_prompt: str = "",
    sub_text: str = "",
    brand_name: str = "",
    style: str = "",
    seed: int | str = 0,
    content_id: int | None = None,
    ad_id: int | None = None,
    idea_id: int | None = None,
    order: int = 0,
    page_label: str = "",
) -> GeneratedAsset:
    provider = get_image_provider()
    aspect = image_render.ASPECT.get(purpose, "4:5")
    background = provider.generate(visual_prompt, aspect) if visual_prompt and provider.name != "template" else None
    img = image_render.render(
        purpose, overlay_text, sub_text=sub_text, brand_name=brand_name, style=style, seed=seed,
        background=background, page_label=page_label,
    )
    kind = "thumbnail" if purpose == "thumbnail" else "image"
    abs_p, rel = storage.new_file(kind, "jpg", content_id=content_id, ad_id=ad_id, purpose=purpose)
    save_jpeg(img, abs_p, content_id, ad_id)
    return storage.record(
        db, kind, rel, content_id=content_id, ad_creative_id=ad_id, idea_id=idea_id, purpose=purpose, aspect=aspect,
        width=img.width, height=img.height, provider=provider.name if background is not None else "template",
        prompt=visual_prompt, overlay_text=overlay_text, order=order,
    )
