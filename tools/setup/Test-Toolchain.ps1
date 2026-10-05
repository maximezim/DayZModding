<#
.SYNOPSIS
    Smoke-tests the toolchain WITHOUT any mod content.

.DESCRIPTION
    1. P: work drive mounted
    2. Vanilla scripts on P:\scripts are readable (known classes found)
    3. Dedicated server starts with no mods and reaches "ready" in its logs,
       then is stopped
    4. Build-Mod (+ Sign-Mod if a key exists) runs on templates\ModTemplate
       into build\smoketest (never into a real mod folder)
    Results: build\smoke-test.json. Exit code = number of failed checks.
#>
[CmdletBinding()]
param(
    [int]$ServerTimeoutSeconds = 600,
    [switch]$SkipServer,
    [switch]$SkipBuild
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
$repo  = Get-DzRepoRoot
$results = New-Object System.Collections.Generic.List[object]
function Result([string]$check, [string]$status, [string]$detail) {
    $results.Add([pscustomobject]@{ Check = $check; Status = $status; Detail = $detail })
    switch ($status) { 'PASS' { Write-DzOk "$check - $detail" } 'SKIP' { Write-DzWarn "$check - $detail" } default { Write-DzFail "$check - $detail" } }
}

# 1 ---------------------------------------------------------------
Write-DzStep 'Work drive'
if (Test-Path -LiteralPath $paths.WorkDrive) { Result 'P: mounted' 'PASS' $paths.WorkDrive }
else { Result 'P: mounted' 'FAIL' 'run tools\setup\Initialize-WorkDrive.ps1' }

# 2 ---------------------------------------------------------------
Write-DzStep 'Vanilla scripts readable'
$scripts = Join-DzPath $paths.WorkDrive 'scripts'
if (Test-Path -LiteralPath $scripts) {
    $files = @(Get-ChildItem -LiteralPath $scripts -Recurse -Filter '*.c' -File -ErrorAction SilentlyContinue)
    $probe = @{ 'class PlayerBase' = '4_World'; 'class MissionServer' = '5_Mission'; 'class DayZGame' = '3_Game' }
    $found = @()
    foreach ($k in $probe.Keys) {
        $hit = Get-ChildItem -LiteralPath (Join-DzPath $scripts $probe[$k]) -Recurse -Filter '*.c' -File -ErrorAction SilentlyContinue |
               Select-String -Pattern ([regex]::Escape($k) + '\b') -List | Select-Object -First 1
        if ($hit) { $found += "$k @ $($hit.Path.Substring($scripts.Length))" }
    }
    if ($files.Count -gt 0 -and $found.Count -eq $probe.Count) { Result 'Game scripts readable' 'PASS' "$($files.Count) .c files; $($found -join '; ')" }
    else { Result 'Game scripts readable' 'FAIL' "$($files.Count) .c files; found: $($found -join '; ')" }
} else { Result 'Game scripts readable' 'FAIL' "$scripts missing" }

# 3 ---------------------------------------------------------------
Write-DzStep 'Dedicated server starts with an empty setup'
if ($SkipServer) { Result 'Server starts' 'SKIP' '-SkipServer' }
elseif (-not (Test-Path -LiteralPath $paths.DayZServerExe)) { Result 'Server starts' 'FAIL' "no $($paths.DayZServerExe)" }
elseif (-not (Test-Path (Join-DzPath $repo 'server' 'serverDZ.dedicated.cfg'))) { Result 'Server starts' 'FAIL' 'run tools\setup\Initialize-TestServer.ps1' }
else {
    $profileDir = Join-DzPath $repo 'server' 'profiles' 'smoketest'
    if (Test-Path -LiteralPath $profileDir) { Remove-Item -LiteralPath $profileDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $profileDir | Out-Null
    $srvArgs = @("-config=$(Join-DzPath $repo 'server' 'serverDZ.dedicated.cfg')", "-port=$($cfg.server.port)", "-profiles=$profileDir", '-dologs', '-adminlog', '-freezecheck')
    $proc = Invoke-DzTool -FilePath $paths.DayZServerExe -ArgumentList $srvArgs -WorkingDirectory $paths.ServerDir -NoWait
    $deadline = (Get-Date).AddSeconds($ServerTimeoutSeconds)
    $ready = $false; $errLine = ''
    while ((Get-Date) -lt $deadline -and -not $proc.HasExited) {
        Start-Sleep -Seconds 5
        $logs = @(Get-ChildItem -LiteralPath $profileDir -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '\.(RPT|log)$' })
        foreach ($l in $logs) {
            $t = Get-Content -Raw -LiteralPath $l.FullName -ErrorAction SilentlyContinue
            if (-not $t) { continue }
            if ($t -match 'Dedicated host created|BattlEye Server: Initialized|Mission read') { $ready = $true }
            $m = [regex]::Match($t, '(?m)^.*(SCRIPT\s+\(E\)|Can''t compile|ErrorMessage).*$')
            if ($m.Success) { $errLine = $m.Value.Trim() }
        }
        if ($ready) { break }
    }
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    if ($ready -and -not $errLine) { Result 'Server starts' 'PASS' "ready marker found; logs in $profileDir" }
    elseif ($ready) { Result 'Server starts' 'FAIL' "started but script error: $errLine" }
    else { Result 'Server starts' 'FAIL' "no ready marker within $ServerTimeoutSeconds s (exited=$($proc.HasExited)); see $profileDir" }
}

# 4 ---------------------------------------------------------------
Write-DzStep 'Build scripts on the empty template'
if ($SkipBuild) { Result 'Build template' 'SKIP' '-SkipBuild' }
else {
    $out = Join-DzPath $repo 'build' 'smoketest'
    try {
        & (Join-DzPath $repo 'tools\build\Build-Mod.ps1') -ModName ModTemplate -OutputRoot $out
        $pbo = Join-DzPath $out '@ModTemplate' 'addons' 'scripts.pbo'
        if (Test-Path -LiteralPath $pbo) { Result 'Build template' 'PASS' $pbo } else { Result 'Build template' 'FAIL' "missing $pbo" }
        if ($paths.PrivateKey -and (Test-Path -LiteralPath $paths.PrivateKey)) {
            & (Join-DzPath $repo 'tools\build\Sign-Mod.ps1') -ModName ModTemplate -OutputRoot $out
            Result 'Sign template' 'PASS' "key $($paths.KeyName)"
        } else { Result 'Sign template' 'SKIP' 'no signing key yet (New-SigningKey.ps1)' }
    } catch { Result 'Build template' 'FAIL' "$_" }
}

$jsonOut = Join-DzPath $repo 'build' 'smoke-test.json'
New-Item -ItemType Directory -Force -Path (Split-Path $jsonOut) | Out-Null
$results | ConvertTo-Json | Set-Content -LiteralPath $jsonOut -Encoding UTF8
$results | Format-Table -AutoSize | Out-String | Write-Host
$failed = @($results | Where-Object { $_.Status -eq 'FAIL' }).Count
Write-Host "Saved $jsonOut - $failed failed check(s)."
exit $failed
