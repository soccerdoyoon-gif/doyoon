"""FastAPI 진입점: uvicorn app.main:app (backend 폴더에서 실행)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import abtests, ads, analytics, brand, calendar, chat, competitors, content, dashboard, logs, oauth, reports, settings, setup, system
from app.core.config import PROJECT_ROOT, get_settings
from app.core.database import init_db
from app.core.logging import get_logger, setup_logging
from app.scheduler.runner import shutdown_scheduler, start_scheduler

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    s = get_settings()
    log = get_logger("main")
    log.info(f"starting — DRY_RUN={s.dry_run}, AI={'claude' if s.ai_enabled else 'mock'}")
    if not s.dry_run:
        log.warning("DRY_RUN=false: 승인된 콘텐츠가 실제 SNS 에 게시됩니다.")
    start_scheduler()
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in s.cors_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for r in (system, setup, brand, content, calendar, dashboard, analytics, ads, abtests, competitors, chat, reports, logs, settings, oauth):
        app.include_router(r.router)

    media_dir = s.data_dir / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media_dir), name="media")

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse({"detail": "Not Found"}, status_code=404)
            candidate = (FRONTEND_DIST / full_path).resolve()
            if full_path and candidate.is_file() and FRONTEND_DIST.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")
    else:

        @app.get("/", include_in_schema=False)
        def root():
            return {"message": "API 실행 중. 대시보드는 frontend 를 빌드하거나 http://localhost:5173 (npm run dev) 에서 여세요.", "docs": "/docs"}

    return app


app = create_app()
