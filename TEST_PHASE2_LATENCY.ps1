$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Py = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $Py)) {
    throw "Virtual environment missing."
}

# Run as a module so the repository root remains importable
# and `from app...` works reliably.
& $Py -m tests.phase2_latency_check

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}