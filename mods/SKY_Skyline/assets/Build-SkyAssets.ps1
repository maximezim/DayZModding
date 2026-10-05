<#
.SYNOPSIS
    SKY_Skyline asset pipeline on Windows: textures -> PAA, (models), configs, checks.

.DESCRIPTION
    1. python assets/textures/gen_textures.py -> build\sky_tex_png (deterministic)
    2. ImageToPAA -> addons\sky_textures\data (trims) and addons\sky_items\data (keycards)
    3. -Models: re-export P3Ds with Blender + Arma Toolbox (needs -Blender and
       ARMATOOLBOX_PATH = folder containing the ArmaToolbox package)
    4. gen_configs.py, economy/gen_economy.py, check_assets.py, layout self-test
    5. Verifies that every vanilla dz\ path referenced by models/rvmats exists on P:
       (penetration rvmats, env map, roadway surfaces - see skyspec.PENETRATION)
    Then build normally: tools\build\Build-Mod.ps1 -ModName SKY_Skyline

.EXAMPLE
    .\mods\SKY_Skyline\assets\Build-SkyAssets.ps1
    .\mods\SKY_Skyline\assets\Build-SkyAssets.ps1 -Models -Blender "C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"
#>
[CmdletBinding()]
param(
    [switch]$Models,
    [string]$Blender = 'blender',
    [string]$Python = 'python',
    [switch]$SkipPChecks
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
Import-Module (Join-Path $repo 'tools\lib\DzCommon.psm1') -Force
$mod = Join-Path $repo 'mods\SKY_Skyline'
$png = Join-Path $repo 'build\sky_tex_png'

function Run-Py([string[]]$a) {
    & $Python @a
    if ($LASTEXITCODE -ne 0) { throw "python $($a -join ' ') failed ($LASTEXITCODE)" }
}

Write-DzStep 'Generate texture sources'
Run-Py @((Join-Path $mod 'assets\textures\gen_textures.py'), '--out', $png)

Write-DzStep 'Convert to PAA'
$conv = Join-Path $repo 'tools\assets\Convert-Textures.ps1'
& $conv -SourceDir $png -DestDir (Join-Path $mod 'addons\sky_textures\data') -Exclude 'sky_keycard*'
& $conv -SourceDir $png -DestDir (Join-Path $mod 'addons\sky_items\data') -Filter 'sky_keycard*'

if ($Models) {
    Write-DzStep 'Export P3D models (Blender + Arma Toolbox)'
    if (-not $env:ARMATOOLBOX_PATH) { throw 'Set ARMATOOLBOX_PATH to the folder containing the ArmaToolbox package.' }
    & $Blender -b --factory-startup --python-exit-code 1 -P (Join-Path $mod 'assets\blender\build_towera.py') -- --out (Join-Path $mod 'addons')
    if ($LASTEXITCODE -ne 0) { throw 'Blender export failed' }
    & $Blender -b --factory-startup --python-exit-code 1 -P (Join-Path $mod 'assets\blender\test_towera.py')
    if ($LASTEXITCODE -ne 0) { throw 'Tower A geometry tests failed' }
    foreach ($gen in 'build_kit.py', 'build_props.py', 'build_floors.py') {
        $g = Join-Path $mod "assets\blender\$gen"
        if (Test-Path $g) {
            & $Blender -b --factory-startup --python-exit-code 1 -P $g -- --out (Join-Path $mod 'addons')
            if ($LASTEXITCODE -ne 0) { throw "$gen export failed" }
        }
    }
    & $Blender -b --factory-startup --python-exit-code 1 -P (Join-Path $mod 'assets\blender\test_kit.py')
    if ($LASTEXITCODE -ne 0) { throw 'Kit geometry tests failed' }
}

Write-DzStep 'Configs, economy, checks'
Run-Py @((Join-Path $mod 'assets\gen_configs.py'))
Run-Py @((Join-Path $mod 'assets\gen_manifest.py'))
Run-Py @((Join-Path $mod 'economy\gen_economy.py'))
Run-Py @((Join-Path $mod 'assets\check_assets.py'))
Run-Py @((Join-Path $mod 'placement\tests\test_sky_layout.py'))
if (Test-Path 'P:\scripts') {
    Run-Py @((Join-Path $repo 'tools\assets\enscript_xref.py'), '--vanilla', 'P:\scripts', '--mod', (Join-Path $mod 'addons\sky_scripts\scripts'))
}

if (-not $SkipPChecks) {
    Write-DzStep 'Vanilla references on P:'
    if (-not (Test-Path 'P:\DZ')) { throw 'P:\DZ missing - run tools\setup\Initialize-WorkDrive.ps1 (or -SkipPChecks)' }
    $refs = New-Object System.Collections.Generic.HashSet[string]
    foreach ($p3d in Get-ChildItem (Join-Path $mod 'addons') -Recurse -Filter *.p3d) {
        $j = & $Python (Join-Path $repo 'tools\assets\p3d_inspect.py') $p3d.FullName --json | ConvertFrom-Json
        foreach ($prop in $j.PSObject.Properties) { foreach ($l in $prop.Value) { foreach ($t in @($l.textures) + @($l.materials)) { if ($t -like 'dz\*') { [void]$refs.Add($t) } } } }
    }
    foreach ($rv in Get-ChildItem (Join-Path $mod 'addons') -Recurse -Filter *.rvmat) {
        foreach ($m in [regex]::Matches((Get-Content -Raw $rv.FullName), '"(dz\\[^"]+)"')) { [void]$refs.Add($m.Groups[1].Value) }
    }
    $missing = 0
    foreach ($r in $refs) {
        # .tga/.png references resolve to the .paa on P: after extraction
        $cands = @("P:\$r", ("P:\$r" -replace '\.(tga|png)$', '.paa'))
        if ($cands | Where-Object { Test-Path -LiteralPath $_ }) { Write-DzOk $r } else { Write-DzFail "$r not found on P:"; $missing++ }
    }
    if ($missing) { throw "$missing vanilla reference(s) missing - fix skyspec.PENETRATION / rvmat env paths" }
}
Write-DzOk 'SKY assets ready - next: tools\build\Build-Mod.ps1 -ModName SKY_Skyline; Sign-Mod.ps1; Build-And-Run.ps1'
