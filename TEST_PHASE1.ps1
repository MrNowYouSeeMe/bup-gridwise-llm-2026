$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$TestLog = Join-Path $Root "logs\phase1-tests.log"
if (-not (Test-Path $Python)) { throw "Virtual environment missing." }
& $Python -m pytest -q 2>&1 | Tee-Object -FilePath $TestLog
$Code = $LASTEXITCODE
if ($Code -ne 0) {
    Write-Host "[FAIL] Phase 1 test gate failed." -ForegroundColor Red
    Write-Host "[INFO] Test log: $TestLog" -ForegroundColor Yellow
    exit $Code
}
Write-Host "[PASS] Phase 1 test gate passed." -ForegroundColor Green