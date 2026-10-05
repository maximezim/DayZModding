<#
.SYNOPSIS
    Converts every PNG/TGA in a folder to PAA with DayZ Tools' ImageToPAA.

.DESCRIPTION
    ImageToPAA picks the PAA format from the file suffix (_co, _ca, _nohq,
    _smdi, _as ...), so keep the DayZ suffix convention in the source names.
    Skips files whose .paa is newer than the source unless -Force.

.EXAMPLE
    .\tools\assets\Convert-Textures.ps1 -SourceDir build\sky_tex_png -DestDir mods\SKY_Skyline\addons\sky_textures\data
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SourceDir,
    [Parameter(Mandatory)][string]$DestDir,
    [string]$Filter = '*',
    [string]$Exclude = '',
    [switch]$Force,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$paths = Get-DzPaths
Assert-DzTool 'ImageToPAA' $paths.ImageToPAA -DryRun:$DryRun
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

$files = @(Get-ChildItem -LiteralPath $SourceDir -File | Where-Object { $_.Extension -in '.png', '.tga' -and $_.BaseName -like $Filter -and -not ($Exclude -and $_.BaseName -like $Exclude) })
if ($files.Count -eq 0) { throw "No PNG/TGA files in $SourceDir" }
Write-DzStep "ImageToPAA: $($files.Count) file(s) -> $DestDir"
$n = 0
foreach ($f in $files) {
    $dst = Join-DzPath $DestDir ($f.BaseName.ToLowerInvariant() + '.paa')
    if (-not $Force -and (Test-Path -LiteralPath $dst) -and (Get-Item -LiteralPath $dst).LastWriteTime -ge $f.LastWriteTime) { continue }
    Invoke-DzTool -FilePath $paths.ImageToPAA -ArgumentList @($f.FullName, $dst) -DryRun:$DryRun | Out-Null
    if (-not $DryRun -and -not (Test-Path -LiteralPath $dst)) { throw "ImageToPAA produced no $dst" }
    $n++
}
Write-DzOk "$n converted"
