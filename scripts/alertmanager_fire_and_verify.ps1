param(
    [string]$AlertmanagerUrl = "http://localhost:9093",
    [int]$DurationMinutes = 15,
    [int]$TimeoutSeconds = 180,
    [int]$PollSeconds = 5,
    [string]$ExpectIntegrations = "",
    [switch]$RequireAllIntegrations,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "alertmanager_fire_and_verify.py"
if (-not (Test-Path $pythonScript)) {
    throw "Python verifier script not found: $pythonScript"
}

$pythonExecutable = $null
$pythonPrefixArgs = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExecutable = "py"
    $pythonPrefixArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExecutable = "python"
} else {
    throw "Neither 'py' nor 'python' command is available."
}

$args = @()
$args += $pythonPrefixArgs
$args += $pythonScript
$args += @("--alertmanager-url", $AlertmanagerUrl)
$args += @("--duration-minutes", $DurationMinutes.ToString())
$args += @("--timeout-seconds", $TimeoutSeconds.ToString())
$args += @("--poll-seconds", $PollSeconds.ToString())

if (-not [string]::IsNullOrWhiteSpace($ExpectIntegrations)) {
    $args += @("--expect-integrations", $ExpectIntegrations)
}
if ($RequireAllIntegrations) {
    $args += "--require-all-integrations"
}
if ($DryRun) {
    $args += "--dry-run"
}

& $pythonExecutable @args
if ($LASTEXITCODE -ne 0) {
    throw "Alertmanager fire+verify failed with exit code $LASTEXITCODE"
}
