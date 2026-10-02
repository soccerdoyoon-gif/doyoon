@echo off
chcp 65001 >nul
REM Docker 없이 실행 (Windows). 처음 실행 시 필요한 패키지를 자동 설치합니다.
cd /d %~dp0
if not exist .env copy .env.example .env
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -q -r backend\requirements.txt
if not exist frontend\dist (
  cd frontend
  call npm install --no-audit --no-fund
  call npm run build
  cd ..
)
echo.
echo   대시보드: http://localhost:8000   (종료: Ctrl + C)
echo.
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
