<#
.SYNOPSIS
    Offline self-test of the workspace scripts. Needs no game, no DayZ Tools.

.DESCRIPTION
    Runs every build/launch script in -DryRun mode against temporary copies
    of the template and asserts on the commands they would run. Works on
    Windows PowerShell 5.1 and PowerShell 7 (incl. Linux CI).
    Exit code = number of failed assertions.
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$repo  = Get-DzRepoRoot
$build = Join-DzPath $repo 'tools' 'build'
$tmp   = Join-DzPath ([System.IO.Path]::GetTempPath()) ('dz-selftest-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
New-Item -ItemType Directory -Path $tmp | Out-Null
$script:fail = 0

function Check([string]$name, [bool]$cond, [string]$detail = '') {
    if ($cond) { Write-DzOk $name } else { $script:fail++; Write-DzFail "$name $detail" }
}
function Run([scriptblock]$sb) {
    # Capture Write-Host (stream 6) + output as one string.
    return ((& $sb 6>&1 2>&1) | Out-String)
}

try {
    Write-DzStep 'Parse all scripts'
    foreach ($f in Get-ChildItem -LiteralPath (Join-DzPath $repo 'tools') -Recurse -File | Where-Object { $_.Extension -in '.ps1', '.psm1' }) {
        $tokens = $null; $errs = $null
        [void][System.Management.Automation.Language.Parser]::ParseFile($f.FullName, [ref]$tokens, [ref]$errs)
        Check "parse $($f.Name)" (-not $errs) ($errs | Out-String)
    }

    Write-DzStep 'New-Mod scaffolds from the template'
    $mods = Join-DzPath $tmp 'mods'
    Run { & (Join-DzPath $build 'New-Mod.ps1') -ModName SelfTestMod -Author 'tester' -DestinationRoot $mods } | Out-Null
    $cfgCpp = Get-Content -Raw (Join-DzPath $mods 'SelfTestMod' 'addons' 'scripts' 'config.cpp')
    Check 'template name replaced in config.cpp' ($cfgCpp -match 'class SelfTestMod_Scripts' -and $cfgCpp -notmatch 'ModTemplate')
    Check 'author written to mod.cpp' ((Get-Content -Raw (Join-DzPath $mods 'SelfTestMod' 'mod.cpp')) -match 'author = "tester";')
    $bytes = [System.IO.File]::ReadAllBytes((Join-DzPath $mods 'SelfTestMod' 'addons' 'scripts' 'config.cpp'))
    Check 'config.cpp has no BOM' (-not ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB))

    Write-DzStep 'Build-Mod: pack-only script PBO'
    $out = Join-DzPath $tmp 'build'
    $modDir = Join-DzPath $mods 'SelfTestMod'
    $o = Run { & (Join-DzPath $build 'Build-Mod.ps1') -ModName SelfTestMod -ModPath $modDir -OutputRoot $out -DryRun }
    Check 'uses -packonly' ($o -match '-packonly')
    Check 'prefix SelfTestMod\scripts' ($o -match [regex]::Escape('-prefix=SelfTestMod\scripts'))
    $manifest = Get-Content -Raw (Join-DzPath $out '@SelfTestMod' 'build-manifest.json') | ConvertFrom-Json
    Check 'manifest lists scripts.pbo' (@($manifest.pbos | Where-Object { $_.Pbo -eq 'scripts.pbo' }).Count -eq 1)
    Check 'mod.cpp copied to @mod' (Test-Path (Join-DzPath $out '@SelfTestMod' 'mod.cpp'))

    Write-DzStep 'Build-Mod: data PBO with a model is binarized via the work drive'
    $data = Join-DzPath $modDir 'addons' 'Data'
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    Set-Content -LiteralPath (Join-DzPath $data 'config.cpp') -Value 'class CfgPatches {};'
    Set-Content -LiteralPath (Join-DzPath $data 'dummy.p3d') -Value 'not a real model'
    $o = Run { & (Join-DzPath $build 'Build-Mod.ps1') -ModName SelfTestMod -ModPath $modDir -OutputRoot $out -DryRun }
    Check 'binarize uses -project=' ($o -match '-project=P:')
    Check 'binarize source is on P:' ($o -match 'P:[\\/]+SelfTestMod[\\/]Data')
    Check 'junction to work drive planned' ($o -match 'junction')
    Check 'pbo names lower-cased' ((Get-Content -Raw (Join-DzPath $out '@SelfTestMod' 'build-manifest.json')) -match '"data.pbo"')

    Write-DzStep 'Build-Mod: $PBOPREFIX$ wins'
    Set-Content -LiteralPath (Join-DzPath $modDir 'addons' 'scripts' '$PBOPREFIX$') -Value 'Custom\Prefix\scripts'
    $o = Run { & (Join-DzPath $build 'Build-Mod.ps1') -ModName SelfTestMod -ModPath $modDir -OutputRoot $out -DryRun }
    Check 'custom prefix honoured' ($o -match [regex]::Escape('-prefix=Custom\Prefix\scripts'))

    Write-DzStep 'Build-Mod: pboProject packer'
    $o = Run { & (Join-DzPath $build 'Build-Mod.ps1') -ModName SelfTestMod -ModPath $modDir -OutputRoot $out -Packer pboproject -DryRun }
    Check 'pboProject batch flags' ($o -match '-P -W=P:' -and $o -match '\+Mod=')

    Write-DzStep 'Sign-Mod'
    $o = Run { & (Join-DzPath $build 'Sign-Mod.ps1') -ModName SelfTestMod -KeyName SelfTestKey -OutputRoot $out -DryRun }
    Check 'sign step runs with key name' ($o -match "key 'SelfTestKey'")
    Check 'public key folder created' (Test-Path (Join-DzPath $out '@SelfTestMod' 'keys'))
    $threw = $false
    try { Run { & (Join-DzPath $build 'Sign-Mod.ps1') -ModName SelfTestMod -OutputRoot $out -DryRun } | Out-Null } catch { $threw = $_.ToString() -match 'No signing key' }
    Check 'refuses to sign without a configured key' $threw

    Write-DzStep 'Launchers'
    $launch = Join-DzPath $repo 'tools' 'launch'
    $o = Run { & (Join-DzPath $launch 'Start-DiagLocal.ps1') -Mods (Join-DzPath $out '@SelfTestMod') -ServerMods (Join-DzPath $out '@SelfTestMod') -DryRun }
    Check 'diag server flags' ($o -match '-server' -and $o -match '-mission=' -and $o -match '-config=' -and $o -match '-servermod=')
    Check 'diag client connects locally' ($o -match '-connect=127\.0\.0\.1')
    Check 'diag without -filePatching by default' ($o -notmatch '-filePatching')
    $o = Run { & (Join-DzPath $launch 'Start-DiagLocal.ps1') -NoClient -FilePatching -DryRun }
    Check 'diag -filePatching passes through' ($o -match '-filePatching')
    $o = Run { & (Join-DzPath $launch 'Start-DedicatedServer.ps1') -Mods SelfTestMod -ServerMods SrvMod -DryRun }
    Check 'dedicated -mod/-servermod are @names' ($o -match '-mod=@SelfTestMod' -and $o -match '-servermod=@SrvMod')
    Check 'dedicated logging flags' ($o -match '-dologs' -and $o -match '-adminlog' -and $o -match '-freezecheck')

    Write-DzStep 'Server config templates'
    foreach ($kind in 'diag', 'dedicated') {
        $t = Get-Content -Raw (Join-DzPath $repo 'server' 'templates' "serverDZ.$kind.cfg")
        Check "$kind cfg has placeholders only" ($t -match '__ADMIN_PASSWORD__' -and $t -match '__MISSION__')
    }
    $ded = Get-Content -Raw (Join-DzPath $repo 'server' 'templates' 'serverDZ.dedicated.cfg')
    Check 'dedicated enforces signatures + BattlEye' ($ded -match 'verifySignatures = 2;' -and $ded -match 'BattlEye = 1;' -and $ded -match 'allowFilePatching = 0;')

    Write-DzStep 'Repository hygiene'
    $gi = Get-Content -Raw (Join-DzPath $repo '.gitignore')
    Check '.gitignore blocks private keys' ($gi -match '\*\.biprivatekey')
    Check '.gitignore blocks local config' ($gi -match 'workspace\.config\.json')
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ''
if ($script:fail) { Write-DzFail "$script:fail assertion(s) failed" } else { Write-DzOk 'all self-tests passed' }
exit $script:fail
