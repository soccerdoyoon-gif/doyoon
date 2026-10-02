#!/usr/bin/env bash
# Docker 없이 실행 (Mac / Linux). 처음 실행 시 필요한 패키지를 자동 설치합니다.
set -e
cd "$(dirname "$0")"
if [ ! -f .env ]; then cp .env.example .env; echo ".env 파일을 만들었습니다 (DRY_RUN=true)."; fi
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r backend/requirements.txt
if [ ! -d frontend/dist ]; then (cd frontend && npm install --no-audit --no-fund && npm run build); fi
echo ""
echo "  ▶ 대시보드: http://localhost:8000   (종료: Ctrl + C)"
echo ""
cd backend && exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
