Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [int]$MaxRetries = 5,
    [int]$InitialDelaySeconds = 3
)

$images = @(
    "postgres:16-alpine",
    "redis:7-alpine",
    "prom/prometheus:v3.5.0",
    "prom/alertmanager:v0.28.1",
    "grafana/grafana:11.3.0"
)

foreach ($image in $images) {
    $attempt = 1
    $delay = $InitialDelaySeconds
    $pulled = $false

    while ($attempt -le $MaxRetries -and -not $pulled) {
        Write-Host "Pulling $image (attempt $attempt/$MaxRetries)..."
        docker pull $image
        if ($LASTEXITCODE -eq 0) {
            $pulled = $true
            Write-Host "Pulled $image"
            break
        }

        if ($attempt -lt $MaxRetries) {
            Write-Warning "Failed to pull $image. Retrying in $delay second(s)..."
            Start-Sleep -Seconds $delay
            $delay = [Math]::Min($delay * 2, 60)
        }

        $attempt += 1
    }

    if (-not $pulled) {
        throw "Failed to pull $image after $MaxRetries attempt(s)"
    }
}

Write-Host "Docker warmup completed successfully."
