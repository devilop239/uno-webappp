@echo off
setlocal
title UNO WebApp Launcher
cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
	set "PYTHON=%~dp0.venv\Scripts\python.exe"
) else (
	for /f "delims=" %%P in ('where python') do if not defined PYTHON set "PYTHON=%%P"
)

if not defined PYTHON (
	echo Python was not found. Install Python or add it to PATH.
	pause
	exit /b 1
)

echo Starting UNO WebApp
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:8080

start "UNO Backend" /D "%~dp0" cmd /k ""%PYTHON%" -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-exclude front-end"
start "UNO Frontend" /D "%~dp0front-end" cmd /k ""%PYTHON%" -m http.server 8080 --bind 127.0.0.1"

echo Both services started. You can close this window.
endlocal
