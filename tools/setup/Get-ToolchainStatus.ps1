<#
.SYNOPSIS
    Detects every component of the DayZ modding toolchain. Changes nothing.

.DESCRIPTION
    Prints a status table and writes build\toolchain-status.json (used when
    filling SETUP_REPORT.md). Exit code 0 = everything required is present.
#>
[CmdletBinding()]
param([switch]$Json)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
$rows  = New-Object System.Collections.Generic.List[object]

function Add-Row([string]$Name, [bool]$Ok, [string]$Version, [string]$Detail, [bool]$Required = $true) {
    $rows.Add([pscustomobject]@{ Component = $Name; Ok = $Ok; Required = $Required; Version = $Version; Detail = $Detail })
}
function Get-FileVer([string]$p) {
    if ($p -and (Test-Path -LiteralPath $p)) {
        $v = (Get-Item -LiteralPath $p).VersionInfo
        if ($v.ProductVersion) { return $v.ProductVersion.Trim() }
        return 'present'
    }
    return ''
}
function Get-CmdOutput([string]$exe, [string[]]$cmdArgs) {
    $path = Find-DzOnPath $exe
    if (-not $path) { return '' }
    try { return ((& $path @cmdArgs 2>&1) | Select-Object -First 1 | Out-String).Trim() } catch { return '' }
}

# --- Steam + game content
$steam = Get-DzSteamDir -Config $cfg
Add-Row 'Steam' ([bool]$steam) (Get-FileVer (Join-DzPath $steam 'steam.exe')) $steam
Add-Row 'DayZ (221100)' ([bool]$paths.DayZDir) (Get-DzAppVersion -AppId $AppIds.DayZ) $paths.DayZDir
Add-Row 'DayZDiag_x64.exe' ([bool](Get-FileVer $paths.DayZDiag)) (Get-FileVer $paths.DayZDiag) $paths.DayZDiag
Add-Row 'DayZ Tools (830640)' ([bool]$paths.DayZToolsDir) (Get-DzAppVersion -AppId $AppIds.DayZTools) $paths.DayZToolsDir
foreach ($t in 'AddonBuilder', 'DSSignFile', 'DSCreateKey', 'ImageToPAA', 'TexView2', 'WorkDriveExe', 'CfgConvert') {
    $p = $paths.$t
    Add-Row "  $t" ([bool](Get-FileVer $p)) (Get-FileVer $p) $p
}
$wb = ''; $ob = ''
if ($paths.DayZToolsDir) {
    $wb = Get-ChildItem -LiteralPath $paths.DayZToolsDir -Recurse -Filter 'workbenchApp.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
    $ob = Get-ChildItem -LiteralPath $paths.DayZToolsDir -Recurse -Filter 'ObjectBuilder.exe' -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName
}
Add-Row '  Workbench' ([bool]$wb) (Get-FileVer $wb) $wb
Add-Row '  Object Builder' ([bool]$ob) (Get-FileVer $ob) $ob
Add-Row 'DayZ Server (223350)' ([bool](Get-FileVer $paths.DayZServerExe)) (Get-FileVer $paths.DayZServerExe) $paths.ServerDir
$steamcmd = Join-DzPath $paths.SteamCmdDir 'steamcmd.exe'
Add-Row 'SteamCMD' (Test-Path -LiteralPath $steamcmd) '' $steamcmd

# --- Work drive
$pMounted = Test-Path -LiteralPath $paths.WorkDrive
$scriptsDir = Join-DzPath $paths.WorkDrive 'scripts'
$scriptCount = 0
if ($pMounted -and (Test-Path -LiteralPath $scriptsDir)) {
    $scriptCount = @(Get-ChildItem -LiteralPath $scriptsDir -Recurse -Filter '*.c' -File -ErrorAction SilentlyContinue).Count
}
Add-Row "Work drive $($paths.WorkDrive)" $pMounted '' $paths.WorkDriveSrc
Add-Row '  Extracted game scripts' ($scriptCount -gt 0) "$scriptCount .c files" $scriptsDir
Add-Row '  Extracted game data (P:\DZ)' ($pMounted -and (Test-Path -LiteralPath (Join-DzPath $paths.WorkDrive 'DZ'))) '' (Join-DzPath $paths.WorkDrive 'DZ')

# --- Dev tools
$git = Get-CmdOutput 'git' @('--version')
Add-Row 'Git' ([bool]$git) $git (Find-DzOnPath 'git')
$lfs = Get-CmdOutput 'git' @('lfs', 'version')
Add-Row 'Git LFS' ($lfs -like 'git-lfs*') $lfs ''
$hooks = ''
if ($git) { $hooks = (& git -C (Get-DzRepoRoot) config core.hooksPath 2>$null) }
Add-Row '  repo hooksPath=.githooks' ($hooks -eq '.githooks') $hooks '' $false

$code = Find-DzOnPath 'code-insiders'
if (-not $code) { $code = Find-DzOnPath 'code' }
if (-not $code) { $code = Find-DzOnPath 'code.cmd' }
$codeVer = ''; $exts = @()
if ($code) {
    $codeVer = ((& $code --version 2>$null) | Select-Object -First 1)
    $exts = @(& $code --list-extensions 2>$null)
}
Add-Row 'VS Code' ([bool]$code) $codeVer $code
$wanted = (Get-Content -Raw (Join-DzPath (Get-DzRepoRoot) '.vscode\extensions.json') | ConvertFrom-Json).recommendations
foreach ($e in $wanted) { Add-Row "  ext $e" ($exts -contains $e) '' '' }

$blender = Find-DzOnPath 'blender'
if (-not $blender) {
    $bfRoot = Join-DzPath $env:ProgramFiles 'Blender Foundation'
    if ($bfRoot -and (Test-Path -LiteralPath $bfRoot)) {
        $bf = Get-ChildItem -LiteralPath $bfRoot -Recurse -Filter 'blender.exe' -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
        if ($bf) { $blender = $bf.FullName }
    }
}
$blenderVer = ''
if ($blender) { $blenderVer = ((& $blender --version 2>$null) | Select-Object -First 1) }
Add-Row 'Blender' ([bool]$blender) $blenderVer $blender
$addonHit = ''
$bdir = Join-DzPath $env:APPDATA 'Blender Foundation\Blender'
if ($bdir -and (Test-Path -LiteralPath $bdir)) {
    $addonHit = Get-ChildItem -LiteralPath $bdir -Recurse -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^(ArmaToolbox|ArmAToolbox|Arma3ObjectBuilder|DZObjectBuilder|DayZObjectBuilder)' } |
        Select-Object -First 1 -ExpandProperty FullName
}
Add-Row '  Blender P3D add-on (DZOB / Arma Toolbox)' ([bool]$addonHit) '' $addonHit

$py = Get-CmdOutput 'python' @('--version')
if ($py -notlike 'Python 3*') { $py = Get-CmdOutput 'py' @('-3', '--version') }
Add-Row 'Python 3' ($py -like 'Python 3*') $py ''
$pil = ''
if ($py -like 'Python 3*') { $pil = Get-CmdOutput 'python' @('-c', 'import PIL;print(PIL.__version__)') }
Add-Row '  Pillow' ($pil -match '^\d') $pil ''

Add-Row "Mikero pboProject" ([bool](Get-FileVer $paths.PboProject)) (Get-FileVer $paths.PboProject) $paths.PboProject $false
Add-Row "Mikero DePbo" ([bool](Get-FileVer $paths.DePbo)) (Get-FileVer $paths.DePbo) $paths.DePbo $false

# --- Signing key
$keyOk = $paths.PrivateKey -and (Test-Path -LiteralPath $paths.PrivateKey) -and (Test-Path -LiteralPath $paths.PublicKey)
Add-Row 'Signing keypair' ([bool]$keyOk) $paths.KeyName $paths.KeyDir

# --- Test server files
$repo = Get-DzRepoRoot
Add-Row 'server\serverDZ.diag.cfg' (Test-Path (Join-DzPath $repo 'server' 'serverDZ.diag.cfg')) '' ''
Add-Row 'server\mpmissions\<mission>' (Test-Path (Join-DzPath $repo 'server' 'mpmissions' $cfg.server.mission)) '' $cfg.server.mission

New-Item -ItemType Directory -Force -Path $paths.BuildDir | Out-Null
$out = Join-DzPath $paths.BuildDir 'toolchain-status.json'
$rows | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath $out -Encoding UTF8

if ($Json) { $rows | ConvertTo-Json -Depth 3 }
else {
    foreach ($r in $rows) {
        $mark = if ($r.Ok) { '[OK]  ' } elseif ($r.Required) { '[MISS]' } else { '[opt] ' }
        $color = if ($r.Ok) { 'Green' } elseif ($r.Required) { 'Red' } else { 'Yellow' }
        Write-Host ("{0} {1,-44} {2,-28} {3}" -f $mark, $r.Component, $r.Version, $r.Detail) -ForegroundColor $color
    }
    Write-Host "`nSaved $out"
}
$missing = @($rows | Where-Object { $_.Required -and -not $_.Ok })
exit ([int]($missing.Count -gt 0))
