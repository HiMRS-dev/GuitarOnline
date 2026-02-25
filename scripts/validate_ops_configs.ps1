Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path

Push-Location $repoRoot
try {
    docker compose -f docker-compose.prod.yml config -q
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose config validation failed"
    }

    docker compose -f docker-compose.prod.yml -f docker-compose.proxy.yml config -q
    if ($LASTEXITCODE -ne 0) {
        throw "docker compose proxy profile validation failed"
    }

    $oncallConfigPath = Join-Path $repoRoot "ops/alertmanager/alertmanager.oncall.generated.yml"
    if (Test-Path $oncallConfigPath) {
        docker compose -f docker-compose.prod.yml -f docker-compose.alerting.yml config -q
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose alerting profile validation failed"
        }
    } else {
        Write-Host "Skipping alerting profile compose validation (generated on-call config is absent)."
    }

    docker run --rm --entrypoint promtool -v "${repoRoot}/ops/prometheus:/etc/prometheus:ro" `
        prom/prometheus:v3.5.0 check config /etc/prometheus/prometheus.yml
    if ($LASTEXITCODE -ne 0) {
        throw "promtool config validation failed"
    }

    docker run --rm --entrypoint promtool -v "${repoRoot}/ops/prometheus:/etc/prometheus:ro" `
        prom/prometheus:v3.5.0 check rules /etc/prometheus/alerts.yml
    if ($LASTEXITCODE -ne 0) {
        throw "promtool rules validation failed"
    }

    docker run --rm --entrypoint amtool -v "${repoRoot}/ops/alertmanager:/etc/alertmanager:ro" `
        prom/alertmanager:v0.28.1 check-config /etc/alertmanager/alertmanager.yml
    if ($LASTEXITCODE -ne 0) {
        throw "amtool alertmanager config validation failed"
    }

    if (Test-Path $oncallConfigPath) {
        docker run --rm --entrypoint amtool -v "${repoRoot}/ops/alertmanager:/etc/alertmanager:ro" `
            prom/alertmanager:v0.28.1 check-config /etc/alertmanager/alertmanager.oncall.generated.yml
        if ($LASTEXITCODE -ne 0) {
            throw "amtool on-call alertmanager config validation failed"
        }
    } else {
        Write-Host "Skipping on-call alertmanager validation (generated on-call config is absent)."
    }
} finally {
    Pop-Location
}

Write-Host "Ops configuration validation passed."
