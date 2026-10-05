<#
.SYNOPSIS
    Starts DayZServer_x64.exe with -mod / -servermod, production-like settings.

.DESCRIPTION
    Mods must have been deployed into the server folder first
    (tools\build\Deploy-Mod.ps1); they are passed as @Name relative to it.
    Uses server\serverDZ.dedicated.cfg (verifySignatures=2, BattlEye=1).
    Connect with the retail client via the launcher, or with DayZDiag only if
    you also relax verifySignatures/BattlEye.

.EXAMPLE
    .\tools\launch\Start-DedicatedServer.ps1                   # vanilla smoke test
    .\tools\launch\Start-DedicatedServer.ps1 -Mods MyMod -ServerMods MyModServer
#>
[CmdletBinding()]
param(
    [string[]]$Mods = @(),
    [string[]]$ServerMods = @(),
    [int]$Port = 0,
    [string]$Config,
    [string]$ServerDir,
    [switch]$Wait,
    [string[]]$ExtraArgs = @(),     # e.g. '-limitFPS=1000' for the FPS protocol (verify the parameter, B12)
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
$repo  = Get-DzRepoRoot
if (-not $Port) { $Port = [int]$cfg.server.port }
if (-not $ServerDir) { $ServerDir = $paths.ServerDir }
if (-not $Config) { $Config = Join-DzPath $repo 'server' 'serverDZ.dedicated.cfg' }
$exe = Join-DzPath $ServerDir 'DayZServer_x64.exe'
Assert-DzTool 'DayZServer_x64.exe' $exe -DryRun:$DryRun
if (-not $DryRun -and -not (Test-Path -LiteralPath $Config)) { throw "Missing $Config. Run tools\setup\Initialize-TestServer.ps1." }

function ConvertTo-ServerModList([string[]]$names) {
    $list = foreach ($n in $names) {
        $leaf = '@' + ([System.IO.Path]::GetFileName($n)).TrimStart('@')
        if (-not $DryRun -and -not (Test-Path -LiteralPath (Join-DzPath $ServerDir $leaf))) {
            throw "$leaf is not deployed in $ServerDir (run tools\build\Deploy-Mod.ps1 -ModName $($leaf.TrimStart('@')))."
        }
        $leaf
    }
    return ($list -join ';')
}

$profileDir = Join-DzPath $repo 'server' 'profiles' 'dedicated'
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

$srvArgs = @("-config=$Config", "-port=$Port", "-profiles=$profileDir", '-dologs', '-adminlog', '-netlog', '-freezecheck')
if ($Mods.Count)       { $srvArgs += '-mod=' + (ConvertTo-ServerModList $Mods) }
if ($ServerMods.Count) { $srvArgs += '-servermod=' + (ConvertTo-ServerModList $ServerMods) }
$srvArgs += @($ExtraArgs | Where-Object { $_ })

Write-DzStep "Starting dedicated server ($ServerDir) on port $Port"
if ($Wait) {
    Invoke-DzTool -FilePath $exe -ArgumentList $srvArgs -WorkingDirectory $ServerDir -DryRun:$DryRun | Out-Null
} else {
    $proc = Invoke-DzTool -FilePath $exe -ArgumentList $srvArgs -WorkingDirectory $ServerDir -NoWait -DryRun:$DryRun
    if ($proc) { Write-DzOk "PID $($proc.Id). Logs: $profileDir" }
}
