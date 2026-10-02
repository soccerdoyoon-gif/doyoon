"""Mock AI — Claude API Key 가 없을 때 사용하는 규칙 기반 생성기.

결과물에는 [MOCK AI] 표시가 붙고 source='mock_ai' 로 저장됩니다.
분석 계열은 실제 DB 데이터를 규칙으로 요약하므로 수치를 지어내지 않습니다.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

T = {
    "ko": {
        "hook": ["{p}, 아직도 모르세요?", "딱 3초만 보세요 — {p}의 진짜 차이", "{t}이(가) 가장 많이 묻는 질문", "이거 하나로 달라졌어요", "솔직 후기: {p} 써보니"],
        "caption": "{b}의 {p}. {t}을(를) 위해 만들었어요.\n\n오늘은 {angle} 이야기를 해볼게요.",
        "cta": ["프로필 링크에서 자세히 보기", "저장해두고 필요할 때 꺼내보세요", "댓글로 궁금한 점 남겨주세요", "지금 확인해보세요"],
        "angles": ["사용 전후 비교", "자주 하는 실수", "고객 후기", "제작 비하인드", "3가지 꿀팁", "가격 대비 가치"],
        "media": "밝은 자연광, 제품 클로즈업 + 사용 장면 컷",
        "script": ["[0-3초] 훅: {h}", "[3-10초] 문제 상황 보여주기", "[10-20초] {p} 사용 장면", "[20-25초] 결과 + CTA"],
        "info": "알고 계셨나요? {p}를 고를 때 꼭 확인할 3가지 👇",
        "ad": "{t}을(를) 위한 {p}. 지금 바로 만나보세요 →",
        "thread": ["{p}에 대해 자주 받는 질문 5가지 정리 🧵", "1. 어떤 분께 맞나요? → {t}", "2. 사용법은? → 간단해요", "3. 더 궁금하면 댓글로!"],
    },
    "ja": {
        "hook": ["{p}、まだ知らないの？", "3秒だけ見て — {p}の本当の違い", "{t}によく聞かれる質問", "これ一つで変わりました", "正直レビュー：{p}を使ってみた"],
        "caption": "{b}の{p}。{t}のために作りました。\n\n今日は「{angle}」についてお話しします。",
        "cta": ["詳しくはプロフィールのリンクから", "保存して後で見返してね", "気になることはコメントで教えてください", "今すぐチェック"],
        "angles": ["ビフォーアフター", "よくある失敗", "お客様の声", "制作の裏側", "3つのコツ", "コスパ"],
        "media": "自然光、商品のクローズアップ＋使用シーン",
        "script": ["[0-3秒] フック：{h}", "[3-10秒] 悩みのシーン", "[10-20秒] {p}の使用シーン", "[20-25秒] 結果＋CTA"],
        "info": "知ってましたか？{p}を選ぶときに確認したい3つのポイント👇",
        "ad": "{t}のための{p}。今すぐチェック →",
        "thread": ["{p}についてよくある質問まとめ🧵", "1. どんな人向け？→ {t}", "2. 使い方は？→ とても簡単です", "3. 質問はリプで！"],
    },
    "en": {
        "hook": ["Still don't know about {p}?", "Give me 3 seconds — the real difference of {p}", "The #1 question {t} ask us", "This one thing changed everything", "Honest review: I tried {p}"],
        "caption": "{p} by {b}. Made for {t}.\n\nToday: {angle}.",
        "cta": ["Tap the link in bio", "Save this for later", "Drop your questions in the comments", "Check it out now"],
        "angles": ["before vs after", "common mistakes", "customer stories", "behind the scenes", "3 quick tips", "value for money"],
        "media": "Natural light, product close-up + in-use shots",
        "script": ["[0-3s] Hook: {h}", "[3-10s] Show the problem", "[10-20s] {p} in action", "[20-25s] Result + CTA"],
        "info": "Did you know? 3 things to check before choosing {p} 👇",
        "ad": "{p} for {t}. See it now →",
        "thread": ["5 questions we always get about {p} 🧵", "1. Who is it for? → {t}", "2. How to use it? → It's simple", "3. More questions? Reply below!"],
    },
}


def _tpl(lang: str) -> dict:
    return T.get(lang, T["en"])


def content_candidates(brand: Any, slots: list[dict], lang: str) -> list[dict]:
    t = _tpl(lang)
    b = getattr(brand, "brand_name", "Brand") or "Brand"
    p = (getattr(brand, "main_products", "") or getattr(brand, "product_description", "") or b).split("\n")[0][:40]
    tgt = (getattr(brand, "target_customer", "") or "customers")[:40]
    out = []
    for i, slot in enumerate(slots):
        ctype = slot["content_type"]
        hook = "[MOCK AI] " + t["hook"][i % len(t["hook"])].format(p=p, t=tgt)
        angle = t["angles"][i % len(t["angles"])]
        caption = t["caption"].format(b=b, p=p, t=tgt, angle=angle)
        script = ""
        structure: list[str] = []
        thread: list[str] = []
        if ctype in ("reel", "short_video"):
            structure = [s.format(h=hook, p=p) for s in t["script"]]
            script = "\n".join(structure)
        if ctype == "info_tweet":
            caption = t["info"].format(p=p)
        elif ctype == "ad_tweet":
            caption = t["ad"].format(p=p, t=tgt)
        elif ctype == "thread":
            thread = [s.format(p=p, t=tgt) for s in t["thread"]]
            caption = thread[0]
        elif ctype == "tweet":
            caption = f"{hook.replace('[MOCK AI] ', '')} — {angle}"
        tag = "".join(ch for ch in b if ch.isalnum()) or "brand"
        out.append({
            "slot": slot["slot"],
            "platform": slot["platform"],
            "content_type": ctype,
            "title": f"[MOCK AI] {slot['platform']} {ctype} — {angle}",
            "idea": f"{angle} ({p})",
            "hook": hook,
            "caption": caption,
            "script": script,
            "structure": structure,
            "thread": thread,
            "cta": t["cta"][i % len(t["cta"])],
            "hashtags": [f"#{tag}", f"#{angle.replace(' ', '')}"] + (["#fyp"] if slot["platform"] == "tiktok" else []),
            "media_idea": t["media"],
            "suggested_time_local": "",
            "rationale": "Claude API Key 가 없어 템플릿으로 생성한 테스트용 콘텐츠입니다.",
        })
    return out


def scores(candidates: list[dict]) -> list[dict]:
    out = []
    for i, c in enumerate(candidates):
        hook_len = len(c.get("hook", ""))
        out.append({
            "index": i,
            "hook_strength": 7 if 10 <= hook_len <= 60 else 5,
            "target_audience_fit": 6,
            "brand_consistency": 7,
            "cta_quality": 7 if c.get("cta") else 3,
            "originality": 5,
            "expected_engagement": 6 if c.get("hashtags") else 4,
            "note": "[MOCK AI] 규칙 기반 임시 점수",
        })
    return out


def content_analysis(rows: list[dict]) -> dict:
    scored = sorted([r for r in rows if r.get("engagement_rate") is not None], key=lambda r: r["engagement_rate"], reverse=True)
    hours: dict[int, list[float]] = defaultdict(list)
    platforms: dict[str, list[float]] = defaultdict(list)
    for r in scored:
        if r.get("hour") is not None:
            hours[r["hour"]].append(r["engagement_rate"])
        platforms[r["platform"]].append(r["engagement_rate"])
    best_hours = sorted(hours.items(), key=lambda kv: sum(kv[1]) / len(kv[1]), reverse=True)[:3]
    mock = any(r.get("data_source") == "mock" for r in rows)
    return {
        "summary": f"[MOCK AI] 게시물 {len(rows)}개 중 성과 데이터가 있는 {len(scored)}개를 규칙 기반으로 요약했습니다."
        + (" (주의: mock 테스트 데이터 포함)" if mock else ""),
        "top_content": [f"#{r['id']} {r['platform']} {r['title'][:40]} (ER {r['engagement_rate']}%)" for r in scored[:3]],
        "low_content": [f"#{r['id']} {r['platform']} {r['title'][:40]} (ER {r['engagement_rate']}%)" for r in scored[-3:]] if len(scored) > 3 else [],
        "hook_patterns": [r["hook"][:60] for r in scored[:2] if r.get("hook")],
        "caption_patterns": [],
        "cta_patterns": list({r["cta"] for r in scored[:3] if r.get("cta")}),
        "topics": [],
        "best_posting_times": [f"{h:02d}시 (평균 ER {sum(v) / len(v):.2f}%, {len(v)}건)" for h, v in best_hours],
        "platform_differences": [f"{p}: 평균 ER {sum(v) / len(v):.2f}% ({len(v)}건)" for p, v in platforms.items()],
        "recommendations_for_next_content": ["성과 상위 게시물의 Hook 구조를 참고해 새 문구로 변형해 보세요."] if scored else ["아직 성과 데이터가 없습니다. 게시 후 다시 분석하세요."],
        "data_limitations": "Claude API Key 가 없어 단순 규칙으로 요약했습니다. 표본이 작으면 결론을 신뢰하지 마세요.",
    }


def ads_analysis(ads: list[dict]) -> dict:
    with_ctr = [a for a in ads if a.get("ctr") is not None]
    avg_ctr = sum(a["ctr"] for a in with_ctr) / len(with_ctr) if with_ctr else None
    with_cpa = [a for a in ads if a.get("cpa") is not None]
    avg_cpa = sum(a["cpa"] for a in with_cpa) / len(with_cpa) if with_cpa else None
    results = []
    for a in ads:
        findings = []
        verdict = "watch"
        if (a.get("impressions") or 0) < 1000:
            verdict = "insufficient_data"
            findings.append("노출 1,000 미만 — 판단 보류")
        else:
            good = bad = 0
            if avg_ctr and a.get("ctr") is not None:
                if a["ctr"] >= avg_ctr * 1.2:
                    findings.append("CTR 높음"); good += 1
                elif a["ctr"] <= avg_ctr * 0.8:
                    findings.append("CTR 낮음"); bad += 1
            if avg_cpa and a.get("cpa") is not None:
                if a["cpa"] <= avg_cpa * 0.8:
                    findings.append("CPA 낮음"); good += 1
                elif a["cpa"] >= avg_cpa * 1.2:
                    findings.append("CPA 높음"); bad += 1
            verdict = "good" if good > bad else "poor" if bad > good else "watch"
        rec = {"good": "성과 양호 — 유지", "poor": "소재 교체 검토", "watch": "추가 관찰", "insufficient_data": "데이터 더 필요"}[verdict]
        results.append({"ad_id": a["ad_id"], "name": a["name"], "verdict": verdict, "findings": findings, "recommendation": rec})
    return {
        "summary": f"[MOCK AI] 광고 {len(ads)}개를 평균 CTR/CPA 대비로 비교했습니다." + (" (mock 데이터)" if any(a.get("mock_data") for a in ads) else ""),
        "ads": results,
        "proposed_actions": [],
        "creative_directions": ["성과 양호 광고의 메시지 구조를 참고해 새 Hook 으로 변형"],
        "data_limitations": "규칙 기반 비교입니다. 전환 수가 적으면 CPA 비교는 불안정합니다.",
    }


def ad_creatives(brand: Any, count: int, lang: str) -> list[dict]:
    t = _tpl(lang)
    b = getattr(brand, "brand_name", "Brand") or "Brand"
    p = (getattr(brand, "main_products", "") or b)[:40]
    tgt = (getattr(brand, "target_customer", "") or "customers")[:40]
    return [
        {
            "hook": "[MOCK AI] " + t["hook"][i % len(t["hook"])].format(p=p, t=tgt),
            "primary_text": t["caption"].format(b=b, p=p, t=tgt, angle=t["angles"][i % len(t["angles"])]),
            "headline": f"{p}",
            "description": t["ad"].format(p=p, t=tgt),
            "cta": t["cta"][i % len(t["cta"])],
            "video_idea": "\n".join(s.format(h="hook", p=p) for s in t["script"]),
            "image_idea": t["media"],
            "target_message": tgt,
            "rationale": "[MOCK AI] 템플릿 기반 광고안",
        }
        for i in range(count)
    ]


def competitor_analysis(observations: list[dict]) -> dict:
    formats = defaultdict(int)
    for o in observations:
        if o.get("content_format"):
            formats[o["content_format"]] += 1
    return {
        "summary": f"[MOCK AI] 경쟁사 관찰 기록 {len(observations)}건을 정리했습니다.",
        "competitor_patterns": [f"{k}: {v}건" for k, v in formats.items()],
        "gaps_and_opportunities": ["경쟁사가 다루지 않는 주제(사용 비하인드, 고객 질문 답변)를 시도해 보세요."],
        "differentiation_ideas": ["브랜드 가치를 보여주는 제작 과정 콘텐츠", "실제 고객 질문에 답하는 시리즈"],
        "avoid": ["경쟁사 문구/디자인 그대로 복제"],
    }


def strategy(brand: Any) -> dict:
    return {
        "summary": f"[MOCK AI] {getattr(brand, 'brand_name', '')} 기본 콘텐츠 전략",
        "content_pillars": ["교육/정보", "제품 사용 장면", "고객 후기", "비하인드"],
        "weekly_plan": ["월: 정보성", "수: 제품 데모", "금: 후기", "일: 비하인드"],
        "platform_strategy": ["Instagram: 저장 유도형 캐러셀 + Reel", "TikTok: 첫 3초 Hook 이 강한 숏폼", "X: 짧은 팁 + Thread"],
        "kpis_to_watch": ["저장 수", "조회 수", "참여율", "링크 클릭"],
    }


def report_insights(stats: dict) -> dict:
    return {
        "insights": ["[MOCK AI] Claude API Key 를 넣으면 AI 인사이트가 생성됩니다."],
        "tomorrow_plan": ["승인 대기 콘텐츠 검토", "성과 상위 Hook 패턴 재활용"],
        "best_patterns": [],
        "worst_patterns": [],
        "ideas_to_test": ["Hook A/B 테스트", "게시 시간 변경 테스트"],
    }
