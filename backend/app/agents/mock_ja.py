"""Mock(Claude 키 없음)용 일본어 템플릿. 결과에는 [MOCK] 표시 + source='mock_ai'."""
from __future__ import annotations

import random
from typing import Any

HOOKS = ["これ、知らないと損。", "正直、最初は期待してなかった。", "3秒だけ見て。", "日本でこれ使ってる人、まだ少ない。", "毎日のこれ、変えてみた。", "買ってよかったもの、ひとつだけ。"]
ANGLES = ["使ってみた正直レビュー", "よくある失敗3つ", "朝のルーティン", "ビフォーアフター", "選び方のコツ", "作り手のこだわり"]
CTAS = ["保存して見返してね", "気になったらプロフのリンクから", "コメントで教えてね", "まずはチェックしてみて"]
BASE_TAGS = ["#おすすめ", "#話題", "#新作", "#購入品", "#ライフスタイル", "#暮らし", "#日常", "#買ってよかった"]


def short(text: str, n: int = 16) -> str:
    """썸네일용 짧은 문구: 단어 중간에서 자르지 않도록 구두점 기준."""
    text = text.strip()
    if len(text) <= n:
        return text
    for sep in ("。", "、", "！", "？"):
        i = text.find(sep)
        if 0 < i < n:
            return text[: i + (1 if sep != "、" else 0)]
    return text[:n]


def _p(brand: Any) -> str:
    raw = (getattr(brand, "main_products", "") or getattr(brand, "product_description", "") or getattr(brand, "brand_name", "") or "商品")
    return raw.replace("、", ",").split(",")[0].strip()[:20]


def trend() -> dict:
    return {
        "summary": "[MOCK] Claude 未接続のため、一般的な傾向の候補のみです（未検証）。実際のトレンドは API Key 設定後に調査します。",
        "platform_trends": [
            {"platform": "tiktok", "formats": ["正直レビュー", "ルーティン動画", "ビフォーアフター"], "hooks": HOOKS[:4],
             "expressions": ["正直", "ガチで", "神"], "hashtags": ["#おすすめ", "#購入品", "#tiktok教室"],
             "ideal_video_length": "15〜30秒（仮説）", "ctas": ["保存してね", "プロフから見てね"], "notes": "未検証の一般的な候補"},
            {"platform": "instagram_reels", "formats": ["保存したくなる解説", "世界観のある短尺動画"], "hooks": HOOKS[1:3],
             "expressions": ["保存版", "まとめ"], "hashtags": ["#暮らし", "#丁寧な暮らし"], "ideal_video_length": "7〜20秒（仮説）",
             "ctas": ["保存して見返してね"], "notes": "未検証の一般的な候補"},
            {"platform": "x", "formats": ["短い本音ポスト", "質問型ポスト"], "hooks": ["これ地味に便利", "みんなはどうしてる？"],
             "expressions": ["地味に", "わかる"], "hashtags": [], "ideal_video_length": "-", "ctas": ["リプで教えて"], "notes": "ハッシュタグは少なめ"},
        ],
        "competitor_styles": [],
        "global_trends_applicability": [],
        "evidence": "general_knowledge",
        "data_limitations": "Claude API Key がないため実データ・ウェブ調査なし。参考程度にしてください。",
    }


def ideas(brand: Any, count: int, style: str, seed: int = 0) -> dict:
    rng = random.Random(seed)
    angles = ANGLES[:]
    rng.shuffle(angles)
    p = _p(brand)
    return {"ideas": [
        {"title": f"[MOCK] {p}｜{angles[i % len(angles)]}", "concept": f"{p}を{angles[i % len(angles)]}の切り口で紹介",
         "angle": angles[i % len(angles)], "target_insight": "忙しい毎日でも手軽に取り入れたい", "style": style or "親しみやすい",
         "trend_refs": ["正直レビュー"], "hook_direction": HOOKS[(i + seed) % len(HOOKS)]}
        for i in range(count)
    ]}


def copy(brand: Any, ideas_: list[dict]) -> dict:
    p = _p(brand)
    name = getattr(brand, "brand_name", "") or ""
    out = []
    for i, idea in enumerate(ideas_):
        hook = idea.get("hook_direction") or HOOKS[i % len(HOOKS)]
        angle = idea.get("angle", "")
        tags = BASE_TAGS[i % 4: i % 4 + 4]
        out.append({
            "idea_index": i,
            "instagram": {"content_type": ["post", "reel", "carousel"][i % 3], "hook": hook,
                          "caption": f"[MOCK] {hook}\n\n{p}の「{angle}」をまとめました。\n毎日にちょっとした変化を。",
                          "cta": CTAS[0], "hashtags": tags + [f"#{name.replace(' ', '')}"] if name else tags,
                          "carousel_slides": [hook, "ポイント①", "ポイント②", "ポイント③", "保存して見返してね"], "thumbnail_text": short(hook)},
            "tiktok": {"hook": hook, "caption": f"[MOCK] {angle}｜{p}", "cta": CTAS[1], "hashtags": ["#おすすめ", "#購入品", "#fyp"][: 3],
                       "thumbnail_text": short(hook), "youtube_shorts_title": f"{p}、{angle}"},
            "x": {"post_type": ["tweet", "info_tweet", "thread", "ad_tweet"][i % 4], "post": f"[MOCK] {p}、{angle}してみたら地味に良かった。みんなはどうしてる？",
                  "thread": [f"[MOCK] {p}の{angle}まとめ🧵", "① まずはここから", "② 続けるコツ", "③ 気になる人はプロフから"]},
            "facebook": {"post": f"[MOCK] {p}｜{angle}", "hashtags": ["#おすすめ"]},
            "ads": {"headline": f"{p}で毎日をちょっと楽しく", "primary_text": f"[MOCK] {hook} {p}の魅力をチェック。", "description": angle,
                    "cta": "詳しくはこちら", "image_text": short(hook)},
        })
    return {"packages": out}


def script(item_key: str, hook: str, product: str, cta: str) -> dict:
    return {
        "item_key": item_key, "music_style": "明るいローファイ", "video_prompt": f"Vertical 9:16 short video introducing {product}, Japanese lifestyle, natural light",
        "scenes": [
            {"scene_id": 1, "duration": 1.5, "purpose": "hook", "visual": "商品のアップ", "camera": "寄り", "voiceover": hook, "subtitle": hook, "music_style": "イントロ"},
            {"scene_id": 2, "duration": 2, "purpose": "curiosity", "visual": "使う前の様子", "camera": "手元", "voiceover": "実はずっと悩んでた。", "subtitle": "実はずっと悩んでた。", "music_style": ""},
            {"scene_id": 3, "duration": 5, "purpose": "value", "visual": "使っているシーン", "camera": "固定", "voiceover": f"{product}にしてから、毎日がちょっとラクに。", "subtitle": f"{product}にしてから、毎日がちょっとラクに。", "music_style": ""},
            {"scene_id": 4, "duration": 6, "purpose": "product", "visual": "商品の特徴", "camera": "パン", "voiceover": "ポイントはこの手軽さ。", "subtitle": "ポイントはこの手軽さ。", "music_style": ""},
            {"scene_id": 5, "duration": 2.5, "purpose": "cta", "visual": "ロゴと商品", "camera": "引き", "voiceover": cta, "subtitle": cta, "music_style": "アウトロ"},
        ],
    }


def brief(item_key: str, overlay: str, sub: str, purposes: list[str]) -> dict:
    return {"item_key": item_key, "color_mood": "ナチュラル・ミニマル",
            "images": [{"purpose": pp, "overlay_text": overlay, "sub_text": sub, "visual_prompt": ""} for pp in purposes]}
