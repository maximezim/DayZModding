<#
.SYNOPSIS
    Packs every PBO of a mod into build\@<ModName>\addons.

.DESCRIPTION
    Source layout (see CLAUDE.md):
        mods\<ModName>\mod.cpp
        mods\<ModName>\addons\<pbo>\config.cpp   (+ optional $PBOPREFIX$)
    Each folder under addons\ becomes one PBO. Folders that contain models,
    animations or worlds (*.p3d, *.rtm, *.wrp) are binarized; all others are
    packed as-is (-packonly), which is the fast path for script/config PBOs.

    Binarization resolves paths through the work drive, so for those PBOs the
    script links P:\<prefix root> -> mods\<ModName>\addons (junction, no admin).

.EXAMPLE
    .\tools\build\Build-Mod.ps1 -ModName MyMod
.EXAMPLE
    .\tools\build\Build-Mod.ps1 -ModName ModTemplate -DryRun
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ModName,
    [string]$ModPath,
    [ValidateSet('addonbuilder', 'pboproject', '')][string]$Packer = '',
    [string]$OutputRoot,
    [switch]$ForceBinarize,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
if (-not $Packer) { $Packer = $cfg.packer }
if (-not $OutputRoot) { $OutputRoot = $paths.BuildDir }

$modDir  = Resolve-DzModSource -ModName $ModName -ModPath $ModPath
$outMod  = Join-DzPath $OutputRoot "@$ModName"
$outAdd  = Join-DzPath $outMod 'addons'
$include = Join-DzPath $PSScriptRoot 'addonbuilder-include.lst'

Write-DzStep "Build $ModName ($Packer)  $modDir -> $outMod"

if ($Packer -eq 'addonbuilder') { Assert-DzTool 'AddonBuilder' $paths.AddonBuilder -DryRun:$DryRun }
else { Assert-DzTool 'pboProject (Mikero)' $paths.PboProject -DryRun:$DryRun }

# Fresh output: stale PBOs from older builds cause confusing load behaviour.
New-Item -ItemType Directory -Force -Path $outAdd | Out-Null
Get-ChildItem -LiteralPath $outAdd -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in '.pbo', '.bisign' } | Remove-Item -Force

$pbos = Get-DzPboDirs -ModDir $modDir
if ($pbos.Count -eq 0) { throw "No PBO folders under $modDir\addons." }

$results = @()
foreach ($pbo in $pbos) {
    $prefix   = Get-DzPboPrefix -PboDir $pbo.FullName -ModName $ModName
    $binarize = $ForceBinarize -or (Test-DzPboNeedsBinarize -PboDir $pbo.FullName)
    if (-not (Test-Path -LiteralPath (Join-DzPath $pbo.FullName 'config.cpp'))) {
        Write-DzWarn "$($pbo.Name): no config.cpp - the engine will ignore this PBO."
    }
    Write-DzInfo "PBO '$($pbo.Name)'  prefix=$prefix  binarize=$binarize"

    $source = $pbo.FullName
    if ($binarize -or $Packer -eq 'pboproject') {
        # Binarize / pboProject resolve everything relative to the work drive.
        if (-not $DryRun -and -not (Test-Path -LiteralPath $paths.WorkDrive)) {
            throw "Work drive $($paths.WorkDrive) is not mounted (needed to binarize '$($pbo.Name)'). Run tools\setup\Initialize-WorkDrive.ps1."
        }
        $prefixRoot = $prefix.Split('\')[0]
        $linkTarget = Join-DzPath $modDir 'addons'
        if ($prefix -eq "$prefixRoot\$($pbo.Name)") {
            Set-DzJunction -Link (Join-DzPath $paths.WorkDrive $prefixRoot) -Target $linkTarget -DryRun:$DryRun
            $source = Join-DzPath $paths.WorkDrive $prefix
        } else {
            Write-DzWarn "Custom prefix '$prefix' - make sure P:\$prefix maps to $($pbo.FullName)."
            $source = Join-DzPath $paths.WorkDrive $prefix
        }
    }

    if ($Packer -eq 'addonbuilder') {
        $abArgs = @($source, $outAdd, "-prefix=$prefix", "-include=$include")
        if ($binarize) {
            $abArgs += @("-project=$($paths.WorkDrive)", '-clear')
        } else {
            $abArgs += '-packonly'
        }
        Invoke-DzTool -FilePath $paths.AddonBuilder -ArgumentList $abArgs -DryRun:$DryRun | Out-Null
    } else {
        # pboProject writes into <+Mod>\addons. -P = no pause (batch mode).
        # Set the engine to DayZ once in the pboProject GUI; it is persisted.
        $ppArgs = @('-P', "-W=$($paths.WorkDrive)", "+Mod=$outMod", $source)
        Invoke-DzTool -FilePath $paths.PboProject -ArgumentList $ppArgs -DryRun:$DryRun | Out-Null
    }

    # Lower-case PBO names: Linux DayZ servers are case-sensitive.
    $expected = Join-DzPath $outAdd ($pbo.Name + '.pbo')
    $lower    = Join-DzPath $outAdd ($pbo.Name.ToLowerInvariant() + '.pbo')
    if (-not $DryRun) {
        if (-not (Test-Path -LiteralPath $expected)) { throw "Packer reported success but $expected is missing." }
        if ($expected -cne $lower) {
            Rename-Item -LiteralPath $expected -NewName ($pbo.Name.ToLowerInvariant() + '.pbo.tmp')
            Rename-Item -LiteralPath "$lower.tmp" -NewName ([System.IO.Path]::GetFileName($lower))
        }
    }
    $results += [pscustomobject]@{ Pbo = [System.IO.Path]::GetFileName($lower); Prefix = $prefix; Binarized = [bool]$binarize }
}

# mod.cpp (+ optional logo/meta files kept next to it) goes to the @mod root.
foreach ($f in Get-ChildItem -LiteralPath $modDir -File) {
    if ($f.Name -notmatch '^(README.*|\.gitkeep)$') { Copy-Item -LiteralPath $f.FullName -Destination $outMod -Force }
}
if (-not (Test-Path -LiteralPath (Join-DzPath $modDir 'mod.cpp'))) { Write-DzWarn 'No mod.cpp - launcher will show the folder name only.' }

$manifest = [pscustomobject]@{
    mod       = $ModName
    source    = $modDir
    packer    = $Packer
    builtAt   = (Get-Date).ToString('s')
    dryRun    = [bool]$DryRun
    pbos      = $results
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-DzPath $outMod 'build-manifest.json') -Encoding UTF8

$results | Format-Table -AutoSize | Out-String | Write-Host
Write-DzOk "Built $outMod"
