Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [Parameter(Mandatory = $true)]
    [string]$InputFile
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

if (-not [System.IO.Path]::IsPathRooted($InputFile)) {
    $InputFile = Join-Path $repoRoot $InputFile
}

if (-not (Test-Path $InputFile)) {
    throw "Backup file not found: $InputFile"
}

$restoreCommand = 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
$sql = Get-Content -Path $InputFile -Raw

Push-Location $repoRoot
try {
    $sql | docker compose exec -T db sh -c $restoreCommand
    if ($LASTEXITCODE -ne 0) {
        throw "Restore command failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

Write-Host "Restore completed from: $InputFile"
