"""Daily / Weekly 리포트 생성 → DB + data/reports/*.md 저장 → 설정된 채널로 전송."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import mock_ai
from app.ai.client import AIError, get_ai
from app.ai.prompts import COMMON_RULES, as_json, brand_context, language_guide
from app.ai.schemas import REPORT_INSIGHTS
from app.analytics.stats import ads_by_ad, ads_summary, content_performance, engagement_total, platform_summary, rank_content
from app.core.config import get_settings
from app.core.timeutil import local_tz, to_local, utcnow
from app.models import BrandProfile, ContentItem, Insight, Report
from app.services.app_settings import get_setting
from app.services.events import log_event
from app.services.notifiers import dispatch

PLATFORM_LABEL = {"instagram": "Instagram", "tiktok": "TikTok", "x": "X", "facebook": "Facebook"}


def _utc_range(start_day: date, end_day: date) -> tuple[datetime, datetime]:
    tz = local_tz()
    s = datetime.combine(start_day, time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    e = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=tz).astimezone(timezone.utc).replace(tzinfo=None)
    return s, e


def _fmt(v, nd=0, suffix="") -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float) and nd:
        return f"{v:,.{nd}f}{suffix}"
    return f"{v:,.0f}{suffix}" if isinstance(v, (int, float)) else str(v)


def _ai_insights(db: Session, stats: dict, kind: str) -> tuple[dict, str]:
    ai = get_ai()
    brand = db.query(BrandProfile).first()
    if ai.is_available():
        try:
            data = ai.generate_json(
                f"{kind}_report",
                "당신은 SNS 마케팅 매니저입니다. 주어진 수치만 근거로 간결한 인사이트와 계획을 작성하세요.\n" + COMMON_RULES
                + "\n" + language_guide(brand.language if brand else "ko"),
                f"{brand_context(brand)}\n\n<stats>\n{as_json(stats)}\n</stats>\n"
                + ("오늘 인사이트 3-5개와 내일 계획 3-5개를 작성하세요." if kind == "daily"
                   else "이번 주 가장 좋았던 콘텐츠 패턴, 가장 좋지 않았던 패턴, 다음 주 테스트할 아이디어를 작성하세요."),
                REPORT_INSIGHTS,
            )
            return data, "ai"
        except AIError as exc:
            log_event("api_error", f"리포트 AI 인사이트 실패: {exc}", level="WARNING", db=db)
    return mock_ai.report_insights(stats), "mock_ai"


def _content_lines(rows: list[dict]) -> list[str]:
    return [
        f"- #{r['id']} [{PLATFORM_LABEL.get(r['platform'], r['platform'])}] {r['title'][:50]} — ER {_fmt(r['engagement_rate'], 2, '%')}, "
        f"조회 {_fmt(r['views'])}, 좋아요 {_fmt(r['likes'])}" + (" (mock)" if r.get("data_source") == "mock" else "")
        for r in rows
    ] or ["- 데이터 없음"]


def _save(db: Session, rtype: str, start: date, end: date, md: str, data: dict) -> Report:
    s, e = _utc_range(start, end)
    folder = get_settings().data_dir / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{rtype}-{start.isoformat()}{'' if start == end else '_' + end.isoformat()}.md"
    path.write_text(md, encoding="utf-8")
    rep = Report(report_type=rtype, period_start=s, period_end=e, content_md=md, data=data, file_path=str(path))
    db.add(rep)
    db.commit()
    channels = (get_setting(db, "reports") or {}).get("notify_channels", ["file"])
    data["delivery"] = dispatch(channels, f"{rtype.upper()} REPORT {start.isoformat()}", md)
    log_event("system", f"{rtype} 리포트 생성: {path.name}", {"delivery": data["delivery"]}, db=db)
    db.commit()
    return rep


def build_daily_report(db: Session, day: date | None = None) -> Report:
    day = day or to_local(utcnow()).date()
    s, e = _utc_range(day, day)
    today_rows = content_performance(db, s, e)
    week_rows = content_performance(db, s - timedelta(days=6), e)
    best, worst = rank_content(week_rows, 3)
    counts = dict(
        db.execute(
            select(ContentItem.status, func.count()).where(
                ((ContentItem.scheduled_at >= s) & (ContentItem.scheduled_at < e))
                | ((ContentItem.published_at >= s) & (ContentItem.published_at < e))
            ).group_by(ContentItem.status)
        ).all()
    )
    pending_review = db.scalar(select(func.count()).select_from(ContentItem).where(ContentItem.status == "READY_FOR_REVIEW"))
    ts, te = _utc_range(day + timedelta(days=1), day + timedelta(days=1))
    tomorrow = db.scalars(select(ContentItem).where(ContentItem.status == "SCHEDULED", ContentItem.scheduled_at >= ts, ContentItem.scheduled_at < te)).all()
    plat = platform_summary(today_rows)
    ads_t = ads_summary(db, day, day)
    per_ad = ads_by_ad(db, day, day)
    stats = {"date": day.isoformat(), "status_counts": counts, "pending_review": pending_review, "platforms": plat,
             "ads": ads_t, "ads_by_ad": per_ad[:10], "best": best, "worst": worst, "tomorrow_scheduled": len(tomorrow)}
    ai_data, source = _ai_insights(db, stats, "daily")

    md = [f"# DAILY REPORT — {day.isoformat()}", "", "## TODAY",
          f"- 게시 완료: {counts.get('PUBLISHED', 0)}", f"- 게시 실패: {counts.get('FAILED', 0)}",
          f"- 예약 대기: {counts.get('SCHEDULED', 0)}", f"- 승인 대기(전체): {pending_review}", ""]
    for p in ("instagram", "tiktok", "x"):
        sm = plat.get(p)
        md.append(f"## {PLATFORM_LABEL[p]}")
        if sm:
            md.append(f"- 게시 {sm['posts']}개 · 노출 {_fmt(sm['impressions'])} · 조회 {_fmt(sm['views'])} · 좋아요 {_fmt(sm['likes'])} · "
                      f"댓글 {_fmt(sm['comments'])} · 공유 {_fmt(sm['shares'])} · 평균 ER {_fmt(sm['avg_engagement_rate'], 2, '%')}"
                      + (" (mock 데이터)" if sm["mock_data"] else ""))
        else:
            md.append("- 오늘 게시물 없음")
        md.append("")
    md += ["## Ads", f"- 지출 {_fmt(ads_t['spend'])} · 클릭 {_fmt(ads_t['clicks'])} · CTR {_fmt(ads_t['ctr'], 2, '%')} · CPC {_fmt(ads_t['cpc'], 1)} · "
           f"CPA {_fmt(ads_t['cpa'], 1)} · ROAS {_fmt(ads_t['roas'], 2)}" + (" (mock 데이터)" if ads_t["mock_data"] else ""), "",
           "## BEST CONTENT (최근 7일)", *_content_lines(best), "", "## WORST CONTENT (최근 7일)", *_content_lines(worst), "",
           "## AD PERFORMANCE"]
    md += [f"- {a['name']}: 지출 {_fmt(a['spend'])}, CTR {_fmt(a['ctr'], 2, '%')}, CPA {_fmt(a['cpa'], 1)}, ROAS {_fmt(a['roas'], 2)}" for a in per_ad] or ["- 데이터 없음"]
    md += ["", f"## AI INSIGHTS ({source})", *[f"- {x}" for x in ai_data.get("insights", [])], "",
           "## TOMORROW PLAN", f"- 예약된 게시물 {len(tomorrow)}개",
           *[f"  - {to_local(t.scheduled_at).strftime('%H:%M')} [{PLATFORM_LABEL.get(t.platform, t.platform)}] {t.title[:50]}" for t in tomorrow],
           *[f"- {x}" for x in ai_data.get("tomorrow_plan", [])], ""]
    stats["ai"] = ai_data
    return _save(db, "daily", day, day, "\n".join(md), stats)


def build_weekly_report(db: Session, end_day: date | None = None) -> Report:
    end_day = end_day or to_local(utcnow()).date()
    start_day = end_day - timedelta(days=6)
    s, e = _utc_range(start_day, end_day)
    rows = content_performance(db, s, e)
    best, worst = rank_content(rows, 3)
    plat = platform_summary(rows)

    def total(k):
        vals = [r[k] for r in rows if r[k] is not None]
        return sum(vals) if vals else None

    engagement_vals = [engagement_total(r) for r in rows]
    engagement_vals = [v for v in engagement_vals if v is not None]
    ads_t = ads_summary(db, start_day, end_day)
    latest = db.scalars(select(Insight).where(Insight.kind == "content").order_by(Insight.id.desc()).limit(1)).first()
    stats = {
        "period": f"{start_day.isoformat()} ~ {end_day.isoformat()}",
        "total_posts": len(rows),
        "total_impressions": total("impressions"),
        "total_views": total("views"),
        "total_engagement": sum(engagement_vals) if engagement_vals else None,
        "follower_growth": total("followers_gained"),
        "platforms": plat,
        "ads": ads_t,
        "best": best,
        "worst": worst,
        "latest_content_analysis": latest.data if latest else None,
    }
    ai_data, source = _ai_insights(db, stats, "weekly")
    md = [f"# WEEKLY REPORT — {stats['period']}", "", "## Content",
          f"- Total posts: {stats['total_posts']}", f"- Total impressions: {_fmt(stats['total_impressions'])}",
          f"- Total views: {_fmt(stats['total_views'])}", f"- Total engagement: {_fmt(stats['total_engagement'])}",
          f"- Follower growth: {_fmt(stats['follower_growth'])}", "",
          "## Advertising", f"- Spend: {_fmt(ads_t['spend'])}", f"- Clicks: {_fmt(ads_t['clicks'])}",
          f"- Conversions: {_fmt(ads_t['conversions'])}", f"- CPA: {_fmt(ads_t['cpa'], 1)}", f"- ROAS: {_fmt(ads_t['roas'], 2)}",
          *(["- (mock 데이터 포함)"] if ads_t["mock_data"] else []), "",
          "## BEST CONTENT", *_content_lines(best), "", "## WORST CONTENT", *_content_lines(worst), "",
          f"## 이번 주 가장 좋았던 콘텐츠 패턴 ({source})", *([f"- {x}" for x in ai_data.get("best_patterns", [])] or ["- 데이터 부족"]), "",
          "## 가장 좋지 않았던 콘텐츠 패턴", *([f"- {x}" for x in ai_data.get("worst_patterns", [])] or ["- 데이터 부족"]), "",
          "## 다음 주 테스트할 아이디어", *[f"- {x}" for x in ai_data.get("ideas_to_test", [])], ""]
    stats["ai"] = ai_data
    return _save(db, "weekly", start_day, end_day, "\n".join(md), stats)
