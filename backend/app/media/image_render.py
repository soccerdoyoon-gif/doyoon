"""SNS 이미지 렌더링 — 깔끔한 일본 광고 스타일 (미니멀, 짧은 일본어, 모바일 가독성 우선).

배경은 (1) 단색 미니멀 디자인 또는 (2) AI 가 만든 비주얼(텍스트 없음) 을 사용하고,
일본어 문구는 항상 서버에서 선명한 폰트로 합성합니다 (AI 이미지는 일본어 글자가 깨지기 쉬움).
"""
from __future__ import annotations

import hashlib

from PIL import Image, ImageDraw, ImageFilter

from app.media.fonts import font

SIZES = {
    "feed": (1080, 1350),  # Instagram 4:5
    "carousel": (1080, 1350),
    "story": (1080, 1920),  # 9:16
    "thumbnail": (1080, 1920),
    "ad_banner": (1080, 1080),  # 1:1
    "scene": (1080, 1920),
}
ASPECT = {"feed": "4:5", "carousel": "4:5", "story": "9:16", "thumbnail": "9:16", "ad_banner": "1:1", "scene": "9:16"}

# (배경, 글자, 포인트) — 일본 광고에서 흔한 차분한 톤
PALETTES = {
    "minimal": [("#F7F4EF", "#222222", "#C8553D"), ("#FFFFFF", "#1F2933", "#3E7CB1"), ("#EEF3EF", "#22352A", "#5E8C6A"), ("#FBF0EE", "#3A2A2A", "#D0675F")],
    "luxury": [("#151515", "#F5F1E8", "#C9A45C"), ("#1C2230", "#F2EEE6", "#B89B5E")],
    "pop": [("#FFE45C", "#1A1A1A", "#FF4D6D"), ("#4D7CFE", "#FFFFFF", "#FFE45C"), ("#FF6B6B", "#FFFFFF", "#1A1A1A")],
    "street": [("#111111", "#FFFFFF", "#E6FF00"), ("#2B2B2B", "#F2F2F2", "#FF5A1F")],
}
STYLE_TO_PALETTE = {
    "高級感": "luxury", "ラグジュアリー系": "luxury", "若者向け": "pop", "Z世代向け": "pop", "ストリート系": "street",
}
# 행 첫머리에 오면 안 되는 문자 (일본어 줄바꿈 규칙)
NO_LINE_START = set("、。，．・：；？！ー」』）】〕〉》…‥ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ!?),.%")
NO_LINE_END = set("「『（【〔〈《(")


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def palette_for(style: str, seed: str | int) -> tuple[str, str, str]:
    group = PALETTES[STYLE_TO_PALETTE.get(style or "", "minimal")]
    idx = int(hashlib.md5(str(seed).encode()).hexdigest(), 16) % len(group)
    return group[idx]


def wrap_ja(text: str, fnt, max_width: int) -> list[str]:
    """일본어 줄바꿈 (공백이 없어도 폭 기준으로 나누고, 금칙 문자 처리)."""
    lines: list[str] = []
    for para in (text or "").split("\n"):
        cur = ""
        for ch in para:
            trial = cur + ch
            if fnt.getlength(trial) <= max_width or not cur:
                cur = trial
                continue
            if ch in NO_LINE_START and len(cur) > 1:  # 금칙: 다음 줄 첫 글자로 보내지 않음
                cur = trial
                continue
            if cur[-1] in NO_LINE_END and len(cur) > 1:
                lines.append(cur[:-1])
                cur = cur[-1] + ch
                continue
            # 가능하면 「、」 나 공백 바로 뒤에서 줄바꿈 (단어 중간 분리 방지)
            cut = max(cur.rfind("、"), cur.rfind(" "), cur.rfind("　"))
            if 1 <= cut < len(cur) - 1:
                lines.append(cur[: cut + 1])
                cur = cur[cut + 1 :] + ch
                continue
            lines.append(cur)
            cur = ch
        if cur:
            lines.append(cur)
    return lines


def _fit_text(draw, text: str, box_w: int, box_h: int, start: int, minimum: int = 36, max_lines: int = 4):
    size = start
    while size >= minimum:
        f = font(size)
        lines = wrap_ja(text, f, box_w)
        line_h = int(size * 1.35)
        if len(lines) <= max_lines and line_h * len(lines) <= box_h:
            return f, lines, line_h
        size -= 6
    f = font(minimum)
    lines = wrap_ja(text, f, box_w)[:max_lines]
    return f, lines, int(minimum * 1.35)


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1))
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def render(
    purpose: str,
    headline: str,
    *,
    sub_text: str = "",
    brand_name: str = "",
    style: str = "",
    seed: str | int = 0,
    background: Image.Image | None = None,
    layout: str = "center",
    page_label: str = "",
) -> Image.Image:
    w, h = SIZES.get(purpose, SIZES["feed"])
    bg_c, fg_c, accent = palette_for(style, seed)
    if background is not None:
        img = _cover(background.convert("RGB"), (w, h))
        # 글자가 잘 보이도록 아래쪽 그라데이션
        shade = Image.new("L", (1, h))
        for y in range(h):
            shade.putpixel((0, y), int(200 * max(0.0, (y / h - 0.35) / 0.65)))
        overlay = Image.new("RGB", (w, h), (0, 0, 0))
        img = Image.composite(overlay, img, shade.resize((w, h)))
        fg_c, layout = "#FFFFFF", "bottom"
    else:
        img = Image.new("RGB", (w, h), _hex(bg_c))
        deco = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(deco)
        r = int(w * 0.55)
        d.ellipse((w - r // 2, -r // 3, w + r, r), fill=_hex(accent) + (38,))
        d.ellipse((-r // 2, h - r // 2, r // 2, h + r // 2), fill=_hex(accent) + (24,))
        img = Image.alpha_composite(img.convert("RGBA"), deco.filter(ImageFilter.GaussianBlur(2))).convert("RGB")

    draw = ImageDraw.Draw(img)
    pad = int(w * 0.09)
    box_w = w - pad * 2
    box_h = int(h * (0.42 if purpose in ("story", "thumbnail", "scene") else 0.5))
    f, lines, line_h = _fit_text(draw, headline.strip(), box_w, box_h, start=int(w * 0.105))
    block_h = line_h * len(lines)
    sub_f = font(int(w * 0.04), bold=False)
    sub_lines = wrap_ja(sub_text, sub_f, box_w)[:2] if sub_text else []
    sub_h = int(w * 0.04 * 1.5) * len(sub_lines)
    total = block_h + (int(w * 0.05) + sub_h if sub_lines else 0)
    if layout == "bottom":
        y = h - total - int(h * 0.16)
    elif layout == "top":
        y = int(h * 0.14)
    else:
        y = (h - total) // 2
    if background is None and lines:  # 포인트 바
        draw.rectangle((pad, y - int(w * 0.05), pad + int(w * 0.09), y - int(w * 0.05) + 8), fill=_hex(accent))
    for line in lines:
        draw.text((pad, y), line, font=f, fill=_hex(fg_c))
        y += line_h
    if sub_lines:
        y += int(w * 0.05)
        for line in sub_lines:
            draw.text((pad, y), line, font=sub_f, fill=_hex(fg_c))
            y += int(w * 0.04 * 1.5)
    small = font(int(w * 0.032), bold=True)
    if brand_name:
        draw.text((pad, h - pad - int(w * 0.032)), brand_name, font=small, fill=_hex(fg_c))
    if page_label:
        tw = small.getlength(page_label)
        draw.text((w - pad - tw, h - pad - int(w * 0.032)), page_label, font=small, fill=_hex(fg_c))
    return img


def render_subtitle_frame(background: Image.Image, subtitle: str, *, centered: bool = False) -> Image.Image:
    """영상 프레임: 배경 + 짧은 일본어 자막 (외곽선 처리로 가독성 확보).
    centered=True 이면 텍스트 동画 스타일로 화면 중앙에 크게 표시."""
    img = background.copy()
    w, h = img.size
    draw = ImageDraw.Draw(img)
    start = int(w * (0.1 if centered else 0.075))
    box_w = int(w * 0.84)
    # 짧은 자막은 가능한 한 한 줄에 (단어 중간 줄바꿈 방지), 안 되면 줄바꿈
    f, lines, line_h = None, [], 0
    size = start
    while size >= int(w * 0.06):
        cand = font(size)
        if cand.getlength(subtitle) <= box_w:
            f, lines, line_h = cand, [subtitle], int(size * 1.35)
            break
        size -= 4
    if f is None:
        f, lines, line_h = _fit_text(draw, subtitle, box_w, int(h * 0.3), start=start, minimum=40, max_lines=3 if centered else 2)
    y = (h - line_h * len(lines)) // 2 if centered else int(h * 0.70)
    for line in lines:
        tw = f.getlength(line)
        draw.text(((w - tw) / 2, y), line, font=f, fill=(255, 255, 255), stroke_width=7, stroke_fill=(20, 20, 20))
        y += line_h
    return img


def scene_background(text: str, *, style: str, seed: str | int, brand_name: str = "", ai_image: Image.Image | None = None) -> Image.Image:
    """장면 배경. AI 이미지가 없으면 브랜드 컬러의 미니멀 배경 (텍스트 동画 스타일)."""
    if ai_image is not None:
        return _cover(ai_image.convert("RGB"), SIZES["scene"])
    return render("scene", "", brand_name=brand_name, style=style, seed=seed)
