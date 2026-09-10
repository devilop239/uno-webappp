@echo off
TITLE UNO WebApp Launcher

echo ==================================================
echo  Starting UNO WebApp: Backend (8000) ^& Frontend (8080)
echo ==================================================

:: Launch FastAPI Backend Server in background window
echo [1/2] Starting FastAPI Backend on http://localhost:8000 ...
start "UNO FastAPI Backend" cmd /k "python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-exclude front-end"

:: Launch Vite Frontend in current window
echo [2/2] Starting Vite Frontend on http://localhost:8080 ...
cd front-end
npm run dev
