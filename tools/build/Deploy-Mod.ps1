<#
.SYNOPSIS
    Copies build\@<ModName> into the dedicated test server and installs its
    .bikey into <server>\keys.

.DESCRIPTION
    The diag workflow (Start-DiagLocal.ps1) loads mods straight from build\,
    so deploying is only needed for the dedicated server.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string[]]$ModName,
    [string]$ServerDir,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$paths = Get-DzPaths
if (-not $ServerDir) { $ServerDir = $paths.ServerDir }
if (-not $DryRun -and -not (Test-Path -LiteralPath (Join-DzPath $ServerDir 'DayZServer_x64.exe'))) {
    throw "No DayZ server in '$ServerDir'. Install it with tools\setup\Install-Toolchain.ps1 -Only DayZServer."
}

foreach ($name in $ModName) {
    $src = Resolve-DzBuiltMod -Mod $name
    $leaf = [System.IO.Path]::GetFileName($src)
    $dst = Join-DzPath $ServerDir $leaf
    Write-DzStep "Deploy $leaf -> $dst"
    if (-not $DryRun -and -not (Test-Path -LiteralPath (Join-DzPath $src 'addons'))) { throw "$src is not built." }

    if ($DryRun) { Write-DzInfo "> robocopy `"$src`" `"$dst`" /MIR" }
    else {
        # /MIR so removed PBOs disappear from the server copy too.
        & robocopy $src $dst /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)." }
    }

    $keySrc = Join-DzPath $src 'keys'
    if (Test-Path -LiteralPath $keySrc) {
        $serverKeys = Join-DzPath $ServerDir 'keys'
        foreach ($k in Get-ChildItem -LiteralPath $keySrc -Filter '*.bikey') {
            if (-not $DryRun) { Copy-Item -LiteralPath $k.FullName -Destination $serverKeys -Force }
            Write-DzOk "key $($k.Name) -> $serverKeys"
        }
    } else {
        Write-DzWarn "$leaf has no keys\ - unsigned mods are rejected when verifySignatures=2."
    }
}
