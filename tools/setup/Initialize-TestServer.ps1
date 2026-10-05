<#
.SYNOPSIS
    Prepares the local test server: renders server configs with a random
    admin password and copies the vanilla mission for the diag server.

.DESCRIPTION
    - server\templates\serverDZ.*.cfg -> server\serverDZ.*.cfg (git-ignored)
    - <serverDir>\mpmissions\<mission> -> server\mpmissions\<mission> (git-ignored;
      vanilla Bohemia content, used by DayZDiag via -mission=)
    - creates server\profiles\{diag-server,diag-client,dedicated}
    Re-run with -Force to refresh the mission after a game update (wipes its storage).
#>
[CmdletBinding()]
param(
    [string]$Mission,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
$repo  = Get-DzRepoRoot
if (-not $Mission) { $Mission = $cfg.server.mission }
$serverRoot = Join-DzPath $repo 'server'

Write-DzStep 'Render server configs'
foreach ($kind in 'diag', 'dedicated') {
    $dst = Join-DzPath $serverRoot "serverDZ.$kind.cfg"
    if ((Test-Path -LiteralPath $dst) -and -not $Force) { Write-DzOk "$dst exists"; continue }
    $bytes = New-Object byte[] 18
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $pw = [Convert]::ToBase64String($bytes) -replace '[^A-Za-z0-9]', 'x'
    $text = Get-Content -Raw -LiteralPath (Join-DzPath $serverRoot 'templates' "serverDZ.$kind.cfg")
    $text = $text.Replace('__ADMIN_PASSWORD__', $pw).Replace('__MISSION__', $Mission)
    Set-Content -LiteralPath $dst -Value $text -Encoding ASCII
    Write-DzOk "$dst (admin password generated; file is git-ignored)"
}

Write-DzStep "Copy vanilla mission '$Mission' for the diag server"
$src = Join-DzPath $paths.ServerDir 'mpmissions' $Mission
$dstMission = Join-DzPath $serverRoot 'mpmissions' $Mission
if ((Test-Path -LiteralPath $dstMission) -and -not $Force) { Write-DzOk "$dstMission exists" }
elseif (-not (Test-Path -LiteralPath $src)) {
    Write-DzWarn "Vanilla mission not found at $src. Install the DayZ Server first (Install-Toolchain.ps1 -Only DayZServer)."
} else {
    if (Test-Path -LiteralPath $dstMission) { Remove-Item -LiteralPath $dstMission -Recurse -Force }
    New-Item -ItemType Directory -Force -Path (Split-Path $dstMission) | Out-Null
    Copy-Item -LiteralPath $src -Destination $dstMission -Recurse
    $storage = Join-DzPath $dstMission 'storage_1'
    if (Test-Path -LiteralPath $storage) { Remove-Item -LiteralPath $storage -Recurse -Force }
    Write-DzOk "$dstMission"
}
foreach ($required in 'init.c', 'db\types.xml', 'cfgeconomycore.xml') {
    if (Test-Path -LiteralPath (Join-DzPath $dstMission $required)) { Write-DzOk "mission has $required" }
    else { Write-DzWarn "mission lacks $required" }
}

foreach ($p in 'diag-server', 'diag-client', 'dedicated') {
    New-Item -ItemType Directory -Force -Path (Join-DzPath $serverRoot 'profiles' $p) | Out-Null
}
Write-DzOk 'Profiles ready under server\profiles'
