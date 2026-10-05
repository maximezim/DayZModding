<#
.SYNOPSIS
    Launches a DayZDiag_x64 server plus a DayZDiag_x64 client connected to it.

.DESCRIPTION
    Mods are loaded from build\@<Name> (or any path you pass). With
    -FilePatching the client and server also read loose files from the mod
    source tree through a junction <DayZ>\<prefix root> -> mods\<Name>\addons,
    so script edits apply on reconnect without repacking. config.cpp changes
    still need a rebuild.

    Profiles/logs: server\profiles\diag-server and server\profiles\diag-client.

.EXAMPLE
    .\tools\launch\Start-DiagLocal.ps1                       # vanilla, no mods
    .\tools\launch\Start-DiagLocal.ps1 -Mods MyMod -FilePatching
    .\tools\launch\Start-DiagLocal.ps1 -Mods MyMod -ServerMods MyModServer -NoClient
#>
[CmdletBinding()]
param(
    [string[]]$Mods = @(),
    [string[]]$ServerMods = @(),
    [switch]$FilePatching,
    [switch]$NoClient,
    [switch]$NoServer,
    [int]$Port = 0,
    [string]$PlayerName = 'Survivor',
    [int]$ClientDelaySeconds = 25,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
$repo  = Get-DzRepoRoot
if (-not $Port) { $Port = [int]$cfg.server.port }
Assert-DzTool 'DayZDiag_x64.exe' $paths.DayZDiag -DryRun:$DryRun

$serverCfg = Join-DzPath $repo 'server' 'serverDZ.diag.cfg'
$mission   = Join-DzPath $repo 'server' 'mpmissions' $cfg.server.mission
if (-not $DryRun -and -not $NoServer) {
    if (-not (Test-Path -LiteralPath $serverCfg)) { throw "Missing $serverCfg. Run tools\setup\Initialize-TestServer.ps1." }
    if (-not (Test-Path -LiteralPath $mission))   { throw "Missing mission $mission. Run tools\setup\Initialize-TestServer.ps1." }
}

$modPaths    = @($Mods | ForEach-Object { Resolve-DzBuiltMod -Mod $_ })
$serverPaths = @($ServerMods | ForEach-Object { Resolve-DzBuiltMod -Mod $_ })
foreach ($m in $modPaths + $serverPaths) {
    if (-not $DryRun -and -not (Test-Path -LiteralPath (Join-DzPath $m 'addons'))) { throw "Mod not built: $m (run tools\build\Build-Mod.ps1)." }
}

if ($FilePatching) {
    # Expose each mod's source under its prefix root inside the game folder.
    foreach ($m in $Mods + $ServerMods) {
        $name = ([System.IO.Path]::GetFileName($m)).TrimStart('@')
        $src = Join-DzPath $repo 'mods' $name
        if (-not (Test-Path -LiteralPath $src)) { Write-DzWarn "No source for '$name' in mods\ - file patching skipped for it."; continue }
        $roots = @(Get-DzPboDirs -ModDir $src | ForEach-Object { (Get-DzPboPrefix -PboDir $_.FullName -ModName $name).Split('\')[0] } | Sort-Object -Unique)
        foreach ($root in $roots) {
            if ($root -ne $name) { Write-DzWarn "Custom prefix root '$root' for '$name' - link it manually."; continue }
            Set-DzJunction -Link (Join-DzPath $paths.DayZDir $root) -Target (Join-DzPath $src 'addons') -DryRun:$DryRun
        }
    }
}

$common = @('-dologs', '-adminlog', '-netlog', '-freezecheck')
if ($FilePatching) { $common += '-filePatching' }
$modArg       = if ($modPaths.Count)    { '-mod=' + ($modPaths -join ';') } else { '' }
$serverModArg = if ($serverPaths.Count) { '-servermod=' + ($serverPaths -join ';') } else { '' }

if (-not $NoServer) {
    $srvProfile = Join-DzPath $repo 'server' 'profiles' 'diag-server'
    New-Item -ItemType Directory -Force -Path $srvProfile | Out-Null
    Write-DzStep "Starting DayZDiag server on port $Port"
    $srvArgs = @('-server', "-config=$serverCfg", "-mission=$mission", "-port=$Port", "-profiles=$srvProfile", $modArg, $serverModArg) + $common
    Invoke-DzTool -FilePath $paths.DayZDiag -ArgumentList $srvArgs -WorkingDirectory $paths.DayZDir -NoWait -DryRun:$DryRun | Out-Null
}

if (-not $NoClient) {
    if (-not $NoServer -and -not $DryRun) {
        Write-DzInfo "Waiting $ClientDelaySeconds s for the server to come up..."
        Start-Sleep -Seconds $ClientDelaySeconds
    }
    $cliProfile = Join-DzPath $repo 'server' 'profiles' 'diag-client'
    New-Item -ItemType Directory -Force -Path $cliProfile | Out-Null
    Write-DzStep 'Starting DayZDiag client'
    $cliArgs = @('-connect=127.0.0.1', "-port=$Port", "-name=$PlayerName", "-profiles=$cliProfile", $modArg, '-dologs')
    if ($FilePatching) { $cliArgs += '-filePatching' }
    Invoke-DzTool -FilePath $paths.DayZDiag -ArgumentList $cliArgs -WorkingDirectory $paths.DayZDir -NoWait -DryRun:$DryRun | Out-Null
}
Write-DzOk "Logs: server\profiles\diag-server, server\profiles\diag-client"
