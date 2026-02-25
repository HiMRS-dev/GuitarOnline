param(
    [string]$InputFile = ".env"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not (Test-Path $InputFile)) {
    throw "Input file not found: $InputFile"
}

$resolvedPath = (Resolve-Path $InputFile).Path
$bytes = [System.IO.File]::ReadAllBytes($resolvedPath)
$encoded = [System.Convert]::ToBase64String($bytes)

Write-Host "Base64 value for GitHub secret PROD_ENV_FILE_B64:"
Write-Output $encoded
