param(
    [string]$OutputFile = "ops/alertmanager/alertmanager.oncall.generated.yml"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
$envFilePath = Join-Path $repoRoot ".env"

$dotenv = @{}
if (Test-Path $envFilePath) {
    foreach ($line in Get-Content $envFilePath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line.TrimStart().StartsWith("#")) {
            continue
        }

        $parts = $line.Split("=", 2)
        if ($parts.Count -ne 2) {
            continue
        }

        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $dotenv[$key] = $value
    }
}

function Get-OptionalSetting([string]$Name) {
    $value = [Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($value) -and $dotenv.ContainsKey($Name)) {
        $value = $dotenv[$Name]
    }
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $null
    }
    return $value
}

function Escape-DoubleQuotedYaml([string]$Value) {
    return $Value.Replace("\", "\\").Replace('"', '\"')
}

$slackWebhookUrlRaw = Get-OptionalSetting "ALERTMANAGER_SLACK_WEBHOOK_URL"
$slackChannelRaw = Get-OptionalSetting "ALERTMANAGER_SLACK_CHANNEL"
$pagerdutyRoutingKeyRaw = Get-OptionalSetting "ALERTMANAGER_PAGERDUTY_ROUTING_KEY"
$smtpSmarthostRaw = Get-OptionalSetting "ALERTMANAGER_SMTP_SMARTHOST"
$smtpFromRaw = Get-OptionalSetting "ALERTMANAGER_SMTP_FROM"
$smtpToRaw = Get-OptionalSetting "ALERTMANAGER_SMTP_TO"
$smtpAuthUsernameRaw = Get-OptionalSetting "ALERTMANAGER_SMTP_AUTH_USERNAME"
$smtpAuthPasswordRaw = Get-OptionalSetting "ALERTMANAGER_SMTP_AUTH_PASSWORD"

$hasSlack = -not [string]::IsNullOrWhiteSpace($slackWebhookUrlRaw) -and -not [string]::IsNullOrWhiteSpace($slackChannelRaw)
$hasPagerDuty = -not [string]::IsNullOrWhiteSpace($pagerdutyRoutingKeyRaw)
$hasEmail = -not [string]::IsNullOrWhiteSpace($smtpSmarthostRaw) -and `
    -not [string]::IsNullOrWhiteSpace($smtpFromRaw) -and `
    -not [string]::IsNullOrWhiteSpace($smtpToRaw) -and `
    -not [string]::IsNullOrWhiteSpace($smtpAuthUsernameRaw) -and `
    -not [string]::IsNullOrWhiteSpace($smtpAuthPasswordRaw)

if (-not $hasSlack -and -not $hasPagerDuty -and -not $hasEmail) {
    throw "Configure at least one delivery channel: Slack, PagerDuty, or SMTP email."
}

if (($slackWebhookUrlRaw -and -not $slackChannelRaw) -or (-not $slackWebhookUrlRaw -and $slackChannelRaw)) {
    throw "Slack config is partial. Set both ALERTMANAGER_SLACK_WEBHOOK_URL and ALERTMANAGER_SLACK_CHANNEL."
}

$smtpRequireTlsRaw = Get-OptionalSetting "ALERTMANAGER_SMTP_REQUIRE_TLS"
if ([string]::IsNullOrWhiteSpace($smtpRequireTlsRaw)) {
    $smtpRequireTlsRaw = "true"
}
$smtpRequireTls = $smtpRequireTlsRaw.ToLowerInvariant()
if ($smtpRequireTls -ne "true" -and $smtpRequireTls -ne "false") {
    throw "ALERTMANAGER_SMTP_REQUIRE_TLS must be true or false"
}

if (-not $hasEmail) {
    $smtpRequireTls = "true"
}

$routes = @()
$receivers = @('  - name: default-log')

if ($hasEmail) {
    $routes += @(
        '    - receiver: email-warning',
        '      matchers:',
        '        - severity="warning"',
        '      group_wait: 60s',
        '      group_interval: 10m',
        '      repeat_interval: 6h'
    )
}

if ($hasSlack) {
    if (-not $hasEmail) {
        $routes += @(
            '    - receiver: slack-warning',
            '      matchers:',
            '        - severity="warning"',
            '      group_wait: 60s',
            '      group_interval: 10m',
            '      repeat_interval: 6h'
        )
    }

    $routes += @(
        '    - receiver: slack-critical',
        '      matchers:',
        '        - severity="critical"',
        '      group_wait: 15s',
        '      group_interval: 5m',
        '      repeat_interval: 1h'
    )
    if ($hasPagerDuty) {
        $routes += '      continue: true'
    }
}

if ($hasPagerDuty) {
    $routes += @(
        '    - receiver: pagerduty-critical',
        '      matchers:',
        '        - severity="critical"',
        '      group_wait: 15s',
        '      group_interval: 5m',
        '      repeat_interval: 1h'
    )
}

if ($hasEmail) {
    $smtpSmarthost = Escape-DoubleQuotedYaml $smtpSmarthostRaw
    $smtpFrom = Escape-DoubleQuotedYaml $smtpFromRaw
    $smtpTo = Escape-DoubleQuotedYaml $smtpToRaw
    $smtpAuthUsername = Escape-DoubleQuotedYaml $smtpAuthUsernameRaw
    $smtpAuthPassword = Escape-DoubleQuotedYaml $smtpAuthPasswordRaw
    $receivers += @(
        '  - name: email-warning',
        '    email_configs:',
        "      - to: `"$smtpTo`"",
        "        from: `"$smtpFrom`"",
        "        smarthost: `"$smtpSmarthost`"",
        "        auth_username: `"$smtpAuthUsername`"",
        "        auth_password: `"$smtpAuthPassword`"",
        "        require_tls: $smtpRequireTls",
        '        send_resolved: true'
    )
}

if ($hasSlack) {
    $slackWebhookUrl = Escape-DoubleQuotedYaml $slackWebhookUrlRaw
    $slackChannel = Escape-DoubleQuotedYaml $slackChannelRaw
    if (-not $hasEmail) {
        $receivers += @(
            '  - name: slack-warning',
            '    slack_configs:',
            "      - api_url: `"$slackWebhookUrl`"",
            "        channel: `"$slackChannel`"",
            '        send_resolved: true',
            '        title: "{{ .CommonLabels.alertname }} ({{ .Status }})"',
            '        text: "<!channel> \U0001F6A8 {{ .CommonAnnotations.summary }}\n{{ .CommonAnnotations.description }}"'
        )
    }
    $receivers += @(
        '  - name: slack-critical',
        '    slack_configs:',
        "      - api_url: `"$slackWebhookUrl`"",
        "        channel: `"$slackChannel`"",
        '        send_resolved: true',
        '        title: "{{ .CommonLabels.alertname }} ({{ .Status }})"',
        '        text: "<!channel> \U0001F6A8 {{ .CommonAnnotations.summary }}\n{{ .CommonAnnotations.description }}"'
    )
}

if ($hasPagerDuty) {
    $pagerdutyRoutingKey = Escape-DoubleQuotedYaml $pagerdutyRoutingKeyRaw
    $receivers += @(
        '  - name: pagerduty-critical',
        '    pagerduty_configs:',
        "      - routing_key: `"$pagerdutyRoutingKey`"",
        '        severity: "critical"',
        '        send_resolved: true',
        '        description: "{{ .CommonAnnotations.summary }}"'
    )
}

$routesText = if ($routes.Count -eq 0) {
    '  routes: []'
} else {
    "  routes:`n$($routes -join "`n")"
}

$receiversText = $receivers -join "`n"

$config = @"
global:
  resolve_timeout: 5m

route:
  receiver: default-log
  group_by: ["service", "alertname", "severity"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 2h
$routesText

inhibit_rules:
  - source_matchers:
      - severity="critical"
    target_matchers:
      - severity="warning"
    equal: ["alertname", "service"]
  - source_matchers:
      - alertname="GuitarOnlineApiDown"
    target_matchers:
      - alertname=~"GuitarOnlineApiHigh5xxRate|GuitarOnlineApiHighP95Latency"
    equal: ["service"]

receivers:
$receiversText
"@

$outputPath = Join-Path $repoRoot $OutputFile
$outputDir = Split-Path -Parent $outputPath
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

Set-Content -Path $outputPath -Value $config -Encoding UTF8
Write-Host "Generated Alertmanager on-call config: $outputPath"
