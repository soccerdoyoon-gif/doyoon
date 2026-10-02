"""AI Marketing Manager — 자연어 질문에 실제 DB 데이터를 조회해서 답합니다.

Claude 가 아래 도구(tool)로 DB 를 조회합니다. 데이터가 없으면 없다고 답하도록 지시합니다.
도구는 읽기 전용이며, 예외적으로 create_content_drafts 는 '승인 대기' 초안만 만듭니다 (게시 X).
"""
from __future__ import annotations

import json
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.client import AIError, get_ai
from app.ai.prompts import brand_context
from app.analytics.stats import ads_by_ad, ads_summary, content_performance, platform_summary, rank_content
from app.core.timeutil import to_local, utcnow
from app.models import ABTest, BrandProfile, ChatMessage, ContentItem, Insight, PendingAction
from app.services.app_settings import get_setting
from app.services.events import log_event

PLATFORM_ENUM = ["all", "instagram", "facebook", "tiktok", "x"]
_BACKGROUND = True  # 테스트에서는 False (동기 실행)


def _tool(name: str, description: str, props: dict) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {"type": "object", "properties": props, "required": list(props), "additionalProperties": False},
    }


TOOLS = [
    _tool("get_content_performance", "기간 내 게시된 콘텐츠의 성과(플랫폼별 합계, 상위/하위 게시물, 게시물 목록)를 조회합니다.",
          {"days": {"type": "integer", "description": "최근 며칠 (1-90)"}, "platform": {"type": "string", "enum": PLATFORM_ENUM}}),
    _tool("compare_periods", "최근 N일과 그 이전 N일의 플랫폼별 성과를 비교합니다 (하락/상승 원인 분석용).",
          {"days": {"type": "integer"}, "platform": {"type": "string", "enum": PLATFORM_ENUM}}),
    _tool("get_ads_performance", "광고 전체 합계와 광고별 성과(spend, CTR, CPC, CPA, ROAS)를 조회합니다.",
          {"days": {"type": "integer"}}),
    _tool("get_content_queue", "승인 대기/예약/실패 콘텐츠와 앞으로 N일 게시 일정을 조회합니다.",
          {"days_ahead": {"type": "integer"}}),
    _tool("get_latest_insights", "가장 최근 AI 분석 결과(content/ads/competitor/strategy)를 조회합니다.",
          {"kind": {"type": "string", "enum": ["content", "ads", "competitor", "strategy"]}}),
    _tool("get_settings_and_budget_guard", "브랜드 프로필, Budget Guard 설정, 대기 중인 광고 작업, A/B 테스트 목록을 조회합니다.", {}),
    _tool("create_content_package",
          "일본 시장용 콘텐츠 패키지 생성 파이프라인을 백그라운드로 시작합니다 (트렌드 분석 → 아이디어 → 일본어 Hook/카피 → 영상 스크립트 → "
          "이미지/영상 → 자막 → Caption/Hashtag → Brand Guardian → 승인 대기). 게시는 하지 않습니다. "
          "사용자가 콘텐츠/영상/게시물 생성을 요청한 경우에만 사용하세요. 예: '오늘 일본 TikTok용 영상 3개' → platforms=['tiktok'], idea_count=3, with_video=true.",
          {"idea_count": {"type": "integer", "description": "아이디어 개수 1-10. 아이디어 1개마다 지정한 플랫폼별로 1개씩 생성됨. 플랫폼 지정 없이 '콘텐츠 7개'라고 하면 7 ÷ 사용 중인 플랫폼 수(올림)"},
           "platforms": {"type": "array", "items": {"type": "string", "enum": ["instagram", "facebook", "tiktok", "x"]}},
           "theme": {"type": "string", "description": "주제/요청. 없으면 빈 문자열"},
           "with_video": {"type": "boolean"},
           "language": {"type": "string", "enum": ["ja", "ko", "en"], "description": "콘텐츠 언어. 사용자가 명시적으로 요청하지 않으면 ja"}}),
    _tool("get_trends", "가장 최근 일본 시장 트렌드 조사 결과를 조회합니다 (TikTok/Reels/X/Shorts).", {}),
]


def _clamp(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def run_tool(db: Session, name: str, args: dict) -> Any:
    now = utcnow()
    if name == "get_content_performance":
        days = _clamp(args.get("days"), 1, 90, 7)
        rows = content_performance(db, now - timedelta(days=days), now, args.get("platform"))
        best, worst = rank_content(rows, 5)
        return {"days": days, "post_count": len(rows), "by_platform": platform_summary(rows), "best": best, "worst": worst,
                "posts": rows[:60], "note": "null = 플랫폼 미제공 지표. data_source=mock 은 테스트 데이터"}
    if name == "compare_periods":
        days = _clamp(args.get("days"), 1, 45, 7)
        cur = content_performance(db, now - timedelta(days=days), now, args.get("platform"))
        prev = content_performance(db, now - timedelta(days=2 * days), now - timedelta(days=days), args.get("platform"))
        return {"current_period": platform_summary(cur), "previous_period": platform_summary(prev),
                "current_posts": cur[:40], "previous_posts": prev[:40]}
    if name == "get_ads_performance":
        days = _clamp(args.get("days"), 1, 90, 7)
        until = to_local(now).date()
        since = until - timedelta(days=days - 1)
        return {"since": since, "until": until, "totals": ads_summary(db, since, until), "by_ad": ads_by_ad(db, since, until)}
    if name == "get_content_queue":
        ahead = _clamp(args.get("days_ahead"), 1, 30, 7)
        counts = dict(db.execute(select(ContentItem.status, func.count()).group_by(ContentItem.status)).all())
        upcoming = db.scalars(select(ContentItem).where(ContentItem.status == "SCHEDULED", ContentItem.scheduled_at <= now + timedelta(days=ahead)).order_by(ContentItem.scheduled_at)).all()
        failed = db.scalars(select(ContentItem).where(ContentItem.status == "FAILED").limit(20)).all()
        return {"status_counts": counts,
                "upcoming": [{"id": c.id, "platform": c.platform, "title": c.title, "scheduled_local": to_local(c.scheduled_at).strftime("%Y-%m-%d %H:%M")} for c in upcoming],
                "failed": [{"id": c.id, "platform": c.platform, "title": c.title, "error": c.last_error} for c in failed]}
    if name == "get_latest_insights":
        ins = db.scalars(select(Insight).where(Insight.kind == args.get("kind", "content")).order_by(Insight.id.desc()).limit(1)).first()
        return {"found": False} if ins is None else {"found": True, "created_at": ins.created_at, "source": ins.source, "data": ins.data}
    if name == "get_settings_and_budget_guard":
        brand = db.query(BrandProfile).first()
        pending = db.scalars(select(PendingAction).where(PendingAction.status == "PENDING")).all()
        tests = db.scalars(select(ABTest)).all()
        return {"brand": brand_context(brand), "budget_guard": get_setting(db, "budget_guard"),
                "pending_ad_actions": [{"id": p.id, "type": p.action_type, "target": p.target_name or p.target_external_id, "payload": p.payload, "reason": p.reason} for p in pending],
                "ab_tests": [{"id": t.id, "name": t.name, "status": t.status, "conclusion": t.conclusion} for t in tests]}
    if name == "create_content_package":
        from app.agents.pipeline import start_run

        params = {"idea_count": _clamp(args.get("idea_count"), 1, 10, 3), "platforms": args.get("platforms") or None,
                  "theme": args.get("theme", ""), "with_video": bool(args.get("with_video", True)), "language": args.get("language") or "ja"}
        run = start_run(db, {k: v for k, v in params.items() if v not in (None, "")}, background=_BACKGROUND)
        return {"run_id": run.id, "status": run.status, "request": params,
                "note": "백그라운드에서 생성 중. 완료되면 '승인 대기' 화면에 표시됩니다. 사용자가 승인하기 전에는 게시되지 않습니다."}
    if name == "get_trends":
        ins = db.scalars(select(Insight).where(Insight.kind == "trend").order_by(Insight.id.desc()).limit(1)).first()
        return {"found": False} if ins is None else {"found": True, "created_at": ins.created_at, "source": ins.source, "data": ins.data}
    return {"error": f"unknown tool {name}"}


SYSTEM = """당신은 일본 시장을 담당하는 이 브랜드의 AI Marketing Manager 입니다. 기본 시장은 일본, 통화는 엔(¥), 시간은 JST 입니다.
콘텐츠(캡션·카피·스크립트 등)는 기본적으로 일본어로 만들고, 한국어/영어는 사용자가 명시적으로 요청할 때만 사용하세요.
답변(설명)은 사용자가 질문한 언어로 하세요. 금액은 ¥ 로 표시하세요. 사용자의 질문에 답하기 전에 반드시 도구로 실제 DB 데이터를 조회하세요.
규칙:
- 도구 결과에 없는 수치/사실을 만들어내지 마세요. 데이터가 없으면 "데이터가 없습니다"라고 말하고 무엇이 필요한지 안내하세요.
- data_source 가 mock 이거나 source 가 mock 인 데이터는 테스트용 가짜 데이터라는 점을 답변에 밝히세요.
- 광고 예산 배분 질문에는 Budget Guard 한도를 고려한 '제안'만 하고, 실행은 사용자가 광고 메뉴에서 승인해야 한다고 안내하세요.
- 표본이 작으면 결론을 유보하세요. 원인 분석은 가설로 표현하세요.
- 사용자가 쓴 언어로, 핵심부터 간결하게 답하세요. 표나 목록을 적절히 사용하세요."""


def _n(v, suffix: str = "") -> str:
    return "N/A" if v is None else (f"{v:,}" if isinstance(v, int) else str(v)) + suffix


GEN_WORDS = ("만들어", "생성", "作って", "作成", "create", "make")
PLATFORM_WORDS = {"tiktok": ("tiktok", "틱톡", "ティックトック"), "instagram": ("instagram", "인스타", "インスタ", "reels", "릴스"),
                  "x": (" x ", "x용", "트위터", "twitter", "ツイッター", "xで"), "facebook": ("facebook", "페이스북")}


def parse_generation_request(q: str) -> dict | None:
    """Mock 모드용 간단한 명령 해석: '오늘 일본 TikTok용 영상 3개 만들어줘' 등."""
    low = f" {q.lower()} "
    if not any(w in low for w in GEN_WORDS):
        return None
    m = re.search(r"(\d+)\s*(개|個|本|つ|件)?", q)
    count = int(m.group(1)) if m else 3
    platforms = [p for p, ws in PLATFORM_WORDS.items() if any(w in low for w in ws)]
    video = any(w in low for w in ("영상", "動画", "video", "숏폼", "ショート", "릴스", "reels"))
    if video and not platforms:
        platforms = ["tiktok"]
    lang = "ko" if "한국어" in q else "en" if ("영어" in q or "english" in low) else "ja"
    return {"idea_count": max(1, min(10, count)), "platforms": platforms or None, "with_video": video or None, "language": lang}


def question_lang(q: str) -> str:
    if re.search(r"[\uAC00-\uD7AF]", q):
        return "ko"
    if re.search(r"[\u3040-\u30FF\u4E00-\u9FFF]", q):
        return "ja"
    return "en"


MOCK_TEXT = {
    "ja": {
        "started": "[MOCK AI] コンテンツパッケージの制作を開始しました（実行 #{run}）。\n- 対象: {plats}／アイデア {n}件／言語: {lang}\n"
                   "- 流れ: トレンド分析 → アイデア → 日本語フック・コピー → 動画台本 → 画像・動画・字幕 → キャプション・ハッシュタグ → Brand Guardian → 承認待ち\n"
                   "完了したら「承認待ち」画面で確認・承認してください。承認するまで投稿されません。",
        "all": "設定中のSNSすべて",
        "head": "[MOCK AI] Claude APIキーがないため、直近7日間のデータの要約のみ表示します。",
        "plat": "- {p}: 投稿 {posts}件、再生 {views}、いいね {likes}、平均ER {er}",
        "no_posts": "- 直近7日間に投稿されたコンテンツはありません。",
        "ads": "- 広告: 広告費 ¥{spend}、CTR {ctr}、CPA ¥{cpa}、ROAS {roas}",
        "no_ads": "- 広告データはありません。",
        "tail": "設定 > APIキーでClaude APIキーを入力すると、質問に合わせた分析ができます。",
    },
    "ko": {
        "started": "[MOCK AI] 콘텐츠 패키지 생성을 시작했습니다 (실행 #{run}).\n- 대상: {plats} / 아이디어 {n}개 / 언어: {lang}\n"
                   "- 순서: 트렌드 분석 → 아이디어 → 일본어 Hook·카피 → 영상 스크립트 → 이미지/영상·자막 → Caption·Hashtag → Brand Guardian → 승인 대기\n"
                   "완료되면 '승인 대기' 화면에서 확인·승인하세요. 승인 전에는 게시되지 않습니다.",
        "all": "설정된 SNS 전체",
        "head": "[MOCK AI] Claude API Key 가 없어 최근 7일 데이터 요약만 보여드립니다.",
        "plat": "- {p}: 게시 {posts}개, 조회 {views}, 좋아요 {likes}, 평균 ER {er}",
        "no_posts": "- 최근 7일 게시된 콘텐츠가 없습니다.",
        "ads": "- 광고: 지출 ¥{spend}, CTR {ctr}, CPA ¥{cpa}, ROAS {roas}",
        "no_ads": "- 광고 데이터가 없습니다.",
        "tail": "설정 > API Key 에서 Claude API Key 를 입력하면 질문에 맞춘 분석을 받을 수 있습니다.",
    },
}


def _mock_answer(db: Session, question: str) -> str:
    lang = question_lang(question)
    if lang == "en":
        lang = get_setting(db, "ui_language") or "ja"
    M = MOCK_TEXT["ko" if lang == "ko" else "ja"]
    req = parse_generation_request(question)
    if req and not req["platforms"]:  # 플랫폼 지정이 없으면 '총 개수' 로 보고 아이디어 수를 나눔
        n_platforms = max(1, sum(1 for v in get_setting(db, "platforms_enabled").values() if v))
        req["idea_count"] = max(1, -(-req["idea_count"] // n_platforms))
    if req:
        res = run_tool(db, "create_content_package", {**{k: v for k, v in req.items() if v is not None}, "theme": ""})
        return M["started"].format(run=res["run_id"], plats=", ".join(req["platforms"] or [M["all"]]), n=req["idea_count"], lang=req["language"])
    perf = run_tool(db, "get_content_performance", {"days": 7, "platform": "all"})
    ads = run_tool(db, "get_ads_performance", {"days": 7})
    lines = [M["head"], ""]
    if perf["by_platform"]:
        for p, s_ in perf["by_platform"].items():
            lines.append(M["plat"].format(p=p, posts=s_["posts"], views=_n(s_["views"]), likes=_n(s_["likes"]), er=_n(s_["avg_engagement_rate"], "%"))
                         + (" (mock)" if s_["mock_data"] else ""))
    else:
        lines.append(M["no_posts"])
    t = ads["totals"]
    if t["spend"] is not None:
        lines.append(M["ads"].format(spend=f"{t['spend']:,.0f}", ctr=_n(t["ctr"], "%"), cpa=_n(t["cpa"]), roas=_n(t["roas"])) + (" (mock)" if t["mock_data"] else ""))
    else:
        lines.append(M["no_ads"])
    lines += ["", M["tail"]]
    return "\n".join(lines)


def ask(db: Session, session_id: str, question: str, max_turns: int = 8) -> dict:
    db.add(ChatMessage(session_id=session_id, role="user", content=question))
    db.commit()
    ai = get_ai()
    tools_used: list[str] = []
    if not ai.is_available():
        answer = _mock_answer(db, question)
    else:
        history = db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.id.desc()).limit(11)).all()
        messages: list[dict] = [{"role": m.role, "content": m.content} for m in reversed(history) if m.content]
        while messages and messages[0]["role"] != "user":
            messages.pop(0)
        today = to_local(utcnow()).strftime("%Y-%m-%d (%a)")
        params = ai._base_params(16000)
        answer = ""
        try:
            for _ in range(max_turns):
                resp = ai.create("marketing_manager", system=SYSTEM + f"\n오늘(현지): {today}", tools=TOOLS, messages=messages, **params)
                messages.append({"role": "assistant", "content": resp.content})
                if resp.stop_reason != "tool_use":
                    answer = ai.text_of(resp).strip()
                    break
                results = []
                for block in resp.content:
                    if getattr(block, "type", "") != "tool_use":
                        continue
                    tools_used.append(block.name)
                    try:
                        out = run_tool(db, block.name, dict(block.input))
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(out, ensure_ascii=False, default=str)[:60000]})
                    except Exception as exc:
                        results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"도구 오류: {exc}", "is_error": True})
                messages.append({"role": "user", "content": results})
            else:
                answer = "질문이 복잡해 답변을 끝내지 못했습니다. 질문을 나눠서 다시 물어봐 주세요."
        except AIError as exc:
            answer = f"AI 호출 오류: {exc}"
    db.add(ChatMessage(session_id=session_id, role="assistant", content=answer))
    log_event("ai_generation", "AI Marketing Manager 응답", {"tools": tools_used}, db=db)
    db.commit()
    return {"answer": answer, "tools_used": tools_used, "mode": "ai" if ai.is_available() else "mock_ai"}
