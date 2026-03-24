@echo off
title SilverEdge — MCX Silver Trading Platform

echo.
echo  ==========================================
echo    SilverEdge MCX Silver Trading Platform
echo  ==========================================
echo.

REM ── Check .env ─────────────────────────────
if not exist "backend\.env" (
    echo [WARN] backend\.env not found — copying from .env.example
    copy "backend\.env.example" "backend\.env" >nul
    echo.
    echo [ACTION REQUIRED] Fill in your credentials in backend\.env then re-run.
    echo.
    echo Required keys:
    echo   ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_ID, ANGEL_ONE_PASSWORD
    echo   ANGEL_ONE_TOTP_SECRET, DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN
    echo   SECRET_KEY  (generate: python -c "import secrets; print(secrets.token_hex(32))")
    pause
    exit /b 1
)

REM ── Backend ────────────────────────────────
echo [1/4] Setting up Python virtual environment...
cd backend
if not exist ".venv" (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [2/4] Installing Python dependencies...
pip install -q -r requirements.txt
echo [OK] Backend dependencies installed

echo [3/4] Starting FastAPI backend on port 8000...
start "SilverEdge Backend" cmd /k "call .venv\Scripts\activate.bat && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo [OK] Backend started in new window
cd ..

REM ── Frontend ───────────────────────────────
echo [4/4] Installing frontend dependencies...
cd frontend
if not exist "node_modules" (
    npm install --silent
)
echo [OK] Frontend dependencies installed

echo.
echo  ==========================================
echo    Platform is starting!
echo    Dashboard  -^>  http://localhost:3000
echo    API Docs   -^>  http://localhost:8000/docs
echo  ==========================================
echo.

npm run dev
cd ..

echo.
echo  All services stopped.
pause
