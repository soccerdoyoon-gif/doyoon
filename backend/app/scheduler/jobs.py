"""자동화 작업 목록. 각 작업은 독립 DB 세션을 사용하고, 실패해도 다른 작업에 영향이 없습니다."""
from __future__ import annotations

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.services.app_settings import get_setting
from app.services.events import log_event

logger = get_logger("scheduler")


def _run(name: str, fn) -> None:
    db = SessionLocal()
    try:
        fn(db)
    except Exception as exc:
        db.rollback()
        logger.exception(f"job {name} failed")
        log_event("system", f"스케줄 작업 실패: {name} — {type(exc).__name__}: {exc}", level="ERROR")
    finally:
        db.close()


def job_publish_due() -> None:
    from app.services.publisher import publish_due

    _run("publish_due", publish_due)


def job_collect_metrics() -> None:
    from app.services.metrics_collector import collect_metrics

    _run("collect_metrics", collect_metrics)


def job_daily_generation() -> None:
    from app.ai.content_generator import generate_content

    def fn(db):
        if not get_setting(db, "setup_completed"):
            return
        generate_content(db)

    _run("daily_generation", fn)


def job_daily_analysis() -> None:
    from app.agents.posting_times import learn
    from app.ai.analyzer import analyze_content

    def fn(db):
        analyze_content(db)
        learn(db)  # JST 게시 시간 재학습

    _run("daily_analysis", fn)


def job_sync_ads() -> None:
    from app.services.ads_service import sync_ads

    def fn(db):
        if get_setting(db, "ads_enabled"):
            sync_ads(db)

    _run("sync_ads", fn)


def job_ads_analysis() -> None:
    from app.ai.analyzer import analyze_ads

    def fn(db):
        if get_setting(db, "ads_enabled"):
            analyze_ads(db)

    _run("ads_analysis", fn)


def job_daily_report() -> None:
    from app.services.report_service import build_daily_report

    _run("daily_report", build_daily_report)


def job_weekly_report() -> None:
    from app.services.report_service import build_weekly_report

    _run("weekly_report", build_weekly_report)


def job_refresh_tokens() -> None:
    from app.connectors.instagram import InstagramConnector

    def fn(db):
        ig = InstagramConnector()
        if ig.is_configured():
            ig.refresh_token()
            log_event("system", "Instagram 장기 토큰 갱신", db=db)
            db.commit()

    _run("refresh_tokens", fn)


JOBS = {
    "refresh_tokens": job_refresh_tokens,
    "publish_due": job_publish_due,
    "collect_metrics": job_collect_metrics,
    "daily_generation": job_daily_generation,
    "daily_analysis": job_daily_analysis,
    "sync_ads": job_sync_ads,
    "ads_analysis": job_ads_analysis,
    "daily_report": job_daily_report,
    "weekly_report": job_weekly_report,
}
