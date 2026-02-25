param(
    [string]$AlertmanagerUrl = "http://localhost:9093",
    [int]$DurationMinutes = 15
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$baseUrl = $AlertmanagerUrl.TrimEnd("/")
$startsAt = (Get-Date).ToUniversalTime().ToString("o")
$endsAt = (Get-Date).ToUniversalTime().AddMinutes($DurationMinutes).ToString("o")
$runId = [Guid]::NewGuid().ToString("N")

$alerts = @(
    @{
        labels = @{
            alertname = "GuitarOnlineSyntheticWarning"
            severity = "warning"
            source = "synthetic"
            run_id = $runId
        }
        annotations = @{
            summary = "Synthetic warning routing test"
            description = "Synthetic warning alert to validate severity routing to warning receivers."
        }
        startsAt = $startsAt
        endsAt = $endsAt
    },
    @{
        labels = @{
            alertname = "GuitarOnlineSyntheticCritical"
            severity = "critical"
            source = "synthetic"
            run_id = $runId
        }
        annotations = @{
            summary = "Synthetic critical routing test"
            description = "Synthetic critical alert to validate severity routing to critical receivers."
        }
        startsAt = $startsAt
        endsAt = $endsAt
    }
)

$payload = $alerts | ConvertTo-Json -Depth 10

Invoke-RestMethod `
    -Uri "$baseUrl/api/v2/alerts" `
    -Method Post `
    -ContentType "application/json" `
    -Body $payload | Out-Null

Write-Host "Synthetic alerts submitted to Alertmanager."
Write-Host "run_id=$runId"
Write-Host "Next checks:"
Write-Host "  1) Alertmanager UI/API shows alerts with run_id=$runId."
Write-Host "  2) Confirm delivery in real channel(s): Slack/PagerDuty/Email."
