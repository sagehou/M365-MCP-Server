#requires -Version 5.1
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'install-windows-local.ps1'
$testDirectory = Join-Path ([IO.Path]::GetTempPath()) ('m365-installer-check-' + [Guid]::NewGuid().ToString('N'))
$originalArchitecture = $env:PROCESSOR_ARCHITECTURE
$originalNativeArchitecture = $env:PROCESSOR_ARCHITEW6432
$originalProtocol = [Net.ServicePointManager]::SecurityProtocol
$script:prompts = New-Object 'Collections.Generic.Queue[string]'
$script:metadataRequests = 0
$script:badHash = $false
$script:duplicateChecksum = $false
$script:missingAsset = $false
$script:mismatchBinary = $false

function Assert($Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Read-Host {
    param([string]$Prompt)
    Assert ($script:prompts.Count -gt 0) "Unexpected interactive prompt: $Prompt"
    return $script:prompts.Dequeue()
}

function Invoke-RestMethod {
    param($Uri, $Headers, $TimeoutSec)
    Assert ($Uri -ceq 'https://api.github.com/repos/sagehou/M365-MCP-Server/releases/latest') 'Installer must resolve one stable release.'
    $script:metadataRequests++
    $names = @('SHA256SUMS.txt', 'm365-mcp-windows-local-go-amd64.zip', 'm365-mcp-windows-local-go-arm64.zip', 'm365-mail-skill.zip')
    if ($script:missingAsset) { $names = @($names | Where-Object { $_ -ne 'm365-mail-skill.zip' }) }
    return [pscustomobject]@{ tag_name = 'v9.8.7'; draft = $false; prerelease = $false; assets = @($names | ForEach-Object { [pscustomobject]@{ name = $_ } }) }
}

function Invoke-WebRequest {
    param([switch]$UseBasicParsing, $Uri, $OutFile, $TimeoutSec)
    Assert ($Uri.StartsWith('https://github.com/sagehou/M365-MCP-Server/releases/download/v9.8.7/')) 'Downloads must stay on the resolved release.'
    $name = $Uri.Substring($Uri.LastIndexOf('/') + 1)
    if ($name -ceq 'SHA256SUMS.txt') {
        $lines = @('m365-mcp-windows-local-go-amd64.exe', 'm365-mcp-windows-local-go-arm64.exe', 'm365-mcp-windows-local-go-amd64.zip', 'm365-mcp-windows-local-go-arm64.zip', 'm365-mail-skill.zip') | ForEach-Object {
            $hash = (Get-FileHash -LiteralPath (Join-Path $testDirectory $_) -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($script:badHash -and $_ -ceq 'm365-mail-skill.zip') { $hash = '0' * 64 }
            if ($script:mismatchBinary -and $_.EndsWith('.exe')) { $hash = '0' * 64 }
            "$hash  $_"
        }
        if ($script:duplicateChecksum) { $lines += $lines[0] }
        [IO.File]::WriteAllLines($OutFile, $lines)
    } else {
        Copy-Item -LiteralPath (Join-Path $testDirectory $name) -Destination $OutFile
    }
}

try {
    New-Item -ItemType Directory -Path $testDirectory | Out-Null
    foreach ($arch in @('amd64', 'arm64')) {
        $packageDirectory = Join-Path $testDirectory "package-$arch"
        New-Item -ItemType Directory -Path $packageDirectory | Out-Null
        $binary = Join-Path $testDirectory "m365-mcp-windows-local-go-$arch.exe"
        [IO.File]::WriteAllText($binary, "fixture-$arch")
        Copy-Item -LiteralPath $binary -Destination (Join-Path $packageDirectory 'm365-mcp-windows-local-go.exe')
        foreach ($name in @('LICENSE', 'THIRD_PARTY_NOTICES.txt', 'README.md', 'README.zh-CN.md')) {
            [IO.File]::WriteAllText((Join-Path $packageDirectory $name), 'fixture notice or guide')
        }
        Compress-Archive -Path (Join-Path $packageDirectory '*') -DestinationPath (Join-Path $testDirectory "m365-mcp-windows-local-go-$arch.zip")
    }
    $skillSource = Join-Path $testDirectory 'skill-source\m365-mail'
    New-Item -ItemType Directory -Path (Join-Path $skillSource 'references') -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $skillSource 'SKILL.md'), 'fixture skill')
    [IO.File]::WriteAllText((Join-Path $skillSource 'references\zh-CN.md'), 'fixture translation')
    Compress-Archive -LiteralPath $skillSource -DestinationPath (Join-Path $testDirectory 'm365-mail-skill.zip')

    $env:PROCESSOR_ARCHITECTURE = 'AMD64'
    $env:PROCESSOR_ARCHITEW6432 = ''
    $script:prompts.Enqueue('')
    $script:prompts.Enqueue('')
    $destination = Join-Path $testDirectory "default agent's installation"
    & ([scriptblock]::Create((Get-Content -LiteralPath $installer -Raw))) -InstallDirectory $destination -SkipLogin
    Assert ($script:prompts.Count -eq 0) 'Interactive install must ask for both IDs.'
    $configuration = Get-Content -LiteralPath (Join-Path $destination 'mcp.json') -Raw | ConvertFrom-Json
    Assert ($configuration.mcpServers.'m365-local'.command -ceq (Join-Path $destination 'm365-mcp-windows-local-go.exe')) 'Incorrect MCP executable path.'
    Assert ($configuration.mcpServers.'m365-local'.args.Count -eq 1 -and $configuration.mcpServers.'m365-local'.args[0] -ceq 'stdio') 'Installer must configure stdio.'
    $login = Get-Content -LiteralPath (Join-Path $destination 'login-command.txt') -Raw
    Assert ($login.Contains("--client-id '6e35216e-2623-43cc-b867-83bec0865cf3' --tenant 'organizations'")) 'Blank answers must select built-in defaults.'
    Assert ($login.Contains("agent''s installation")) 'Saved login command must escape apostrophes in paths.'
    Assert ((Get-Content -LiteralPath $configuration.mcpServers.'m365-local'.command -Raw) -ceq 'fixture-amd64') 'Default installer chose the wrong Go architecture.'
    Assert (Test-Path -LiteralPath (Join-Path $destination 'm365-mail\references\zh-CN.md')) 'Installer lost Skill references.'

    $clientId = '11111111-2222-3333-4444-555555555555'
    $tenantId = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
    $env:PROCESSOR_ARCHITECTURE = 'x86'
    $env:PROCESSOR_ARCHITEW6432 = 'ARM64'
    & $installer -InstallDirectory $destination -NonInteractive -SkipLogin -ClientId $clientId -TenantId $tenantId
    $login = Get-Content -LiteralPath (Join-Path $destination 'login-command.txt') -Raw
    Assert ($login.Contains("--client-id '$clientId' --tenant '$tenantId'")) 'Custom IDs did not reach the login command.'
    Assert ((Get-Content -LiteralPath (Join-Path $destination 'm365-mcp-windows-local-go.exe') -Raw) -ceq 'fixture-arm64') 'Installer must select native ARM64 even in an emulated shell.'
    Assert (-not (Test-Path -LiteralPath (Join-Path $destination 'm365-mail\m365-mail'))) 'Reinstall nested the Skill folder.'

    $script:prompts.Enqueue($clientId)
    $script:prompts.Enqueue('consumers')
    & $installer -InstallDirectory $destination -SkipLogin
    Assert ($script:prompts.Count -eq 0) 'Custom interactive responses were not consumed.'
    Assert ((Get-Content -LiteralPath (Join-Path $destination 'login-command.txt') -Raw).Contains("--tenant 'consumers'")) 'Personal-account tenant was not preserved.'
    & $installer -InstallDirectory $destination -NonInteractive -SkipLogin
    Assert ((Get-Content -LiteralPath (Join-Path $destination 'login-command.txt') -Raw).Contains("--tenant 'organizations'")) 'Unattended default install prompted or missed its defaults.'

    foreach ($arguments in @(
        @{ ClientId = 'not-a-guid' },
        @{ TenantId = 'not-a-tenant' },
        @{ InstallDirectory = 'C:relative' }
    )) {
        $before = $script:metadataRequests
        $rejected = $false
        try { & $installer -NonInteractive -SkipLogin @arguments } catch { $rejected = $true }
        Assert ($rejected -and $script:metadataRequests -eq $before) 'Invalid configuration must fail before network or installation.'
    }
    $env:PROCESSOR_ARCHITECTURE = 'x86'
    $env:PROCESSOR_ARCHITEW6432 = ''
    $rejected = $false
    try { & $installer -NonInteractive -SkipLogin } catch { $rejected = $true }
    Assert $rejected 'Unsupported 32-bit Windows architecture was accepted.'
    $env:PROCESSOR_ARCHITECTURE = 'AMD64'

    foreach ($failure in @('badHash', 'duplicateChecksum', 'missingAsset', 'mismatchBinary')) {
        Set-Variable -Name $failure -Scope Script -Value $true
        $before = Get-Content -LiteralPath (Join-Path $destination 'mcp.json') -Raw
        $binaryBefore = (Get-FileHash -LiteralPath (Join-Path $destination 'm365-mcp-windows-local-go.exe')).Hash
        $rejected = $false
        try { & $installer -InstallDirectory $destination -NonInteractive -SkipLogin } catch { $rejected = $true }
        Assert $rejected "Installer accepted $failure."
        Assert ((Get-Content -LiteralPath (Join-Path $destination 'mcp.json') -Raw) -ceq $before) 'Rejected download changed existing configuration.'
        Assert ((Get-FileHash -LiteralPath (Join-Path $destination 'm365-mcp-windows-local-go.exe')).Hash -ceq $binaryBefore) 'Rejected download changed the existing executable.'
        Set-Variable -Name $failure -Scope Script -Value $false
    }
    Assert ([Net.ServicePointManager]::SecurityProtocol -eq $originalProtocol) 'Installer changed the caller TLS settings.'
    Write-Host 'Windows installer checks passed without login or external network calls.'
} finally {
    $env:PROCESSOR_ARCHITECTURE = $originalArchitecture
    $env:PROCESSOR_ARCHITEW6432 = $originalNativeArchitecture
    Remove-Item -LiteralPath $testDirectory -Recurse -Force
}
