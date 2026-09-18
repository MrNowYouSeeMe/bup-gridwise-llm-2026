$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { throw "Virtual environment missing. Run SETUP_BUP_GRIDWISE_PHASE1.ps1 first." }
Write-Host "[INFO] API:    http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "[INFO] Health: http://127.0.0.1:8000/health" -ForegroundColor Cyan
Write-Host "[INFO] Log:    $Root\logs\gridwise.log" -ForegroundColor Cyan
& $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload