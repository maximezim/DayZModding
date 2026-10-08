<#
.SYNOPSIS
    Signs every PBO in build\@<ModName>\addons with DSSignFile and places the
    public .bikey in build\@<ModName>\keys.

.DESCRIPTION
    The private key lives outside the repository (signing.keyDir in
    workspace.config.json, default %USERPROFILE%\.dayz-keys). Create one with
    tools\setup\New-SigningKey.ps1. This script refuses to use a private key
    located inside the repository.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ModName,
    [string]$KeyName,
    [string]$OutputRoot,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg = Get-DzConfig
if ($KeyName) { $cfg.signing.keyName = $KeyName }
$paths = Get-DzPaths -Config $cfg
if (-not $OutputRoot) { $OutputRoot = $paths.BuildDir }

if (-not $paths.KeyName) { throw 'No signing key configured. Run tools\setup\New-SigningKey.ps1 -KeyName <Tag> first.' }
if (Test-DzPathInRepo $paths.PrivateKey) {
    throw "Private key '$($paths.PrivateKey)' is inside the repository. Move it out (signing.keyDir)."
}
Assert-DzTool 'DSSignFile' $paths.DSSignFile -DryRun:$DryRun
Assert-DzTool 'Private key' $paths.PrivateKey -DryRun:$DryRun
Assert-DzTool 'Public key' $paths.PublicKey -DryRun:$DryRun

$outMod = Join-DzPath $OutputRoot "@$ModName"
$outAdd = Join-DzPath $outMod 'addons'
$pbos = @(Get-ChildItem -LiteralPath $outAdd -Filter '*.pbo' -File -ErrorAction SilentlyContinue)
if ($pbos.Count -eq 0 -and -not $DryRun) { throw "No PBOs in $outAdd. Run Build-Mod.ps1 first." }

Write-DzStep "Sign $ModName with key '$($paths.KeyName)'"
Get-ChildItem -LiteralPath $outAdd -Filter '*.bisign' -File -ErrorAction SilentlyContinue | Remove-Item -Force

foreach ($pbo in $pbos) {
    Invoke-DzTool -FilePath $paths.DSSignFile -ArgumentList @($paths.PrivateKey, $pbo.FullName) -WorkingDirectory $outAdd -DryRun:$DryRun | Out-Null
    $sig = "$($pbo.FullName).$($paths.KeyName).bisign"
    if (-not $DryRun -and -not (Test-Path -LiteralPath $sig)) { throw "Signature not produced: $sig" }
    Write-DzOk ([System.IO.Path]::GetFileName($sig))
}

$keysDir = Join-DzPath $outMod 'keys'
New-Item -ItemType Directory -Force -Path $keysDir | Out-Null
if (-not $DryRun) { Copy-Item -LiteralPath $paths.PublicKey -Destination $keysDir -Force }
Write-DzOk "Public key -> $keysDir"
