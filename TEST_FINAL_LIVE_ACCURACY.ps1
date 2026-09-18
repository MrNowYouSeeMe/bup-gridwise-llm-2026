$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$env:RUN_PHASE3_LIVE_E2E = "1"

$Out = Join-Path $Root "logs\final-live-accuracy-stdout.log"
$Err = Join-Path $Root "logs\final-live-accuracy-stderr.log"

if (Test-Path $Out) { Remove-Item $Out -Force }
if (Test-Path $Err) { Remove-Item $Err -Force }

$P = Start-Process `
    -FilePath $Py `
    -ArgumentList @("-m","pytest","-q","-s","tests/test_phase3_live_e2e.py") `
    -WorkingDirectory $Root `
    -RedirectStandardOutput $Out `
    -RedirectStandardError $Err `
    -Wait `
    -PassThru `
    -NoNewWindow

if (Test-Path $Out) { Get-Content $Out }
if (Test-Path $Err) { Get-Content $Err }

exit $P.ExitCode