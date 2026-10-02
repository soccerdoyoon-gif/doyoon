"""일본어 폰트 탐색. FONT_PATH 로 직접 지정 가능."""
from __future__ import annotations

import os
from functools import lru_cache

from PIL import ImageFont

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("fonts")

BOLD_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "C:/Windows/Fonts/YuGothB.ttc",
    "C:/Windows/Fonts/meiryob.ttc",
]
REGULAR_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
    "C:/Windows/Fonts/YuGothM.ttc",
    "C:/Windows/Fonts/meiryo.ttc",
    "C:/Windows/Fonts/msgothic.ttc",
]


@lru_cache
def find_font(bold: bool = True) -> str | None:
    custom = get_settings().font_path
    if custom and os.path.exists(custom):
        return custom
    for path in (BOLD_CANDIDATES + REGULAR_CANDIDATES) if bold else (REGULAR_CANDIDATES + BOLD_CANDIDATES):
        if os.path.exists(path):
            return path
    logger.warning("일본어 폰트를 찾지 못했습니다. FONT_PATH 를 설정하세요 (README 참고).")
    return None


@lru_cache(maxsize=64)
def font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = find_font(bold)
    if path is None:
        return ImageFont.load_default(size=size)
    return ImageFont.truetype(path, size=size, index=0)
