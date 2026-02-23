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
    throw "Docker image cache file not found: $InputFile"
}

docker load -i $InputFile
if ($LASTEXITCODE -ne 0) {
    throw "Failed to import docker image cache from $InputFile"
}

Write-Host "Docker image cache imported: $InputFile"
