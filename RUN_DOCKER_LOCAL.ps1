param(
    [int]$HostPort = 8099
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$Image = "gridwise-llm:local-final"
$Name = "gridwise-final-manual"

docker build -t $Image .

try {
    docker rm -f $Name 2>$null | Out-Null
}
catch {
}

docker run -d --rm `
    --name $Name `
    -p "127.0.0.1:${HostPort}:8000" `
    --env-file .env `
    -e PORT=8000 `
    $Image

Write-Host "Container started." -ForegroundColor Green
Write-Host "Health: http://127.0.0.1:$HostPort/health" -ForegroundColor Cyan
Write-Host "Stop: docker stop $Name" -ForegroundColor Yellow