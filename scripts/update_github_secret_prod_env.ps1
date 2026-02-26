param(
    [string]$InputFile = ".env",
    [string]$SecretName = "PROD_ENV_FILE_B64",
    [string]$Repository = "",
    [string]$RemoteHost = "",
    [string]$RemoteUser = "deploy",
    [string]$RemoteEnvPath = "/opt/guitaronline/.env"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-GhPath {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if ($gh) {
        return $gh.Source
    }

    $knownPath = "C:\Program Files\GitHub CLI\gh.exe"
    if (Test-Path $knownPath) {
        return $knownPath
    }

    throw "GitHub CLI not found. Install it first (winget install GitHub.cli)."
}

function Resolve-SshPath {
    $ssh = Get-Command ssh -ErrorAction SilentlyContinue
    if ($ssh) {
        return $ssh.Source
    }
    return "C:\Windows\System32\OpenSSH\ssh.exe"
}

function Resolve-RepositorySlug([string]$repository) {
    if (-not [string]::IsNullOrWhiteSpace($repository)) {
        return $repository
    }

    $remoteUrl = (git remote get-url origin).Trim()
    if (-not $remoteUrl) {
        throw "Cannot detect git remote origin URL."
    }

    $patterns = @(
        '^https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$',
        '^git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
        '^ssh://git@github\.com/([^/]+)/([^/]+?)(?:\.git)?$'
    )

    foreach ($pattern in $patterns) {
        if ($remoteUrl -match $pattern) {
            return "$($Matches[1])/$($Matches[2])"
        }
    }

    throw "Unsupported origin URL format: $remoteUrl"
}

function Get-EncodedEnvContent {
    param(
        [string]$InputFile,
        [string]$RemoteHost,
        [string]$RemoteUser,
        [string]$RemoteEnvPath
    )

    if (-not [string]::IsNullOrWhiteSpace($RemoteHost)) {
        $sshPath = Resolve-SshPath
        if (-not (Test-Path $sshPath)) {
            throw "ssh executable not found."
        }

        $remoteTarget = "$RemoteUser@$RemoteHost"
        Write-Host "Reading env from remote host: ${remoteTarget}:${RemoteEnvPath}"
        $encodedRemote = & $sshPath -o BatchMode=yes $remoteTarget "base64 -w0 '$RemoteEnvPath'"
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($encodedRemote)) {
            throw "Failed to read or encode remote env file: ${remoteTarget}:${RemoteEnvPath}"
        }
        return $encodedRemote.Trim()
    }

    if (-not (Test-Path $InputFile)) {
        throw "Input file not found: $InputFile"
    }

    $resolvedPath = (Resolve-Path $InputFile).Path
    Write-Host "Reading env from local file: $resolvedPath"
    $bytes = [System.IO.File]::ReadAllBytes($resolvedPath)
    return [System.Convert]::ToBase64String($bytes)
}

$ghPath = Resolve-GhPath
$repoSlug = Resolve-RepositorySlug -repository $Repository

$hasToken = -not [string]::IsNullOrWhiteSpace($env:GH_TOKEN) -or `
    -not [string]::IsNullOrWhiteSpace($env:GITHUB_TOKEN)

if (-not $hasToken) {
    & $ghPath auth status | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "GitHub authentication missing. Run 'gh auth login' once or set GH_TOKEN."
    }
}

$encoded = Get-EncodedEnvContent `
    -InputFile $InputFile `
    -RemoteHost $RemoteHost `
    -RemoteUser $RemoteUser `
    -RemoteEnvPath $RemoteEnvPath

Write-Host "Updating repository secret '$SecretName' in '$repoSlug'..."
& $ghPath secret set $SecretName --repo $repoSlug --body $encoded
if ($LASTEXITCODE -ne 0) {
    throw "Failed to update secret '$SecretName' in '$repoSlug'."
}

$secretList = & $ghPath secret list --repo $repoSlug
if ($LASTEXITCODE -ne 0) {
    throw "Failed to verify secret list in '$repoSlug'."
}

if (-not (($secretList | Out-String) -match "(?m)^$([regex]::Escape($SecretName))\s")) {
    throw "Secret '$SecretName' was not found after update."
}

Write-Host "Secret '$SecretName' successfully updated for '$repoSlug'."
