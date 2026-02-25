param(
    [string]$AlertmanagerUrl = "http://localhost:9093",
    [int]$DurationMinutes = 90,
    [string]$Service = "guitaronline-api",
    [switch]$IncludeCritical,
    [string]$CreatedBy = "",
    [Parameter(Mandatory = $true)]
    [string]$Comment
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($DurationMinutes -le 0) {
    throw "DurationMinutes must be greater than 0."
}

$baseUrl = $AlertmanagerUrl.TrimEnd("/")
if ([string]::IsNullOrWhiteSpace($CreatedBy)) {
    $CreatedBy = $env:USERNAME
}
if ([string]::IsNullOrWhiteSpace($CreatedBy)) {
    $CreatedBy = "release-operator"
}

$severityValue = if ($IncludeCritical) { "warning|critical" } else { "warning" }
$matchers = @(
    @{
        name = "severity"
        value = $severityValue
        isRegex = $true
    }
)
if (-not [string]::IsNullOrWhiteSpace($Service)) {
    $matchers += @{
        name = "service"
        value = $Service
        isRegex = $false
    }
}

$startsAt = (Get-Date).ToUniversalTime()
$endsAt = $startsAt.AddMinutes($DurationMinutes)
$payload = @{
    matchers = $matchers
    startsAt = $startsAt.ToString("o")
    endsAt = $endsAt.ToString("o")
    createdBy = $CreatedBy
    comment = $Comment
}

$body = $payload | ConvertTo-Json -Depth 6
$response = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v2/silences" -ContentType "application/json" -Body $body

$silenceId = if ($response.silenceID) { $response.silenceID } else { $response.silenceId }
if ([string]::IsNullOrWhiteSpace($silenceId)) {
    throw "Alertmanager did not return silence ID."
}

Write-Host "Silence created:"
Write-Host "  id: $silenceId"
Write-Host "  starts_at_utc: $($startsAt.ToString("o"))"
Write-Host "  ends_at_utc: $($endsAt.ToString("o"))"
Write-Host "  severity_matcher: $severityValue"
if (-not [string]::IsNullOrWhiteSpace($Service)) {
    Write-Host "  service_matcher: $Service"
}
