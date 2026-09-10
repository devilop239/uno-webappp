# PowerShell Launcher for UNO WebApp Backend & Frontend

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Starting UNO WebApp: Backend (8000) & Frontend (8080)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend in background process
Write-Host "[1/2] Launching FastAPI Backend on http://localhost:8000 ..." -ForegroundColor Green
$backend = Start-Process python -ArgumentList "-m uvicorn app:app --host 0.0.0.0 --port 8000 --reload --reload-exclude front-end" -PassThru

Start-Sleep -Seconds 2

# 2. Start Vite Frontend in current session
Write-Host "[2/2] Launching Vite Frontend on http://localhost:8080 ..." -ForegroundColor Green
Set-Location -Path "front-end"
npm run dev

# Cleanup backend on stop
if ($backend -and -not $backend.HasExited) {
    Stop-Process -Id $backend.Id -Force
}
