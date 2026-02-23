Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [string]$OutputFile = "backups/docker_images_cache.tar"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

if (-not [System.IO.Path]::IsPathRooted($OutputFile)) {
    $OutputFile = Join-Path $repoRoot $OutputFile
}

$outputDir = Split-Path -Parent $OutputFile
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

$images = @(
    "postgres:16-alpine",
    "redis:7-alpine",
    "prom/prometheus:v3.5.0",
    "prom/alertmanager:v0.28.1",
    "grafana/grafana:11.3.0"
)

foreach ($image in $images) {
    docker image inspect $image | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Image is missing locally: $image. Run scripts/docker_warmup.ps1 first."
    }
}

docker save -o $OutputFile $images
if ($LASTEXITCODE -ne 0) {
    throw "Failed to export docker image cache to $OutputFile"
}

Write-Host "Docker image cache exported: $OutputFile"
