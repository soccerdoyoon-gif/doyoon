"""APScheduler 설정. 시간은 TIMEZONE(.env) 기준.

매분      : 예약 게시 실행 (재시도 포함)
매시 10분 : 게시물 성과 수집
06:00     : 광고 데이터 수집 → 06:20 AI 광고 분석 (광고 연결 시)
06:30     : AI 성과 분석 (다음 콘텐츠 생성에 반영)
07:00     : 콘텐츠 후보 생성 (설정에서 시간 변경 가능)
21:00     : Daily Report
월 08:00  : Weekly Report
"""
from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import get_settings
from app.core.logging import get_logger
from app.scheduler import jobs

logger = get_logger("scheduler")
_scheduler: BackgroundScheduler | None = None


def build_scheduler(gen_hour: int = 7, gen_minute: int = 0) -> BackgroundScheduler:
    tz = get_settings().timezone
    sched = BackgroundScheduler(timezone=tz, job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300})
    sched.add_job(jobs.job_publish_due, IntervalTrigger(minutes=1), id="publish_due")
    sched.add_job(jobs.job_collect_metrics, CronTrigger(minute=10, timezone=tz), id="collect_metrics")
    sched.add_job(jobs.job_sync_ads, CronTrigger(hour=6, minute=0, timezone=tz), id="sync_ads")
    sched.add_job(jobs.job_ads_analysis, CronTrigger(hour=6, minute=20, timezone=tz), id="ads_analysis")
    sched.add_job(jobs.job_daily_analysis, CronTrigger(hour=6, minute=30, timezone=tz), id="daily_analysis")
    sched.add_job(jobs.job_daily_generation, CronTrigger(hour=gen_hour, minute=gen_minute, timezone=tz), id="daily_generation")
    sched.add_job(jobs.job_daily_report, CronTrigger(hour=21, minute=0, timezone=tz), id="daily_report")
    sched.add_job(jobs.job_refresh_tokens, CronTrigger(day_of_week="sun", hour=3, minute=0, timezone=tz), id="refresh_tokens")
    sched.add_job(jobs.job_weekly_report, CronTrigger(day_of_week="mon", hour=8, minute=0, timezone=tz), id="weekly_report")
    return sched


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler
    if not get_settings().scheduler_enabled or _scheduler is not None:
        return _scheduler
    from app.core.database import SessionLocal
    from app.services.app_settings import get_setting

    db = SessionLocal()
    try:
        gen = get_setting(db, "generation")
    finally:
        db.close()
    _scheduler = build_scheduler(int(gen.get("hour", 7)), int(gen.get("minute", 0)))
    _scheduler.start()
    logger.info("scheduler started")
    return _scheduler


def reschedule_generation(hour: int, minute: int) -> None:
    if _scheduler is not None:
        _scheduler.reschedule_job("daily_generation", trigger=CronTrigger(hour=hour, minute=minute, timezone=get_settings().timezone))


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def job_status() -> list[dict]:
    if _scheduler is None:
        return []
    return [
        {"id": j.id, "next_run": j.next_run_time.isoformat() if j.next_run_time else None}
        for j in _scheduler.get_jobs()
    ]
