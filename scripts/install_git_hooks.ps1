Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

Push-Location $repoRoot
try {
    git config core.hooksPath .githooks
    Write-Host "Configured git hooks path: .githooks"
    Write-Host "Pre-commit secret scan is enabled."
    Write-Host "To verify, run: git config --get core.hooksPath"
} finally {
    Pop-Location
}
