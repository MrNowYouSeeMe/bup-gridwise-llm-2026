$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing."
}

$env:RUN_LIVE_LLM_TESTS = "0"

& $Py -m pytest -q `
    tests/test_phase1.py `
    tests/test_phase1_hardening.py `
    tests/test_phase2_guardrails.py `
    tests/test_phase2_interpreter_unit.py

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[PASS] Offline Phase 1 + Phase 2 regression passed." -ForegroundColor Green