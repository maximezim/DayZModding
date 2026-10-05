<#
.SYNOPSIS
    Mounts the P: work drive via DayZ Tools' WorkDrive.exe and extracts the
    game scripts/data onto it as read-only reference.

.DESCRIPTION
    WorkDrive.exe (DayZ Tools\Bin\WorkDrive) is the same tool the DayZ Tools
    launcher's "Mount Drive" / "Extract Game Data" buttons run:
        WorkDrive.exe /Mount <letter> <sourceDir>
        WorkDrive.exe /ExtractGameData
    If WorkDrive.exe fails, falls back to `subst` for the mount (not
    persistent across reboots - re-run this script or use DayZ Tools).

    Extraction takes a long time and ~15+ GB. Re-run with -ExtractOnly after
    every major game update so P:\scripts matches the live game.
#>
[CmdletBinding()]
param(
    [switch]$MountOnly,
    [switch]$ExtractOnly,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$paths  = Get-DzPaths
$letter = $paths.WorkDrive.Substring(0, 1)
$drive  = $paths.WorkDrive
Assert-DzTool 'WorkDrive.exe (DayZ Tools)' $paths.WorkDriveExe

if (-not $ExtractOnly) {
    Write-DzStep "Mount $drive from $($paths.WorkDriveSrc)"
    if (Test-Path -LiteralPath $drive) { Write-DzOk "$drive already mounted" }
    else {
        New-Item -ItemType Directory -Force -Path $paths.WorkDriveSrc | Out-Null
        try {
            Invoke-DzTool -FilePath $paths.WorkDriveExe -ArgumentList @('/Mount', $letter, $paths.WorkDriveSrc) -WorkingDirectory (Split-Path $paths.WorkDriveExe) | Out-Null
        } catch { Write-DzWarn "WorkDrive.exe /Mount failed: $_" }
        if (-not (Test-Path -LiteralPath $drive)) {
            Write-DzWarn "Falling back to: subst $letter`: `"$($paths.WorkDriveSrc)`""
            & subst "$letter`:" $paths.WorkDriveSrc
        }
        if (-not (Test-Path -LiteralPath $drive)) { throw "Could not mount $drive. Use DayZ Tools > Settings > set Work drive, then 'Mount Drive'." }
        Write-DzOk "$drive mounted"
    }
}

if (-not $MountOnly) {
    $scripts = Join-DzPath $drive 'scripts'
    if ((Test-Path -LiteralPath $scripts) -and -not $Force) {
        Write-DzOk "$scripts exists - skip extraction (use -Force after a game update)"
    } else {
        Write-DzStep 'Extract game data to the work drive (slow, ~15+ GB)'
        Invoke-DzTool -FilePath $paths.WorkDriveExe -ArgumentList @('/ExtractGameData') -WorkingDirectory (Split-Path $paths.WorkDriveExe) | Out-Null
    }
    $n = @(Get-ChildItem -LiteralPath $scripts -Recurse -Filter '*.c' -File -ErrorAction SilentlyContinue).Count
    if ($n -eq 0) { throw "No .c files under $scripts after extraction. Use DayZ Tools > 'Extract Game Data' and check DayZ Tools\Bin\Logs." }
    foreach ($m in '3_Game', '4_World', '5_Mission') {
        if (Test-Path -LiteralPath (Join-DzPath $scripts $m)) { Write-DzOk "$scripts\$m" } else { Write-DzWarn "missing $scripts\$m" }
    }
    Write-DzOk "$n vanilla script files available as reference (read-only: never edit P:\scripts or P:\DZ)"
}
