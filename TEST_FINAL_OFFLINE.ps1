$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$env:RUN_LIVE_LLM_TESTS = "0"
$env:RUN_PHASE3_LIVE_E2E = "0"
& $Py -m pytest -q
exit $LASTEXITCODE