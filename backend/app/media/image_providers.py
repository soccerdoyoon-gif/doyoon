"""이미지 비주얼 생성 Provider.

- template: 외부 API 없이 서버에서 디자인 (무료, 기본값)
- openai  : OpenAI Images API 로 '텍스트 없는' 배경 비주얼 생성 → 일본어 문구는 서버에서 합성
새 Provider 는 ImageProvider 를 상속해서 PROVIDERS 에 등록하면 됩니다.
"""
from __future__ import annotations

import base64
import io

import httpx
from PIL import Image

from app.core.config import get_settings
from app.services.events import log_event


class ImageProvider:
    name = "template"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, aspect: str) -> Image.Image | None:
        return None  # template: 배경 비주얼 없음 → 미니멀 디자인


class OpenAIImageProvider(ImageProvider):
    name = "openai"
    SIZES = {"9:16": "1024x1536", "4:5": "1024x1536", "1:1": "1024x1024", "16:9": "1536x1024"}

    def __init__(self, http: httpx.Client | None = None):
        self.http = http or httpx.Client(timeout=httpx.Timeout(180.0))

    def is_available(self) -> bool:
        return bool(get_settings().openai_api_key)

    def generate(self, prompt: str, aspect: str) -> Image.Image | None:
        s = get_settings()
        full = (
            prompt
            + ". Clean minimal Japanese advertising photography style, soft natural light, mobile-first composition, "
            "leave empty space for text. Absolutely no text, no letters, no logos, no watermarks."
        )
        try:
            resp = self.http.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {s.openai_api_key}"},
                json={"model": s.openai_image_model, "prompt": full, "size": self.SIZES.get(aspect, "1024x1024"), "n": 1},
            )
            resp.raise_for_status()
            b64 = resp.json()["data"][0]["b64_json"]
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        except (httpx.HTTPError, KeyError, ValueError, OSError) as exc:
            log_event("api_error", f"이미지 생성 API 실패 → 템플릿 디자인으로 대체: {type(exc).__name__}", level="WARNING")
            return None


PROVIDERS: dict[str, type[ImageProvider]] = {"template": ImageProvider, "openai": OpenAIImageProvider}
_override: ImageProvider | None = None


def get_image_provider() -> ImageProvider:
    if _override is not None:
        return _override
    p = PROVIDERS.get(get_settings().image_provider, ImageProvider)()
    return p if p.is_available() else ImageProvider()


def set_image_override(p: ImageProvider | None) -> None:
    global _override
    _override = p
