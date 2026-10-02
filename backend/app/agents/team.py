"""콘텐츠 제작 에이전트 팀 (모두 일본 시장 기본).

Content Strategist → Copywriter(+Hashtag) → Short-form Script → Creative Director → Brand Guardian
각 에이전트는 여러 아이템을 한 번에 처리해서 Claude 호출 수(=비용)를 줄입니다.
"""
from __future__ import annotations

from typing import Any

from app.agents import mock_ja
from app.agents.base import as_json, brand_context, run_json, system_prompt
from app.agents.schemas import BRIEFS, COPY, IDEAS, REVIEWS, SCRIPTS, STYLES

PLATFORM_GUIDE = """プラットフォーム別の最適化（同じ文言をコピペしない）:
- Instagram: ビジュアル＋世界観＋共感。保存・シェアを促す。キャプションは冒頭1行で引き込み、改行で読みやすく。ハッシュタグ5〜10個。
- TikTok: 最初の1秒のフックが命。テンポ速く。キャプションは短く。ハッシュタグ3〜5個。
- X: 短く会話っぽく。本音・問いかけ・共感。ハッシュタグは0〜2個。1投稿は全角140字以内（日本語は1文字=2カウントで280）。
- YouTube Shorts: タイトルと最初の3秒に集中。
- 広告: 誇張しない。短い見出し＋具体的なベネフィット＋明確なCTA。"""


def strategist(brand, trend: dict, analysis: dict, count: int, platforms: list[str], theme: str, style: str, language: str, seed: int) -> tuple[list[dict], str]:
    prompt = (
        f"{brand_context(brand)}\n\n<trend_report>\n{as_json(trend)}\n</trend_report>\n"
        f"<latest_performance_analysis>\n{as_json(analysis)}\n</latest_performance_analysis>\n"
        f"対象プラットフォーム: {', '.join(platforms)}\n" + (f"今回のテーマ・依頼: {theme}\n" if theme else "")
        + (f"指定スタイル: {style}\n" if style else f"スタイルは次から最適なものを選ぶ: {', '.join(STYLES)}\n")
        + f"日本の消費者に刺さるコンテンツのアイデアを{count}個出してください。それぞれ切り口を変え、"
        "トレンドの中で日本で実際に使えるものだけを参考にし（trend_refs に記載）、過去の分析結果の改善点を反映してください。"
    )
    data, src = run_json(
        "content_strategist", system_prompt("あなたは日本市場専門のSNSコンテンツストラテジストです。", language), prompt, IDEAS,
        lambda: mock_ja.ideas(brand, count, style, seed),
    )
    return (data.get("ideas") or [])[:count], src


def copywriter(brand, ideas: list[dict], platforms: list[str], trend: dict, overused: list[str], language: str) -> tuple[list[dict], str]:
    prompt = (
        f"{brand_context(brand)}\n\n<ideas>\n{as_json([{'idea_index': i, **x} for i, x in enumerate(ideas)])}\n</ideas>\n"
        f"<trend_report>\n{as_json({'platform_trends': trend.get('platform_trends', [])})}\n</trend_report>\n"
        f"<recently_overused_hashtags>{as_json(overused)}</recently_overused_hashtags>\n"
        f"作成するプラットフォーム: {', '.join(platforms)} と広告(ads)。対象外のプラットフォームの項目は空文字・空配列にしてください。\n\n"
        f"{PLATFORM_GUIDE}\n\n"
        "コピーライティングのルール:\n"
        "- 日本の広告コピーライターとして、アイデアの style（カジュアル／高級感／Z世代向け など）に合わせて書く。\n"
        "- 文は短く。特に短尺動画は1文目を強く（例の雰囲気:「これ、知らないと損。」「正直、最初は期待してなかった。」「3秒だけ見て。」）。ただし例をそのまま使い回さない。\n"
        "- ハッシュタグは日本語中心でコンテンツとブランドに合わせて毎回考える。recently_overused_hashtags ばかり使わない。#付きで。\n"
        "- instagram.content_type は post / carousel / reel から内容に合うものを選ぶ。carousel の場合 carousel_slides に各スライドの短い文言（3〜7枚）。\n"
        "- thumbnail_text と ads.image_text は画像内に入れる文字なので全角12文字前後まで。\n"
        "- x.post_type が thread の場合は thread に3〜6投稿、post は1投稿目と同じ。\n"
        "- youtube_shorts_title は30字以内。"
    )
    data, src = run_json(
        "copywriter", system_prompt("あなたは日本の広告コピーライター兼SNSハッシュタグ担当です。", language), prompt, COPY,
        lambda: mock_ja.copy(brand, ideas), max_tokens=32000,
    )
    return data.get("packages") or [], src


def script_writer(brand, targets: list[dict], language: str) -> tuple[dict[str, dict], str]:
    """targets: [{item_key, platform, idea, hook, cta}] → {item_key: script}"""
    if not targets:
        return {}, "skip"
    prompt = (
        f"{brand_context(brand)}\n\n<videos>\n{as_json(targets)}\n</videos>\n"
        "それぞれの縦型ショート動画（9:16、TikTok / Instagram Reels / YouTube Shorts）の台本を作ってください。\n"
        "基本構成: 0〜1秒 強いフック → 1〜3秒 疑問・興味づけ → 3〜10秒 核となる価値 → 10〜20秒 商品・サービスの説明 → 最後 CTA。\n"
        "- scenes は4〜7個、duration は秒数、合計15〜30秒程度。purpose に構成上の役割。\n"
        "- voiceover（セリフ）と subtitle（字幕）は短く速いテンポの日本語。字幕は1画面で読める長さ（全角15字前後で句点ごと）に。\n"
        "- visual は撮影・生成する映像の内容（日本語、日本の生活シーン）、camera はカメラワーク。\n"
        "- video_prompt は外部の動画生成AI用の英語プロンプト（9:16、テキストなし）。\n"
        "- TikTok はテンポ重視、Reels は世界観・ビジュアル重視で、同じ台本にしない。"
    )
    data, src = run_json(
        "shortform_script", system_prompt("あなたは日本のショート動画ディレクター兼台本作家です。", language), prompt, SCRIPTS,
        lambda: {"scripts": [mock_ja.script(t["item_key"], t["hook"], mock_ja._p(brand), t["cta"]) for t in targets]},
        max_tokens=32000,
    )
    return {s["item_key"]: s for s in data.get("scripts", [])}, src


def creative_director(brand, targets: list[dict], language: str) -> tuple[dict[str, dict], str]:
    """targets: [{item_key, platform, content_type, hook, caption, purposes[]}] → {item_key: brief}"""
    if not targets:
        return {}, "skip"
    prompt = (
        f"{brand_context(brand)}\n\n<items>\n{as_json(targets)}\n</items>\n"
        "各アイテムの purposes ごとに画像ブリーフを作ってください（feed=4:5, story=9:16, ad_banner=1:1, thumbnail=9:16）。\n"
        "デザイン方針: すっきりした日本の広告デザイン、ミニマル、モバイルで読みやすい、文字を入れすぎない。\n"
        "- overlay_text: 画像に入れる日本語。全角12文字前後まで、短く強く。\n"
        "- sub_text: 補足（全角20文字まで、不要なら空）。\n"
        "- visual_prompt: 画像生成AI用の英語プロンプト。日本の生活シーン・商品の雰囲気。画像内に文字を入れない指示は不要（システムで付与）。"
    )
    data, src = run_json(
        "creative_director", system_prompt("あなたは日本のSNS・広告のクリエイティブディレクターです。", language), prompt, BRIEFS,
        lambda: {"briefs": [mock_ja.brief(t["item_key"], t.get("thumbnail_text") or t["hook"][:12], "", t["purposes"]) for t in targets]},
    )
    return {b["item_key"]: b for b in data.get("briefs", [])}, src


def guardian_review(brand, items: list[dict], language: str) -> tuple[dict[str, dict], str]:
    """items: [{item_key, platform, content_type, hook, caption, cta, hashtags, thread, thumbnail_text, subtitles, rule_issues}]"""
    if not items:
        return {}, "skip"
    prompt = (
        f"{brand_context(brand)}\n\n<items>\n{as_json(items)}\n</items>\n"
        "ブランドガーディアンとして各アイテムを日本人の目線でチェックしてください:\n"
        "日本語の文法 / 不自然な表現 / 韓国語の直訳っぽさ / 攻撃的すぎる広告表現 / 過度な誇張 / 日本文化的に違和感のある表現 / 禁止表現。"
        "rule_issues は機械チェックの結果です。\n"
        "- 問題なし→ verdict=pass。直せる問題→ verdict=fix として corrected に修正後の文言（変更しない項目は空文字・空配列）。"
        "subtitles を直す場合は全シーン分を順番どおりに。\n"
        "- 根本的に使えない（ブランド毀損・虚偽・不適切）→ verdict=reject。\n"
        "- scores は1〜10の整数で厳しめに（社内の優先順位付け用。実際の成果予測ではない）。score_note は改善のヒント1行。"
    )

    def fallback():
        return {"reviews": [{
            "item_key": it["item_key"], "verdict": "pass", "issues": [], "score_note": "[MOCK] ルールベースの仮スコア",
            "corrected": {"hook": "", "caption": "", "cta": "", "thumbnail_text": "", "hashtags": [], "thread": [], "subtitles": []},
            "scores": {"hook_strength": 6, "target_audience_fit": 6, "brand_consistency": 7, "cta_quality": 6 if it.get("cta") else 3,
                       "originality": 5, "expected_engagement": 6},
        } for it in items]}

    data, src = run_json(
        "brand_guardian", system_prompt("あなたは厳格な日本語ネイティブのブランドガーディアン（表現・法務チェック担当）です。", language),
        prompt, REVIEWS, fallback, max_tokens=32000,
    )
    return {r["item_key"]: r for r in data.get("reviews", [])}, src


def apply_corrections(item: Any, corrected: dict) -> list[str]:
    changed = []
    for f in ("hook", "caption", "cta", "thumbnail_text"):
        if corrected.get(f):
            setattr(item, f, corrected[f])
            changed.append(f)
    if corrected.get("hashtags"):
        item.hashtags = corrected["hashtags"]
        changed.append("hashtags")
    if corrected.get("thread"):
        item.thread = corrected["thread"]
        item.caption = corrected["thread"][0]
        changed.append("thread")
    subs = corrected.get("subtitles") or []
    if subs and item.scenes and len(subs) == len(item.scenes):
        item.scenes = [{**sc, "subtitle": s} for sc, s in zip(item.scenes, subs)]
        changed.append("subtitles")
    return changed
