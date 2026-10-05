<#
.SYNOPSIS
    One-command validation run: static checks, build, pack, sign, deploy, start the
    dedicated server, collect RPT / script / ADM logs and write a PASS/FAIL summary.

.DESCRIPTION
    Steps (each prints its exact command lines; -DryRun prints and runs nothing):
      1. Static checks (mods with assets\check_assets.py, e.g. SKY_Skyline): Python
         generators in --check mode, check_assets, the placement self-test; Blender
         geometry tests when -Blender is given.
      2. tools\build\Build-Mod.ps1, Sign-Mod.ps1, Deploy-Mod.ps1 (dedicated server).
      3. Optional -Layout <yaml>: placement\sky_layout.py -> objectSpawnersArr JSON, plus the
         mod's economy (sky_ce folder, mapgroupproto groups, roof-drop event positions),
         merged into a COPY of the vanilla mission: <ServerDir>\mpmissions\<Mission>.validation
         (the vanilla mission folder is never edited). A rendered
         server\serverDZ.validation.cfg (git-ignored) points the server at that copy.
      4. tools\launch\Start-DedicatedServer.ps1 with verifySignatures = 2 / BattlEye = 1
         (the dedicated config), waits -Minutes, then stops the server (-KeepRunning keeps it).
      5. Copies the new logs from server\profiles\dedicated to build\validation\<timestamp>\
         and writes summary.md / summary.json there. Exit code 1 on FAIL.
    -AnalyzeOnly <folder> re-runs only the log summary on a folder of logs.

.EXAMPLE
    .\tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -DryRun
    .\tools\tests\Invoke-ModValidation.ps1 -ModName SKY_Skyline -Layout mods\SKY_Skyline\placement\layout.yaml -Minutes 4
    .\tools\tests\Invoke-ModValidation.ps1 -AnalyzeOnly build\validation\20261005-1200\logs
#>
[CmdletBinding()]
param(
    [string]$ModName = 'SKY_Skyline',
    [string]$Layout,
    [string]$Mission,
    [int]$Minutes = 3,
    [string]$Python = 'python',
    [string]$Blender,
    [switch]$AllowPlaceholder,
    [switch]$SkipStatic,
    [switch]$SkipBuild,
    [switch]$KeepRunning,
    [string]$AnalyzeOnly,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

# ---------------------------------------------------------------- log analysis
# Lines that make the run FAIL (first match per line wins). Patterns are engine/script log
# texts seen in DayZ RPT/script logs; unknown wording only shows up under "Notable".
$script:FailPatterns = [ordered]@{
    'script error'       = 'SCRIPT\s+\(E\)'
    'compile error'      = "Can't compile|Error compiling"
    'missing object'     = 'Cannot open object'
    'missing file'       = 'Cannot open file|Cannot load texture|Cannot load material|Warning Message: Cannot open'
    'config inheritance' = 'Updating base class'
    'config entry'       = 'No entry'
    'signature'          = 'Signature check|is not signed|wrong signature'
    'crash'              = '\bCrash\b|Access violation|EXCEPTION_'
}
# These four only FAIL when the line names the mod (ModFilter); the same lines from vanilla or
# other mods are listed under "Notable" so vanilla noise cannot fail a run.
$script:ModScoped = @('missing object', 'missing file', 'config inheritance', 'config entry')
$script:NotePatterns = [ordered]@{
    'SKY script lines' = '\[SKY\]'
    'mod mentions'     = 'SKY_Skyline|Land_SKY_'
    'warnings'         = 'SCRIPT\s+\(W\)|Warning'
    'other-mod / vanilla load errors' = '__scoped__'
}

function Save-DzText([string]$Path, [string]$Text) {
    [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))   # no BOM (QA Info)
}

function Save-DzXml($Doc, [string]$Path) {
    $set = New-Object System.Xml.XmlWriterSettings
    $set.Encoding = New-Object System.Text.UTF8Encoding($false)
    $set.Indent = $true
    $w = [System.Xml.XmlWriter]::Create($Path, $set)
    try { $Doc.Save($w) } finally { $w.Close() }
}

function Get-DzLogSummary {
    param([Parameter(Mandatory)][string]$LogDir, [string]$ModFilter = 'SKY_|Land_SKY|\[SKY\]')
    $files = @(Get-ChildItem -LiteralPath $LogDir -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '\.(RPT|log|ADM|mdmp)$' -or $_.Name -like 'crash*' })
    $fails = [ordered]@{}
    $notes = [ordered]@{}
    foreach ($k in $script:FailPatterns.Keys) { $fails[$k] = New-Object System.Collections.ArrayList }
    foreach ($k in $script:NotePatterns.Keys) { $notes[$k] = 0 }
    foreach ($f in $files) {
        if ($f.Name -like 'crash*' -or $f.Name -like '*.mdmp') { [void]$fails['crash'].Add("$($f.Name): crash log / dump present"); if ($f.Name -like '*.mdmp') { continue } }
        $n = 0
        foreach ($line in [System.IO.File]::ReadLines($f.FullName)) {
            $n++
            foreach ($k in $script:FailPatterns.Keys) {
                # case-sensitive: vanilla "StaticHeliCrash" / lower-case "sky_" paths must not match (QA R-L4)
                if ($line -cmatch $script:FailPatterns[$k]) {
                    if (($script:ModScoped -contains $k) -and ($line -cnotmatch $ModFilter)) {
                        $notes['other-mod / vanilla load errors']++
                    } else {
                        [void]$fails[$k].Add(('{0}:{1}: {2}' -f $f.Name, $n, $line.Trim()))
                    }
                    break
                }
            }
            foreach ($k in $script:NotePatterns.Keys) {
                if ($script:NotePatterns[$k] -ne '__scoped__' -and $line -cmatch $script:NotePatterns[$k]) { $notes[$k]++ }
            }
        }
    }
    $total = 0
    foreach ($k in $fails.Keys) { $total += $fails[$k].Count }
    return [pscustomobject]@{ Files = $files; Fails = $fails; Notes = $notes; FailCount = $total }
}

function Write-DzSummary {
    param($Summary, $Steps, [string]$OutDir, [string]$Title)
    $status = 'PASS'
    if ($Summary.FailCount -gt 0) { $status = 'FAIL' }
    foreach ($s in $Steps) { if ($s.Result -eq 'DRYRUN' -and $status -eq 'PASS') { $status = 'DRYRUN' } }
    foreach ($s in $Steps) { if ($s.Result -eq 'FAIL') { $status = 'FAIL' } }
    $md = New-Object System.Text.StringBuilder
    [void]$md.AppendLine("# $Title")
    [void]$md.AppendLine('')
    [void]$md.AppendLine("Status: **$status**  ($(Get-Date -Format 'yyyy-MM-dd HH:mm'))")
    [void]$md.AppendLine('')
    [void]$md.AppendLine('## Steps')
    [void]$md.AppendLine('| Step | Result | Detail |')
    [void]$md.AppendLine('|---|---|---|')
    foreach ($s in $Steps) { [void]$md.AppendLine("| $($s.Name) | $($s.Result) | $($s.Detail) |") }
    [void]$md.AppendLine('')
    [void]$md.AppendLine('## Log findings (FAIL patterns)')
    foreach ($k in $Summary.Fails.Keys) {
        $list = $Summary.Fails[$k]
        [void]$md.AppendLine("- **$k**: $($list.Count)")
        $shown = 0
        foreach ($l in $list) { if ($shown -lt 5) { [void]$md.AppendLine("  - ``$l``"); $shown++ } }
    }
    [void]$md.AppendLine('')
    [void]$md.AppendLine('## Notable (not failing)')
    foreach ($k in $Summary.Notes.Keys) { [void]$md.AppendLine("- $k : $($Summary.Notes[$k])") }
    [void]$md.AppendLine('')
    [void]$md.AppendLine('## Log files')
    foreach ($f in $Summary.Files) { [void]$md.AppendLine("- $($f.Name) ($([int]($f.Length / 1024)) KB)") }
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    Set-Content -LiteralPath (Join-DzPath $OutDir 'summary.md') -Value $md.ToString() -Encoding UTF8
    $json = [ordered]@{ status = $status; steps = $Steps; failCount = $Summary.FailCount; fails = $Summary.Fails; notes = $Summary.Notes }
    Set-Content -LiteralPath (Join-DzPath $OutDir 'summary.json') -Value ($json | ConvertTo-Json -Depth 6) -Encoding UTF8
    return $status
}

if ($AnalyzeOnly) {
    $sum = Get-DzLogSummary -LogDir $AnalyzeOnly
    $st = Write-DzSummary -Summary $sum -Steps @() -OutDir $AnalyzeOnly -Title "Log analysis: $AnalyzeOnly"
    Write-DzStep "Log analysis $st ($($sum.FailCount) failing lines) -> $(Join-DzPath $AnalyzeOnly 'summary.md')"
    if ($st -eq 'FAIL') { exit 1 }
    exit 0
}

# ---------------------------------------------------------------- run
$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
$repo  = Get-DzRepoRoot
if (-not $Mission) { $Mission = $cfg.server.mission }
$modDir = Join-DzPath $repo 'mods' $ModName
$stamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$outDir = Join-DzPath $repo 'build' 'validation' $stamp
$steps  = New-Object System.Collections.ArrayList
function Add-Step([string]$Name, [string]$Result, [string]$Detail) {
    [void]$steps.Add([pscustomobject]@{ Name = $Name; Result = $Result; Detail = $Detail })
    $line = '{0}: {1} {2}' -f $Name, $Result, $Detail
    if ($Result -eq 'FAIL') { Write-DzFail $line } elseif ($Result -eq 'SKIP') { Write-DzWarn $line } else { Write-DzOk $line }
}

function Invoke-DzCheck([string]$Name, [string]$Exe, [string[]]$CheckArgs) {
    Write-DzInfo "> $Exe $($CheckArgs -join ' ')"
    if ($DryRun) { Add-Step $Name 'DRYRUN' ''; return }
    # PowerShell 5.1 turns native stderr into terminating errors under 'Stop' (QA R-L3)
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $out = & $Exe @CheckArgs 2>&1 | ForEach-Object { "$_" }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $old
    $last = ($out | Select-Object -Last 1) -as [string]
    if ($code -eq 0) { Add-Step $Name 'PASS' $last } else { Add-Step $Name 'FAIL' "exit $code - $last" }
}

Write-DzStep "Validation of $ModName ($stamp)"
if (-not (Test-Path -LiteralPath $modDir)) { throw "Mod not found: $modDir" }

# 1. static checks
if ($SkipStatic) { Add-Step 'static checks' 'SKIP' '-SkipStatic' }
elseif (Test-Path -LiteralPath (Join-DzPath $modDir 'assets' 'check_assets.py')) {
    Write-DzStep 'Static checks (Python)'
    Invoke-DzCheck 'gen_configs --check'  $Python @((Join-DzPath $modDir 'assets' 'gen_configs.py'), '--check')
    Invoke-DzCheck 'gen_manifest --check' $Python @((Join-DzPath $modDir 'assets' 'gen_manifest.py'), '--check')
    Invoke-DzCheck 'gen_economy --check'  $Python @((Join-DzPath $modDir 'economy' 'gen_economy.py'), '--check')
    Invoke-DzCheck 'check_assets'         $Python @((Join-DzPath $modDir 'assets' 'check_assets.py'))
    Invoke-DzCheck 'placement self-test'  $Python @((Join-DzPath $modDir 'placement' 'tests' 'test_sky_layout.py'))
    if ($Blender) {
        Write-DzStep 'Static checks (Blender geometry tests)'
        Invoke-DzCheck 'test_kit'    $Blender @('-b', '--factory-startup', '-P', (Join-DzPath $modDir 'assets' 'blender' 'test_kit.py'))
        Invoke-DzCheck 'test_towera' $Blender @('-b', '--factory-startup', '-P', (Join-DzPath $modDir 'assets' 'blender' 'test_towera.py'))
    } else { Add-Step 'Blender geometry tests' 'SKIP' 'pass -Blender <blender.exe> to run test_kit / test_towera' }
} else { Add-Step 'static checks' 'SKIP' 'mod has no assets\check_assets.py' }

# 2. build, sign, deploy
if ($SkipBuild) { Add-Step 'build/sign/deploy' 'SKIP' '-SkipBuild' }
else {
    $current = 'build (pack)'
    try {
        & (Join-DzPath $repo 'tools' 'build' 'Build-Mod.ps1') -ModName $ModName -DryRun:$DryRun
        Add-Step $current 'PASS' "build\@$ModName"
        $current = 'sign'
        try {
            & (Join-DzPath $repo 'tools' 'build' 'Sign-Mod.ps1') -ModName $ModName -DryRun:$DryRun
            Add-Step $current 'PASS' 'bisign + bikey'
        } catch {
            if (-not $DryRun) { throw }
            Add-Step $current 'DRYRUN' $_.Exception.Message      # dry run on a machine without a key
        }
        $current = 'deploy'
        & (Join-DzPath $repo 'tools' 'build' 'Deploy-Mod.ps1') -ModName $ModName -DryRun:$DryRun
        Add-Step $current 'PASS' $paths.ServerDir
    } catch {
        Add-Step $current 'FAIL' $_.Exception.Message
        $st = Write-DzSummary -Summary (Get-DzLogSummary -LogDir $outDir) -Steps $steps -OutDir $outDir -Title "Validation $ModName $stamp"
        Write-DzFail "Validation $st -> $(Join-DzPath $outDir 'summary.md')"
        exit 1
    }
}

# 3. optional layout -> mission copy
$config = Join-DzPath $repo 'server' 'serverDZ.dedicated.cfg'
if ($Layout) {
    Write-DzStep "Layout $Layout -> mission copy '$Mission.validation'"
    $layoutOut = Join-DzPath $outDir 'layout'
    $layoutArgs = @((Join-DzPath $modDir 'placement' 'sky_layout.py'), '--layout', $Layout, '--out', $layoutOut)
    if (-not $AllowPlaceholder) { $layoutArgs += '--strict' }     # a placeholder/unsurveyed site must not spawn at (0, 0, 0)
    Invoke-DzCheck 'sky_layout' $Python $layoutArgs
    if ($steps[$steps.Count - 1].Result -eq 'FAIL') {
        $st = Write-DzSummary -Summary (Get-DzLogSummary -LogDir $outDir) -Steps $steps -OutDir $outDir -Title "Validation $ModName $stamp"
        Write-DzFail "Layout failed (see $layoutOut\placement_report.md). Validation $st -> $(Join-DzPath $outDir 'summary.md')"
        exit 1
    }
    $srcMission = Join-DzPath $paths.ServerDir 'mpmissions' $Mission
    $valMission = Join-DzPath $paths.ServerDir 'mpmissions' "$Mission.validation"
    $valConfig  = Join-DzPath $repo 'server' 'serverDZ.validation.cfg'
    Write-DzInfo "> copy $srcMission -> $valMission (storage wiped); merge sky_objects.json, cfggameplay, sky_ce, mapgroupproto, roof drops, infected zone"
    Write-DzInfo "> render $valConfig (template = $Mission.validation)"
    if (-not $DryRun) {
        if (-not (Test-Path -LiteralPath $srcMission)) { throw "Vanilla mission not found: $srcMission" }
        if (Test-Path -LiteralPath $valMission) { Remove-Item -LiteralPath $valMission -Recurse -Force }
        Copy-Item -LiteralPath $srcMission -Destination $valMission -Recurse
        $storage = Join-DzPath $valMission 'storage_1'
        if (Test-Path -LiteralPath $storage) { Remove-Item -LiteralPath $storage -Recurse -Force }
        # objectSpawnersArr
        New-Item -ItemType Directory -Force -Path (Join-DzPath $valMission 'sky') | Out-Null
        Copy-Item -LiteralPath (Join-DzPath $layoutOut 'sky_objects.json') -Destination (Join-DzPath $valMission 'sky' 'sky_objects.json')
        $gpPath = Join-DzPath $valMission 'cfggameplay.json'
        $gp = Get-Content -Raw -LiteralPath $gpPath | ConvertFrom-Json
        if (-not $gp.WorldsData) { $gp | Add-Member -NotePropertyName WorldsData -NotePropertyValue ([pscustomobject]@{}) }
        $gp.WorldsData | Add-Member -NotePropertyName objectSpawnersArr -NotePropertyValue @('sky/sky_objects.json') -Force
        Save-DzText $gpPath ($gp | ConvertTo-Json -Depth 20)
        # economy: <ce folder="sky_ce"> + mapgroupproto groups + roof-drop positions
        $eco = Join-DzPath $modDir 'economy'
        if (Test-Path -LiteralPath (Join-DzPath $eco 'sky_ce')) {
            Copy-Item -LiteralPath (Join-DzPath $eco 'sky_ce') -Destination (Join-DzPath $valMission 'sky_ce') -Recurse
            $corePath = Join-DzPath $valMission 'cfgeconomycore.xml'
            [xml]$core = Get-Content -Raw -LiteralPath $corePath
            [xml]$snip = '<root>' + ((Get-Content -Raw -LiteralPath (Join-DzPath $eco 'cfgeconomycore_snippet.xml')) -replace '<!--[\s\S]*?-->', '') + '</root>'
            foreach ($n in $snip.root.ChildNodes) { [void]$core.economycore.AppendChild($core.ImportNode($n, $true)) }
            Save-DzXml $core $corePath
            $protoPath = Join-DzPath $valMission 'mapgroupproto.xml'
            [xml]$proto = Get-Content -Raw -LiteralPath $protoPath
            [xml]$ours = Get-Content -Raw -LiteralPath (Join-DzPath $eco 'mapgroupproto_sky.xml')
            foreach ($g in $ours.prototype.SelectNodes('group')) { [void]$proto.prototype.AppendChild($proto.ImportNode($g, $true)) }
            Save-DzXml $proto $protoPath
            $evPath = Join-DzPath $valMission 'cfgeventspawns.xml'
            [xml]$ev = Get-Content -Raw -LiteralPath $evPath
            [xml]$drops = Get-Content -Raw -LiteralPath (Join-DzPath $layoutOut 'cfgeventspawns_snippet.xml')
            [void]$ev.eventposdef.AppendChild($ev.ImportNode($drops.event, $true))
            Save-DzXml $ev $evPath
            $zoneSnip = Join-DzPath $layoutOut 'zombie_territories_snippet.xml'
            $ztPath = Join-DzPath $valMission 'env' 'zombie_territories.xml'
            if ((Test-Path -LiteralPath $zoneSnip) -and (Test-Path -LiteralPath $ztPath)) {
                [xml]$zt = Get-Content -Raw -LiteralPath $ztPath
                [xml]$zs = '<root>' + ((Get-Content -Raw -LiteralPath $zoneSnip) -replace '<!--[\s\S]*?-->', '') + '</root>'
                $terr = $zt.SelectSingleNode("//territory[zone[@name='InfectedCity']]")
                if (-not $terr) { $terr = $zt.SelectSingleNode('//territory') }
                foreach ($z in $zs.root.SelectNodes('zone')) { [void]$terr.AppendChild($zt.ImportNode($z, $true)) }
                Save-DzXml $zt $ztPath
            }
        }
        $text = Get-Content -Raw -LiteralPath $config
        $text = [regex]::Replace($text, 'template\s*=\s*"[^"]*"', "template = `"$Mission.validation`"")
        Set-Content -LiteralPath $valConfig -Value $text -Encoding ASCII
    }
    $config = $valConfig
    Add-Step 'mission copy' 'PASS' "$Mission.validation (loot positions need ExportProxyData, placement\README.md section 3)"
}

# 4. start server, wait, stop
$profileDir = Join-DzPath $repo 'server' 'profiles' 'dedicated'
$t0 = Get-Date
& (Join-DzPath $repo 'tools' 'launch' 'Start-DedicatedServer.ps1') -Mods $ModName -Config $config -DryRun:$DryRun
if ($DryRun) {
    Write-DzInfo "> wait $Minutes min, stop DayZServer_x64, copy logs newer than start from $profileDir to $outDir\logs"
    Add-Step 'server run' 'DRYRUN' "$Minutes min"
} else {
    Start-Sleep -Seconds 5
    $proc = Get-Process -Name 'DayZServer_x64' -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -ge $t0.AddSeconds(-2) } | Select-Object -First 1
    if (-not $proc) { Add-Step 'server run' 'FAIL' 'DayZServer_x64 did not start' }
    else {
        $deadline = $t0.AddMinutes($Minutes)
        $died = $false
        while ((Get-Date) -lt $deadline) {
            Start-Sleep -Seconds 5
            $proc.Refresh()
            if ($proc.HasExited) { $died = $true; break }
        }
        if ($died) { Add-Step 'server run' 'FAIL' "server exited early (code $($proc.ExitCode))" }
        else {
            Add-Step 'server run' 'PASS' "$Minutes min, PID $($proc.Id)"
            if (-not $KeepRunning) { Stop-Process -Id $proc.Id -Force; Add-Step 'server stop' 'PASS' 'stopped' }
            else { Add-Step 'server stop' 'SKIP' "-KeepRunning (PID $($proc.Id))" }
        }
    }
}

# 5. collect logs + summary
$logOut = Join-DzPath $outDir 'logs'
New-Item -ItemType Directory -Force -Path $logOut | Out-Null
if (-not $DryRun -and (Test-Path -LiteralPath $profileDir)) {
    Get-ChildItem -LiteralPath $profileDir -File | Where-Object { $_.LastWriteTime -ge $t0 } |
        Where-Object { $_.Name -match '\.(RPT|log|ADM|mdmp)$' -or $_.Name -like 'crash*' } |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $logOut }
}
$sum = Get-DzLogSummary -LogDir $logOut
$status = Write-DzSummary -Summary $sum -Steps $steps -OutDir $outDir -Title "Validation $ModName $stamp"
Write-DzStep "Validation $status -> $(Join-DzPath $outDir 'summary.md')"
if ($status -eq 'FAIL') { exit 1 }
exit 0
