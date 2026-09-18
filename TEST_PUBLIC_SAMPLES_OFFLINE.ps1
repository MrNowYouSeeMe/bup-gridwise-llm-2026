$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing."
}

& $Py -m pytest -q `
    tests/test_phase3_public_samples.py

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[PASS] All 10 official public samples match optimal cost offline." -ForegroundColor Green
