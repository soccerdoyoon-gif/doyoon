"""AI 분석: 콘텐츠 성과 / 광고 성과 / 광고 소재 / 경쟁사 / 전략 / A/B 해석.

분석 결과는 Insight 로 저장되고, 다음 콘텐츠 생성 시 자동으로 프롬프트에 포함됩니다.
(콘텐츠 생성 → 게시 → 성과 측정 → AI 분석 → 다음 콘텐츠 개선 루프)
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import mock_ai
from app.ai.client import AIError, get_ai
from app.ai.prompts import COMMON_RULES, as_json, brand_context, language_guide
from app.ai.schemas import (
    AB_INTERPRETATION,
    AD_CREATIVES,
    ADS_ANALYSIS,
    COMPETITOR_ANALYSIS,
    CONTENT_ANALYSIS,
    STRATEGY,
)
from app.analytics.abtest import ABResult
from app.analytics.stats import ads_by_ad, ads_summary, content_performance, platform_summary
from app.core.timeutil import utcnow
from app.models import AdCreativeDraft, ABTest, BrandProfile, Competitor, Insight
from app.services.events import log_event

ANALYST_SYSTEM = (
    "당신은 데이터 기반 SNS/퍼포먼스 마케팅 분석가입니다. 주어진 데이터만 근거로 분석하고, "
    "표본이 작거나 데이터가 없으면 그렇다고 분명히 말하세요. 성급한 결론을 내리지 마세요.\n" + COMMON_RULES
)


def _brand(db: Session) -> BrandProfile | None:
    return db.query(BrandProfile).first()


def _save(db: Session, kind: str, data: dict, source: str, start=None, end=None) -> Insight:
    ins = Insight(kind=kind, summary=data.get("summary", ""), data=data, source=source, period_start=start, period_end=end)
    db.add(ins)
    log_event("ai_generation", f"AI 분석 저장: {kind} ({source})", db=db)
    db.commit()
    return ins


def _run(purpose: str, prompt: str, schema: dict, fallback, system: str = ANALYST_SYSTEM) -> tuple[dict, str]:
    ai = get_ai()
    if ai.is_available():
        try:
            return ai.generate_json(purpose, system, prompt, schema), "ai"
        except AIError as exc:
            log_event("api_error", f"AI 분석 실패 ({purpose}) → 규칙 기반 대체: {exc}", level="WARNING")
    return fallback(), "mock_ai"


def analyze_content(db: Session, days: int = 14) -> Insight:
    end = utcnow()
    start = end - timedelta(days=days)
    rows = content_performance(db, start, end)
    brand = _brand(db)
    prompt = (
        f"{brand_context(brand)}\n\n<platform_summary>\n{as_json(platform_summary(rows))}\n</platform_summary>\n"
        f"<posts>\n{as_json(rows)}\n</posts>\n\n"
        f"최근 {days}일 게시물 성과를 분석하세요: 성과 좋은/낮은 콘텐츠, 좋은 Hook·Caption·CTA 패턴, 좋은 주제, "
        "좋은 게시 시간(현지 시각), 플랫폼별 차이, 다음 콘텐츠에 반영할 구체적 개선점. "
        "지표가 null 인 것은 플랫폼이 제공하지 않은 값입니다. data_limitations 에 표본 크기와 한계를 적으세요."
    )
    data, source = _run("content_analysis", prompt, CONTENT_ANALYSIS, lambda: mock_ai.content_analysis(rows))
    data["post_count"] = len(rows)
    return _save(db, "content", data, source, start, end)


def analyze_ads(db: Session, days: int = 7, propose_actions: bool = True) -> Insight:
    from app.services.ads_service import local_today, request_action

    until = local_today()
    since = until - timedelta(days=days - 1)
    per_ad = ads_by_ad(db, since, until)
    totals = ads_summary(db, since, until)
    from app.services.app_settings import get_setting

    guard = get_setting(db, "budget_guard")
    from app.models import AdEntity

    budgets = [
        {"level": e.level, "id": e.external_id, "name": e.name, "status": e.status, "daily_budget": e.daily_budget}
        for e in db.scalars(select(AdEntity).where(AdEntity.daily_budget.is_not(None))).all()
    ]
    prompt = (
        f"{brand_context(_brand(db))}\n\n<totals>\n{as_json(totals)}\n</totals>\n<ads>\n{as_json(per_ad)}\n</ads>\n"
        f"<budgets>\n{as_json(budgets)}\n</budgets>\n<budget_guard>\n{as_json(guard)}\n</budget_guard>\n\n"
        f"최근 {days}일 광고 성과를 광고별로 평가하세요 (예: 'CTR 높음, CPA 낮음 → 성과 양호', 'CTR 낮음, CPA 높음 → 소재 교체 검토'). "
        "노출 1,000 미만 또는 전환이 매우 적은 광고는 insufficient_data 로 두세요. "
        "proposed_actions 는 꼭 필요한 경우에만 제안하고, budget_change 는 Budget Guard 의 max_budget_change_percent 이내로 제안하세요. "
        "pause/resume 은 사용자가 승인해야 실행됩니다. 광고 삭제·캠페인 생성·결제 변경은 제안하지 마세요. "
        "pause/resume 일 때 new_daily_budget 는 0 으로 두세요."
    )
    data, source = _run("ads_analysis", prompt, ADS_ANALYSIS, lambda: mock_ai.ads_analysis(per_ad))
    data["totals"] = totals
    created_actions = []
    if propose_actions:
        for p in data.get("proposed_actions", [])[:5]:
            try:
                act = request_action(
                    db,
                    p["action_type"],
                    p.get("target_level", "adset"),
                    p["target_id"],
                    new_budget=p.get("new_daily_budget") if p["action_type"] == "budget_change" else None,
                    reason=f"[AI 제안] {p.get('reason', '')}",
                    requested_by="ai",
                )
                created_actions.append(act.id)
            except Exception as exc:  # 제안 하나가 잘못돼도 분석은 저장
                log_event("api_error", f"AI 광고 제안 등록 실패: {exc}", level="WARNING", db=db)
    data["pending_action_ids"] = created_actions
    return _save(db, "ads", data, source)


def generate_ad_creatives(db: Session, count: int = 3, focus: str = "") -> list[AdCreativeDraft]:
    from app.services.ads_service import local_today

    brand = _brand(db)
    lang = brand.language if brand else "ko"
    until = local_today()
    per_ad = ads_by_ad(db, until - timedelta(days=13), until)
    prompt = (
        f"{brand_context(brand)}\n\n<ad_performance>\n{as_json(per_ad)}\n</ad_performance>\n"
        + (f"요청/초점: {focus}\n" if focus else "")
        + f"새 광고안 {count}개를 만드세요. 성과 좋은 광고의 특징(메시지 구조, 소구점)은 참고하되 문구를 그대로 복사하지 마세요. "
        "각 안: hook, primary_text, headline(짧게), description, cta, video_idea, image_idea, target_message, rationale(근거).\n"
        + language_guide(lang)
    )
    data, source = _run(
        "ad_creative_generation",
        prompt,
        AD_CREATIVES,
        lambda: {"creatives": mock_ai.ad_creatives(brand, count, lang)},
        system="당신은 퍼포먼스 광고 카피라이터입니다.\n" + COMMON_RULES,
    )
    out = []
    based_on = [a["ad_id"] for a in per_ad[:5]]
    for c in data.get("creatives", [])[:count]:
        d = AdCreativeDraft(**{k: c.get(k, "") for k in ("hook", "primary_text", "headline", "description", "cta", "video_idea", "image_idea", "target_message", "rationale")},
                            based_on=based_on, language=lang, source=source)
        db.add(d)
        out.append(d)
    log_event("ai_generation", f"광고 소재 {len(out)}개 생성 ({source})", db=db)
    db.commit()
    return out


def analyze_competitors(db: Session) -> Insight:
    brand = _brand(db)
    comps = db.scalars(select(Competitor)).all()
    obs = [
        {
            "competitor": c.name,
            "platform": c.platform,
            "topic": o.topic,
            "content_format": o.content_format,
            "hook_pattern": o.hook_pattern,
            "public_reaction": o.public_reaction,
            "posts_per_week": o.posts_per_week,
            "notes": o.notes,
        }
        for c in comps
        for o in c.observations
    ]
    prompt = (
        f"{brand_context(brand)}\n\n<competitor_observations>\n{as_json(obs)}\n</competitor_observations>\n"
        "사용자가 공개 페이지에서 직접 확인해 입력한 경쟁사 관찰 기록입니다. 경쟁사의 주제/형식/업로드 빈도/반응/Hook 패턴을 정리하고, "
        "우리 브랜드가 '복제하지 않고' 차별화할 수 있는 아이디어를 제안하세요."
    )
    data, source = _run("competitor_analysis", prompt, COMPETITOR_ANALYSIS, lambda: mock_ai.competitor_analysis(obs))
    return _save(db, "competitor", data, source)


def generate_strategy(db: Session) -> Insight:
    brand = _brand(db)
    if brand is None:
        raise ValueError("먼저 브랜드 프로필을 등록하세요.")
    latest = db.scalars(select(Insight).where(Insight.kind == "content").order_by(Insight.id.desc()).limit(1)).first()
    prompt = (
        f"{brand_context(brand)}\n\n<latest_performance_analysis>\n{as_json(latest.data if latest else {})}\n</latest_performance_analysis>\n"
        "브랜드의 main_goal 에 맞춘 SNS 콘텐츠 전략을 세우세요: 콘텐츠 기둥(pillars), 주간 계획, 플랫폼별 전략, 지켜볼 KPI."
    )
    data, source = _run("content_strategy", prompt, STRATEGY, lambda: mock_ai.strategy(brand))
    return _save(db, "strategy", data, source)


def interpret_ab_test(db: Session, test: ABTest, result: ABResult) -> dict:
    prompt = (
        f"<ab_test>\n{as_json({'name': test.name, 'variable': test.variable, 'metric': test.metric, 'hypothesis': test.hypothesis, 'variants': [{'label': v.label, 'description': v.description, 'impressions': v.impressions, 'clicks': v.clicks, 'engagements': v.engagements, 'conversions': v.conversions} for v in test.variants]})}\n</ab_test>\n"
        f"<statistical_result>\n{as_json(result.to_dict())}\n</statistical_result>\n"
        "통계 결과의 verdict 를 반드시 따르세요. verdict 가 insufficient_data 또는 no_significant_difference 이면 승자를 선언하지 말고, "
        "필요한 추가 표본과 다음 단계를 제안하세요."
    )
    data, _ = _run(
        "ab_test_interpretation",
        prompt,
        AB_INTERPRETATION,
        lambda: {"interpretation": result.message, "next_steps": ["표본이 충분해질 때까지 테스트 유지"] if result.verdict != "significant" else ["승리 변형을 기본으로 적용하고 다음 변수 테스트"]},
    )
    return data
