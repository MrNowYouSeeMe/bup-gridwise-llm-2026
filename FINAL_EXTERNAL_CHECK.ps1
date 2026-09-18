param(
    [Parameter(Mandatory=$true)]
    [string]$BaseUrl
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

$BaseUrl = $BaseUrl.TrimEnd("/")

$Health = Invoke-RestMethod `
    -Method Get `
    -Uri "$BaseUrl/health" `
    -TimeoutSec 15

if ($Health.status -ne "ok") {
    throw "External /health did not return status=ok."
}

Write-Host "[PASS] External /health." -ForegroundColor Green

$Pack = Get-Content `
    "tests\data\public_sample_cases.json" `
    -Raw |
    ConvertFrom-Json

$Case = $Pack.cases[0]
$Payload = $Case.input | ConvertTo-Json -Depth 100 -Compress

$Times = @()

for ($i = 1; $i -le 8; $i++) {
    $Watch = [System.Diagnostics.Stopwatch]::StartNew()

    $Result = Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/optimize-energy" `
        -ContentType "application/json" `
        -Body $Payload `
        -TimeoutSec 30

    $Watch.Stop()
    $Seconds = $Watch.Elapsed.TotalSeconds
    $Times += $Seconds

    if ($Result.scenario_id -ne $Case.input.scenario_id) {
        throw "External response scenario_id mismatch."
    }

    $Expected = [double]$Case.expected_output.total_cost_bdt
    $Actual = [double]$Result.total_cost_bdt

    if ([Math]::Abs($Expected - $Actual) -gt 0.01) {
        throw "External optimal cost mismatch."
    }

    Write-Host ("[LATENCY] run={0} seconds={1:N3}" -f $i, $Seconds)
}

$Sorted = @($Times | Sort-Object)
$Index = [Math]::Ceiling(0.95 * $Sorted.Count) - 1

if ($Index -lt 0) {
    $Index = 0
}

$P95 = [double]$Sorted[$Index]

Write-Host ("[RESULT] external p95={0:N3}s" -f $P95)

if ($P95 -gt 5.0) {
    throw "External p95 is above the <=5s full-score target."
}

Write-Host "[PASS] External endpoint accuracy and latency gate passed." -ForegroundColor Green