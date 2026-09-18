$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing."
}

$env:RUN_LIVE_LLM_TESTS = "0"
$env:RUN_PHASE3_LIVE_E2E = "0"

& $Py -m pytest -q

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[PASS] Full offline regression passed." -ForegroundColor Green
