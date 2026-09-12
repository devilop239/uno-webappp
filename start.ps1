$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

Write-Host "Starting UNO WebApp" -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  Frontend: http://localhost:8080"

$backend = Start-Process $python -WorkingDirectory $root -ArgumentList @(
    "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-exclude", "front-end"
) -PassThru
$frontend = Start-Process $python -WorkingDirectory (Join-Path $root "front-end") -ArgumentList @(
    "-m", "http.server", "8080", "--bind", "127.0.0.1"
) -PassThru

try {
    Write-Host "Press Ctrl+C to stop both services." -ForegroundColor Yellow
    while (-not $backend.HasExited -and -not $frontend.HasExited) {
        Start-Sleep -Seconds 1
    }
}
finally {
    foreach ($process in @($backend, $frontend)) {
        if ($process -and -not $process.HasExited) { Stop-Process -Id $process.Id -Force }
    }
}
