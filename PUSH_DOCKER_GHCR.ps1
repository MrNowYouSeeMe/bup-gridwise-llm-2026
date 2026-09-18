$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$LocalImage = "gridwise-llm:local-final"
$RemoteImage = "ghcr.io/mrnowyouseeme/bup-gridwise-llm-2026"
$Commit = (& git rev-parse --short HEAD).Trim()

docker image inspect $LocalImage *> $null

if ($LASTEXITCODE -ne 0) {
    throw "Local image $LocalImage does not exist. Build/test it first."
}

$Token = (& gh auth token).Trim()

if (-not $Token) {
    throw "GitHub CLI token unavailable. Run gh auth login first."
}

$LoginOutput = $Token | docker login ghcr.io -u MrNowYouSeeMe --password-stdin

if ($LASTEXITCODE -ne 0) {
    throw "GHCR login failed. The GitHub token may need package write permission."
}

docker tag $LocalImage "${RemoteImage}:${Commit}"
docker tag $LocalImage "${RemoteImage}:latest"

docker push "${RemoteImage}:${Commit}"

if ($LASTEXITCODE -ne 0) {
    throw "Commit-tag push failed."
}

docker push "${RemoteImage}:latest"

if ($LASTEXITCODE -ne 0) {
    throw "latest-tag push failed."
}

Write-Host "[PASS] Docker fallback image pushed." -ForegroundColor Green
Write-Host "Image tag: ${RemoteImage}:${Commit}" -ForegroundColor Cyan
Write-Host "Also pushed: ${RemoteImage}:latest" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: Ensure the GHCR package is publicly pullable for the judging window after the organizer's deadline rules allow it." -ForegroundColor Yellow