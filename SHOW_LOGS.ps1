$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Files = @(
    "$Root\logs\phase1-setup.log",
    "$Root\logs\phase1-tests.log",
    "$Root\logs\gridwise.log",
    "$Root\logs\phase1-uvicorn-err.log"
)
foreach ($File in $Files) {
    Write-Host ""; Write-Host "===== $File =====" -ForegroundColor Cyan
    if (Test-Path $File) { Get-Content $File -Tail 80 } else { Write-Host "Not created yet." }
}