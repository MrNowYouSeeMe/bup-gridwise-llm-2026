$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing."
}

$env:RUN_LIVE_LLM_TESTS = "1"

& $Py -m pytest -q `
    tests/test_phase2_live_semantics.py

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[PASS] Live multilingual semantic suite passed." -ForegroundColor Green