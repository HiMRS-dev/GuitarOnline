param(
    [string]$AlertmanagerUrl = "http://localhost:9093",
    [Parameter(Mandatory = $true)]
    [string]$SilenceId
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$baseUrl = $AlertmanagerUrl.TrimEnd("/")
Invoke-RestMethod -Method Delete -Uri "$baseUrl/api/v2/silence/$SilenceId" | Out-Null

Write-Host "Silence expired: $SilenceId"
