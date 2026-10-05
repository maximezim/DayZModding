<#
.SYNOPSIS
    Build (+sign) one or more mods, then launch them in diag or dedicated mode.

.EXAMPLE
    .\tools\build\Build-And-Run.ps1 -ModName MyMod -FilePatching
    .\tools\build\Build-And-Run.ps1 -ModName MyMod -ServerModName MyModServer -Mode Dedicated
#>
[CmdletBinding()]
param(
    [string[]]$ModName = @(),
    [string[]]$ServerModName = @(),
    [ValidateSet('Diag', 'Dedicated')][string]$Mode = 'Diag',
    [switch]$FilePatching,
    [switch]$NoSign,
    [switch]$NoClient,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$all = @($ModName + $ServerModName)
# Dedicated runs verifySignatures=2, so signing is mandatory there.
$sign = (-not $NoSign) -or ($Mode -eq 'Dedicated')

foreach ($m in $all) {
    & (Join-DzPath $PSScriptRoot 'Build-Mod.ps1') -ModName $m -DryRun:$DryRun
    if ($sign) { & (Join-DzPath $PSScriptRoot 'Sign-Mod.ps1') -ModName $m -DryRun:$DryRun }
}

if ($Mode -eq 'Dedicated') {
    if ($all.Count) { & (Join-DzPath $PSScriptRoot 'Deploy-Mod.ps1') -ModName $all -DryRun:$DryRun }
    & (Join-DzPath $PSScriptRoot '..\launch\Start-DedicatedServer.ps1') -Mods $ModName -ServerMods $ServerModName -DryRun:$DryRun
} else {
    & (Join-DzPath $PSScriptRoot '..\launch\Start-DiagLocal.ps1') -Mods $ModName -ServerMods $ServerModName -FilePatching:$FilePatching -NoClient:$NoClient -DryRun:$DryRun
}
