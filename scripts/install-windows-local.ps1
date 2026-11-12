#requires -Version 5.1
[CmdletBinding()]
param(
    [string]$ClientId,
    [string]$TenantId,
    [string]$InstallDirectory = (Join-Path $env:LOCALAPPDATA 'Programs\M365-MCP'),
    [switch]$NonInteractive,
    [switch]$SkipLogin
)

$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This installer requires Windows 10/11.'
}
if (-not $NonInteractive) {
    if (-not $PSBoundParameters.ContainsKey('ClientId')) {
        $ClientId = Read-Host 'Your own Application (client) ID? Enter a GUID, or press Enter to use the built-in public application'
    }
    if (-not $PSBoundParameters.ContainsKey('TenantId')) {
        $TenantId = Read-Host 'Directory (tenant) ID? Enter its GUID, organizations, common, or consumers; Enter defaults to organizations'
    }
}
$ClientId = ([string]$ClientId).Trim()
$TenantId = ([string]$TenantId).Trim()
if (-not $ClientId) { $ClientId = '6e35216e-2623-43cc-b867-83bec0865cf3' }
if (-not $TenantId) { $TenantId = 'organizations' }
$guidPattern = '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
if ($ClientId -notmatch $guidPattern) {
    throw 'ClientId must be the Application (client) ID GUID, not an Object ID or Client Secret.'
}
$TenantId = $TenantId.ToLowerInvariant()
if ($TenantId -notmatch $guidPattern -and $TenantId -notin @('organizations', 'common', 'consumers')) {
    throw 'TenantId must be a directory GUID, organizations, common, or consumers.'
}
if ($InstallDirectory -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+(?:\\|$))') {
    throw 'InstallDirectory must be an absolute path.'
}
$InstallDirectory = [IO.Path]::GetFullPath($InstallDirectory)
$machineArchitecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
$architecture = switch ($machineArchitecture.ToUpperInvariant()) {
    'AMD64' { 'amd64' }
    'ARM64' { 'arm64' }
    default { throw "Unsupported Windows architecture: $machineArchitecture. Use AMD64 or ARM64 Windows." }
}

$temporaryDirectory = Join-Path ([IO.Path]::GetTempPath()) ('m365-install-' + [Guid]::NewGuid().ToString('N'))
$previousProtocol = [Net.ServicePointManager]::SecurityProtocol
try {
    [Net.ServicePointManager]::SecurityProtocol = $previousProtocol -bor [Net.SecurityProtocolType]::Tls12
    New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
    $release = Invoke-RestMethod -Uri 'https://api.github.com/repos/sagehou/M365-MCP-Server/releases/latest' -Headers @{
        Accept = 'application/vnd.github+json'
        'User-Agent' = 'M365-MCP-Windows-Installer'
    } -TimeoutSec 60
    if ($release.draft -or $release.prerelease -or $release.tag_name -notmatch '^v\d+\.\d+\.\d+$') {
        throw 'GitHub did not return a stable M365 MCP release.'
    }
    $downloadBase = 'https://github.com/sagehou/M365-MCP-Server/releases/download/' + $release.tag_name
    $executableAsset = "m365-mcp-windows-local-go-$architecture.exe"
    $packageAsset = "m365-mcp-windows-local-go-$architecture.zip"
    $skillAsset = 'm365-mail-skill.zip'
    foreach ($name in @('SHA256SUMS.txt', $packageAsset, $skillAsset)) {
        if (@($release.assets | Where-Object { $_.name -ceq $name }).Count -ne 1) {
            throw "Release $($release.tag_name) is missing $name. No installation changes were made."
        }
        Invoke-WebRequest -UseBasicParsing -Uri "$downloadBase/$name" -OutFile (Join-Path $temporaryDirectory $name) -TimeoutSec 300
    }
    $checksums = @(Get-Content -LiteralPath (Join-Path $temporaryDirectory 'SHA256SUMS.txt'))
    foreach ($name in @($packageAsset, $skillAsset)) {
        $pattern = '^([0-9a-fA-F]{64})\s+\*?' + [regex]::Escape($name) + '$'
        $records = @($checksums | Where-Object { $_ -cmatch $pattern })
        if ($records.Count -ne 1) { throw "Expected exactly one SHA-256 record for $name." }
        $expectedHash = [regex]::Match($records[0], $pattern).Groups[1].Value
        $actualHash = (Get-FileHash -LiteralPath (Join-Path $temporaryDirectory $name) -Algorithm SHA256).Hash
        if ($actualHash -ine $expectedHash) {
            throw "SHA-256 mismatch for $name. No installation changes were made."
        }
    }

    $packageDirectory = Join-Path $temporaryDirectory 'package'
    Expand-Archive -LiteralPath (Join-Path $temporaryDirectory $packageAsset) -DestinationPath $packageDirectory
    $packagedExecutable = Join-Path $packageDirectory 'm365-mcp-windows-local-go.exe'
    $pattern = '^([0-9a-fA-F]{64})\s+\*?' + [regex]::Escape($executableAsset) + '$'
    $records = @($checksums | Where-Object { $_ -cmatch $pattern })
    if ($records.Count -ne 1 -or -not (Test-Path -LiteralPath $packagedExecutable -PathType Leaf)) {
        throw 'The Go package is missing its executable or its SHA-256 record.'
    }
    if ((Get-FileHash -LiteralPath $packagedExecutable -Algorithm SHA256).Hash -ine [regex]::Match($records[0], $pattern).Groups[1].Value) {
        throw 'The packaged Go executable does not match the release SHA-256.'
    }
    $packageFiles = @('m365-mcp-windows-local-go.exe', 'LICENSE', 'THIRD_PARTY_NOTICES.txt', 'README.md', 'README.zh-CN.md')
    foreach ($name in $packageFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageDirectory $name) -PathType Leaf)) {
            throw "The Go package is missing $name. No installation changes were made."
        }
    }
    $skillDirectory = Join-Path $temporaryDirectory 'skill'
    Expand-Archive -LiteralPath (Join-Path $temporaryDirectory $skillAsset) -DestinationPath $skillDirectory
    if (-not (Test-Path -LiteralPath (Join-Path $skillDirectory 'm365-mail\SKILL.md') -PathType Leaf)) {
        throw 'The release Skill archive does not contain m365-mail/SKILL.md.'
    }
    New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
    $executable = Join-Path $InstallDirectory 'm365-mcp-windows-local-go.exe'
    foreach ($name in $packageFiles) {
        Copy-Item -LiteralPath (Join-Path $packageDirectory $name) -Destination (Join-Path $InstallDirectory $name) -Force
    }
    Copy-Item -LiteralPath (Join-Path $skillDirectory 'm365-mail') -Destination $InstallDirectory -Recurse -Force
    $configurationPath = Join-Path $InstallDirectory 'mcp.json'
    $configuration = @{ mcpServers = @{ 'm365-local' = @{ command = $executable; args = @('stdio') } } }
    $utf8 = [Text.UTF8Encoding]::new($false)
    [IO.File]::WriteAllText($configurationPath, ($configuration | ConvertTo-Json -Depth 5), $utf8)
    $loginCommand = "& '" + $executable.Replace("'", "''") + "' login --client-id '$ClientId' --tenant '$TenantId'"
    [IO.File]::WriteAllText((Join-Path $InstallDirectory 'login-command.txt'), $loginCommand, $utf8)
    Write-Host "Installed Go $($release.tag_name) ($architecture): $executable"
    Write-Host "MCP configuration: $configurationPath"
    Write-Host "Skill folder: $(Join-Path $InstallDirectory 'm365-mail')"
    if ($SkipLogin) {
        Write-Host 'Sign-in has not run. Complete it with the saved command before connecting the MCP client:'
        Write-Host $loginCommand
    } else {
        & $executable login --client-id $ClientId --tenant $TenantId
        if ($LASTEXITCODE -ne 0) {
            throw "Go was installed, but sign-in failed. Retry the command in $(Join-Path $InstallDirectory 'login-command.txt')."
        }
    }
    Write-Host 'Merge the m365-local entry into your agent MCP settings and install the complete Skill folder in its Skill directory.'
} finally {
    [Net.ServicePointManager]::SecurityProtocol = $previousProtocol
    if (Test-Path -LiteralPath $temporaryDirectory) {
        Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force
    }
}
