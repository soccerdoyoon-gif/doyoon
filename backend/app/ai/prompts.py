"""프롬프트 구성 요소 — 브랜드 메모리, 언어별 현지화 가이드, 공통 규칙."""
from __future__ import annotations

import json
from typing import Any

from app.models import BrandProfile

LANGUAGE_GUIDE = {
    "ko": (
        "모든 콘텐츠를 한국어로 작성하세요. 한국 인스타그램/틱톡/X 사용자가 실제로 쓰는 자연스러운 말투로, "
        "번역투를 피하고 짧은 문장과 줄바꿈을 활용하세요. 해시태그는 한국에서 실제로 검색되는 형태(한글 위주, 필요시 영문 혼용)로 작성하세요."
    ),
    "ja": (
        "すべてのコンテンツを日本語で作成してください。直訳ではなく、日本のInstagram・TikTok・Xで自然に見える表現にしてください。"
        "ブランドトーンに合わせて丁寧語/カジュアルを使い分け、絵文字は控えめに。ハッシュタグは日本で実際に検索される日本語タグを中心にしてください。"
    ),
    "en": (
        "Write all content in natural, native English for the target country's social media culture. "
        "Avoid literal translation, keep sentences punchy, and use hashtags people actually search."
    ),
}

COMMON_RULES = """규칙:
- 브랜드 프로필의 금지어(forbidden_words)는 절대 사용하지 말고, 선호 단어(preferred_words)는 자연스럽게 활용하세요.
- 과장 광고, 허위 효능, 의학적/금전적 보장 표현을 쓰지 마세요. 플랫폼 정책을 지키세요.
- 경쟁사 문구나 과거 성과 좋은 문구를 그대로 복사하지 말고 특징만 참고해 새로 쓰세요.
- 제공된 데이터에 없는 수치나 사실을 지어내지 마세요. data_source 가 'mock' 인 데이터는 테스트용 가짜 데이터입니다.
"""


def brand_context(brand: BrandProfile | None) -> str:
    if brand is None:
        return "브랜드 프로필이 아직 없습니다."
    data: dict[str, Any] = {
        "brand_name": brand.brand_name,
        "brand_description": brand.brand_description,
        "product_description": brand.product_description,
        "main_products": brand.main_products,
        "target_customer": brand.target_customer,
        "country": brand.country,
        "language": brand.language,
        "brand_voice": brand.brand_voice,
        "brand_values": brand.brand_values,
        "forbidden_words": brand.forbidden_words,
        "preferred_words": brand.preferred_words,
        "competitors": brand.competitors,
        "main_goal": brand.main_goal,
        "website_url": brand.website_url,
    }
    return "<brand_profile>\n" + json.dumps(data, ensure_ascii=False, indent=1) + "\n</brand_profile>"


def language_guide(lang: str) -> str:
    return LANGUAGE_GUIDE.get(lang, LANGUAGE_GUIDE["en"])


def as_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)
