@echo off
title ReqAI - Starting...
color 0A

echo.
echo  ██████╗ ███████╗ ██████╗  █████╗ ██╗
echo  ██╔══██╗██╔════╝██╔═══██╗██╔══██╗██║
echo  ██████╔╝█████╗  ██║   ██║███████║██║
echo  ██╔══██╗██╔══╝  ██║▄▄ ██║██╔══██║██║
echo  ██║  ██║███████╗╚██████╔╝██║  ██║██║
echo  ╚═╝  ╚═╝╚══════╝ ╚══▀▀═╝ ╚═╝  ╚═╝╚═╝
echo.
echo  AI Powered Business Requirement Document Generator
echo  ====================================================
echo.

:: ── Check Python ─────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.12 or 3.13.
    pause
    exit /b 1
)

echo [1/3] Starting FastAPI Backend on http://127.0.0.1:8000 ...
start "ReqAI Backend" cmd /k "cd /d "%~dp0backend" && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo [2/3] Waiting for backend to initialize...
timeout /t 6 /nobreak >nul

:: ── Verify backend is up ─────────────────────────────────────────
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Backend may still be starting. Check the backend terminal.
) else (
    echo [OK] Backend is running.
)

echo [3/3] Starting Frontend Server on http://127.0.0.1:5500 ...
start "ReqAI Frontend" cmd /k "cd /d "%~dp0frontend" && python -m http.server 5500"

timeout /t 3 /nobreak >nul

echo.
echo  ====================================================
echo   ReqAI is READY for demonstration!
echo  ====================================================
echo.
echo   Frontend:    http://127.0.0.1:5500/
echo   Backend API: http://127.0.0.1:8000/health
echo   API Docs:    http://127.0.0.1:8000/api/docs
echo.
echo   Opening browser...
echo.

:: ── Open browser ─────────────────────────────────────────────────
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:5500/"

echo  Both servers are running in separate windows.
echo  Close those windows to stop the servers.
echo.
pause
