@echo off
rem ============================================
rem  RAG KB Q&A System - One-click launcher
rem  Double-click this file to start backend + frontend + browser
rem ============================================
cd /d %~dp0

echo ============================================
echo   RAG Knowledge Base System Starting...
echo ============================================

sc query MySQL84 2>nul | find "RUNNING" >nul && echo [OK] MySQL running || echo [WARN] MySQL not running
sc query Redis 2>nul | find "RUNNING" >nul && echo [OK] Redis running || echo [WARN] Redis not running

echo [1/3] Starting backend (port 8000)...
start "RAG-Backend" cmd /k "cd /d %~dp0backend && C:\Users\cgold\miniforge3\envs\rag-kb\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 || pause"

echo [2/3] Waiting for backend...
timeout /t 8 /nobreak >nul

echo [3/3] Starting frontend (port 5173)...
start "RAG-Frontend" cmd /k "cd /d %~dp0frontend && npm run dev || pause"

timeout /t 8 /nobreak >nul
start http://localhost:5173

echo.
echo ============================================
echo   Done! Browser should open http://localhost:5173
echo   Login: admin / 123456
echo   Note: Close black windows to stop services
echo ============================================
echo.
pause