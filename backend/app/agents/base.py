"""에이전트 공통: 일본 시장 기본 규칙 + Claude 호출 (키가 없으면 Mock)."""
from __future__ import annotations

from typing import Any, Callable

from app.ai.client import AIError, get_ai
from app.ai.prompts import as_json, brand_context
from app.services.events import log_event

LANG_NAME = {"ja": "日本語", "ko": "韓国語(한국어)", "en": "英語(English)"}

JAPAN_RULES = """あなたは日本市場に特化したSNSマーケティングチームの一員です。
対象市場: 日本 / ターゲット: 日本在住の消費者 / 通貨: 円(JPY) / 時間: 日本時間(JST)

共通ルール:
- 日本のSNSで実際の人が書くような、自然で短く読みやすい日本語にする。
- 翻訳調、韓国語の直訳表現、不自然に硬い敬語・過剰な敬語は使わない。
- 誇大広告や虚偽表現は禁止。根拠のない「絶対」「必ず」「No.1」「日本一」「最安」「100%」、
  医薬品的な効果効能（治る・痩せる・シミが消える等）は使わない（景品表示法・薬機法に配慮）。
- ブランドの forbidden_words は絶対に使わない。preferred_words は自然な範囲で使う。
- 与えられたデータにない数値・事実・実績を作らない。source/data_source が mock のデータはテスト用の偽データ。
- 競合や過去の投稿の文言をそのままコピーしない。特徴だけ参考にして新しく書く。
- 同じ文言を全SNSにコピペしない。プラットフォームごとに最適化する。"""


def lang_rule(language: str) -> str:
    if language == "ja":
        return "出力するコンテンツ（キャプション、フック、台本、字幕、CTA、ハッシュタグ、画像内テキスト）はすべて自然な日本語。"
    return (
        f"ユーザーの明示的な依頼により、今回のコンテンツは{LANG_NAME.get(language, language)}で作成する。"
        "ただしターゲットは日本在住の人であることを前提に、日本の文化・SNS習慣に合わせる。"
    )


def system_prompt(role: str, language: str = "ja") -> str:
    return f"{role}\n\n{JAPAN_RULES}\n- {lang_rule(language)}"


def run_json(purpose: str, system: str, prompt: str, schema: dict, fallback: Callable[[], dict], max_tokens: int = 16000) -> tuple[dict, str]:
    """Claude 로 JSON 생성. 키가 없거나 실패하면 fallback(Mock) 결과."""
    ai = get_ai()
    if ai.is_available():
        try:
            return ai.generate_json(purpose, system, prompt, schema, max_tokens=max_tokens), "ai"
        except AIError as exc:
            log_event("api_error", f"{purpose} AI 실패 → Mock 으로 대체: {exc}", level="WARNING")
    return fallback(), "mock_ai"


__all__ = ["JAPAN_RULES", "as_json", "brand_context", "lang_rule", "run_json", "system_prompt"]
