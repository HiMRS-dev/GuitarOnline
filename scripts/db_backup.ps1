Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [string]$OutputFile = ""
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$backupDir = Join-Path $repoRoot "backups"

if (-not (Test-Path $backupDir)) {
    New-Item -Path $backupDir -ItemType Directory | Out-Null
}

if ([string]::IsNullOrWhiteSpace($OutputFile)) {
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $OutputFile = Join-Path $backupDir "guitaronline-$timestamp.sql"
} elseif (-not [System.IO.Path]::IsPathRooted($OutputFile)) {
    $OutputFile = Join-Path $repoRoot $OutputFile
}

$dumpCommand = 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists'

Push-Location $repoRoot
try {
    docker compose exec -T db sh -c $dumpCommand | Set-Content -Path $OutputFile -Encoding utf8
    if ($LASTEXITCODE -ne 0) {
        throw "Backup command failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host "Backup saved to: $OutputFile"
