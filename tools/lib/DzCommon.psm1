# Shared helpers for the DayZ workspace scripts.
# Targets Windows PowerShell 5.1 and PowerShell 7+. Keep syntax 5.1-compatible
# (no ?? / ?: / pipeline-chain operators, Join-DzPath with two arguments only).

Set-StrictMode -Version 2.0

$script:RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path

# Steam app ids (verified against Steam store / SteamCMD docs).
$script:AppIds = @{
    DayZ       = 221100
    DayZTools  = 830640
    DayZServer = 223350
}

# ---------------------------------------------------------------- logging
function Write-DzStep { param([string]$Message) Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-DzInfo { param([string]$Message) Write-Host "    $Message" }
function Write-DzOk   { param([string]$Message) Write-Host "    [OK]   $Message" -ForegroundColor Green }
function Write-DzWarn { param([string]$Message) Write-Host "    [WARN] $Message" -ForegroundColor Yellow }
function Write-DzFail { param([string]$Message) Write-Host "    [FAIL] $Message" -ForegroundColor Red }

function Test-DzWindows {
    # $IsWindows does not exist on Windows PowerShell 5.1.
    return ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT)
}

function Get-DzRepoRoot { return $script:RepoRoot }

function Join-DzPath {
    # Join-DzPath with any number of segments (5.1 has no -AdditionalChildPath).
    # An unknown base (tool not installed) yields '' instead of a misleading relative path.
    param([Parameter(Mandatory)][AllowEmptyString()][string]$Base, [Parameter(ValueFromRemainingArguments)][string[]]$Parts)
    if (-not $Base) { return '' }
    # [IO.Path]::Combine never validates the drive (Join-DzPath throws if P: is not mounted).
    $p = $Base
    foreach ($part in $Parts) { if ($part) { $p = [System.IO.Path]::Combine($p, $part) } }
    # Lets the dry-run self-test run under PowerShell 7 on Linux/CI.
    if (-not (Test-DzWindows)) { $p = $p.Replace('\', '/') }
    return $p
}

function Expand-DzPath {
    param([string]$Path)
    if (-not $Path) { return '' }
    return [System.Environment]::ExpandEnvironmentVariables($Path)
}

# ---------------------------------------------------------------- config
function Merge-DzObject {
    param($Base, $Overlay)
    if ($null -eq $Overlay) { return $Base }
    foreach ($prop in $Overlay.PSObject.Properties) {
        $existing = $Base.PSObject.Properties[$prop.Name]
        if ($existing -and $existing.Value -is [psobject] -and $prop.Value -is [psobject] -and
            -not ($existing.Value -is [string]) -and -not ($prop.Value -is [string])) {
            Merge-DzObject -Base $existing.Value -Overlay $prop.Value | Out-Null
        } elseif ($existing) {
            $existing.Value = $prop.Value
        } else {
            $Base | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value
        }
    }
    return $Base
}

function Get-DzConfig {
    $example = Join-DzPath $script:RepoRoot 'workspace.config.example.json'
    $local   = Join-DzPath $script:RepoRoot 'workspace.config.json'
    $cfg = Get-Content -Raw -LiteralPath $example | ConvertFrom-Json
    if (Test-Path -LiteralPath $local) {
        $cfg = Merge-DzObject -Base $cfg -Overlay (Get-Content -Raw -LiteralPath $local | ConvertFrom-Json)
    }
    return $cfg
}

function Set-DzConfigValue {
    # Writes a dotted key (e.g. 'signing.keyName') into the local, git-ignored config.
    param([Parameter(Mandatory)][string]$Key, [Parameter(Mandatory)]$Value)
    $local = Join-DzPath $script:RepoRoot 'workspace.config.json'
    if (Test-Path -LiteralPath $local) {
        $cfg = Get-Content -Raw -LiteralPath $local | ConvertFrom-Json
    } else {
        $cfg = New-Object psobject
    }
    $node = $cfg
    $parts = $Key.Split('.')
    for ($i = 0; $i -lt $parts.Length - 1; $i++) {
        $p = $node.PSObject.Properties[$parts[$i]]
        if (-not $p) { $node | Add-Member -NotePropertyName $parts[$i] -NotePropertyValue (New-Object psobject); $p = $node.PSObject.Properties[$parts[$i]] }
        $node = $p.Value
    }
    $leaf = $parts[-1]
    if ($node.PSObject.Properties[$leaf]) { $node.$leaf = $Value } else { $node | Add-Member -NotePropertyName $leaf -NotePropertyValue $Value }
    $cfg | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $local -Encoding UTF8
}

# ---------------------------------------------------------------- Steam detection
function Get-DzSteamDir {
    param($Config = (Get-DzConfig))
    if ($Config.steamDir) { return (Expand-DzPath $Config.steamDir) }
    if (Test-DzWindows) {
        foreach ($key in 'HKCU:\Software\Valve\Steam', 'HKLM:\SOFTWARE\WOW6432Node\Valve\Steam') {
            $item = Get-ItemProperty -Path $key -ErrorAction SilentlyContinue
            if ($item) {
                foreach ($name in 'SteamPath', 'InstallPath') {
                    $prop = $item.PSObject.Properties[$name]
                    if ($prop -and $prop.Value -and (Test-Path -LiteralPath $prop.Value)) { return ($prop.Value -replace '/', '\') }
                }
            }
        }
    }
    return ''
}

function Get-DzSteamLibraries {
    param($Config = (Get-DzConfig))
    $steam = Get-DzSteamDir -Config $Config
    $libs = New-Object System.Collections.Generic.List[string]
    if (-not $steam) { return @() }
    $libs.Add($steam)
    $vdf = Join-DzPath $steam 'steamapps' 'libraryfolders.vdf'
    if (Test-Path -LiteralPath $vdf) {
        foreach ($m in [regex]::Matches((Get-Content -Raw -LiteralPath $vdf), '"path"\s+"([^"]+)"')) {
            $p = $m.Groups[1].Value -replace '\\\\', '\'
            if (-not $libs.Contains($p)) { $libs.Add($p) }
        }
    }
    return $libs.ToArray()
}

function Find-DzSteamApp {
    # Returns the install directory of a Steam app by reading its appmanifest, or ''.
    param([Parameter(Mandatory)][int]$AppId, $Config = (Get-DzConfig))
    foreach ($lib in (Get-DzSteamLibraries -Config $Config)) {
        $manifest = Join-DzPath $lib 'steamapps' "appmanifest_$AppId.acf"
        if (Test-Path -LiteralPath $manifest) {
            $m = [regex]::Match((Get-Content -Raw -LiteralPath $manifest), '"installdir"\s+"([^"]+)"')
            if ($m.Success) {
                $dir = Join-DzPath $lib 'steamapps' 'common' $m.Groups[1].Value
                if (Test-Path -LiteralPath $dir) { return $dir }
            }
        }
    }
    return ''
}

function Get-DzAppVersion {
    # Steam buildid from the appmanifest, useful for reports.
    param([Parameter(Mandatory)][int]$AppId, $Config = (Get-DzConfig))
    foreach ($lib in (Get-DzSteamLibraries -Config $Config)) {
        $manifest = Join-DzPath $lib 'steamapps' "appmanifest_$AppId.acf"
        if (Test-Path -LiteralPath $manifest) {
            $m = [regex]::Match((Get-Content -Raw -LiteralPath $manifest), '"buildid"\s+"([^"]+)"')
            if ($m.Success) { return "buildid $($m.Groups[1].Value)" }
        }
    }
    return ''
}

# ---------------------------------------------------------------- tool paths
function Find-DzOnPath {
    param([Parameter(Mandatory)][string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cmd) { return $cmd.Source }
    return ''
}

function Get-DzPaths {
    # Resolves every external tool the workspace uses. Missing tools resolve to ''.
    param($Config = (Get-DzConfig))
    $dayz = Expand-DzPath $Config.dayzDir
    if (-not $dayz) { $dayz = Find-DzSteamApp -AppId $script:AppIds.DayZ -Config $Config }
    $tools = Expand-DzPath $Config.dayzToolsDir
    if (-not $tools) { $tools = Find-DzSteamApp -AppId $script:AppIds.DayZTools -Config $Config }
    $server = Expand-DzPath $Config.serverDir
    if (-not ($server -and (Test-Path -LiteralPath $server))) {
        $steamServer = Find-DzSteamApp -AppId $script:AppIds.DayZServer -Config $Config
        if ($steamServer) { $server = $steamServer }
    }

    $mikero = Expand-DzPath $Config.mikeroBinDir
    if (-not $mikero) {
        foreach ($cand in "${env:ProgramFiles(x86)}\Mikero\DePboTools\bin", "$env:ProgramFiles\Mikero\DePboTools\bin") {
            if ($cand -and (Test-Path -LiteralPath $cand)) { $mikero = $cand; break }
        }
    }

    $keyDir  = Expand-DzPath $Config.signing.keyDir
    $keyName = $Config.signing.keyName

    $p = [ordered]@{
        RepoRoot      = $script:RepoRoot
        BuildDir      = Join-DzPath $script:RepoRoot 'build'
        DayZDir       = $dayz
        DayZToolsDir  = $tools
        ServerDir     = $server
        SteamCmdDir   = Expand-DzPath $Config.steamCmdDir
        WorkDrive     = ($Config.workDrive.letter.TrimEnd(':') + ':\')
        WorkDriveSrc  = Expand-DzPath $Config.workDrive.sourceDir
        DayZDiag      = ''
        DayZServerExe = ''
        AddonBuilder  = ''
        DSSignFile    = ''
        DSCreateKey   = ''
        ImageToPAA    = ''
        TexView2      = ''
        WorkDriveExe  = ''
        CfgConvert    = ''
        PboProject    = ''
        DePbo         = ''
        KeyDir        = $keyDir
        KeyName       = $keyName
        PrivateKey    = ''
        PublicKey     = ''
    }
    if ($dayz)   { $p.DayZDiag      = Join-DzPath $dayz 'DayZDiag_x64.exe' }
    if ($server) { $p.DayZServerExe = Join-DzPath $server 'DayZServer_x64.exe' }
    if ($tools) {
        $bin = Join-DzPath $tools 'Bin'
        $p.AddonBuilder = Join-DzPath $bin 'AddonBuilder' 'AddonBuilder.exe'
        $p.DSSignFile   = Join-DzPath $bin 'DsUtils' 'DSSignFile.exe'
        $p.DSCreateKey  = Join-DzPath $bin 'DsUtils' 'DSCreateKey.exe'
        $p.ImageToPAA   = Join-DzPath $bin 'ImageToPAA' 'ImageToPAA.exe'
        $p.TexView2     = Join-DzPath $bin 'ImageToPAA' 'TexView.exe'
        $p.WorkDriveExe = Join-DzPath $bin 'WorkDrive' 'WorkDrive.exe'
        $p.CfgConvert   = Join-DzPath $bin 'CfgConvert' 'CfgConvert.exe'
    }
    if ($mikero) {
        $p.PboProject = Join-DzPath $mikero 'pboProject.exe'
        $p.DePbo      = Join-DzPath $mikero 'DePbo64.dll'
    } else {
        $p.PboProject = Find-DzOnPath 'pboProject.exe'
    }
    if ($keyDir -and $keyName) {
        $p.PrivateKey = Join-DzPath $keyDir "$keyName.biprivatekey"
        $p.PublicKey  = Join-DzPath $keyDir "$keyName.bikey"
    }
    return New-Object psobject -Property $p
}

function Assert-DzTool {
    # Throws a helpful error if a required tool is missing (skipped in dry-run).
    param([Parameter(Mandatory)][string]$Name, [string]$Path, [switch]$DryRun)
    if ($DryRun) { return }
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) {
        throw "$Name not found ('$Path'). Run tools\setup\Get-ToolchainStatus.ps1, or set the path in workspace.config.json."
    }
}

# ---------------------------------------------------------------- process runner
function ConvertTo-DzArgString {
    param([string[]]$Arguments)
    $out = foreach ($a in $Arguments) {
        if ($null -eq $a -or $a -eq '') { continue }
        if ($a -match '[\s"]') {
            # Quote whole arg; for -key=value quote the value only (what BI tools expect).
            if ($a -match '^([-+/][^=\s]+=)(.*)$') { $Matches[1] + '"' + $Matches[2].Replace('"', '\"') + '"' }
            else { '"' + $a.Replace('"', '\"') + '"' }
        } else { $a }
    }
    return ($out -join ' ')
}

function Invoke-DzTool {
    # Runs an external tool, waits, and throws on non-zero exit. With -DryRun only prints.
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [string]$WorkingDirectory = $script:RepoRoot,
        [switch]$DryRun,
        [switch]$NoWait,
        [int[]]$OkExitCodes = @(0)
    )
    $argString = ConvertTo-DzArgString -Arguments $ArgumentList
    $shown = $FilePath
    if (-not $shown) { $shown = '<tool not installed>' }
    Write-DzInfo "> `"$shown`" $argString"
    if ($DryRun) { return $null }
    if (-not $FilePath) { throw 'Invoke-DzTool: tool path is empty (tool not installed).' }
    $sp = @{ FilePath = $FilePath; WorkingDirectory = $WorkingDirectory; PassThru = $true }
    if ($argString) { $sp.ArgumentList = $argString }
    if ($NoWait) { return (Start-Process @sp) }
    $proc = Start-Process @sp -NoNewWindow -Wait
    if ($OkExitCodes -notcontains $proc.ExitCode) {
        throw "$([System.IO.Path]::GetFileName($FilePath)) exited with code $($proc.ExitCode)."
    }
    return $proc
}

# ---------------------------------------------------------------- mod layout
function Resolve-DzModSource {
    # A mod source is <repo>\mods\<Name> (or templates\<Name>, or an explicit path).
    # Layout: <ModDir>\mod.cpp and <ModDir>\addons\<pbo>\ (one folder per PBO).
    param([Parameter(Mandatory)][string]$ModName, [string]$ModPath)
    if ($ModPath) { $dir = $ModPath }
    else {
        $dir = ''
        foreach ($root in 'mods', 'templates') {
            $cand = Join-DzPath $script:RepoRoot $root $ModName
            if (Test-Path -LiteralPath $cand) { $dir = $cand; break }
        }
        if (-not $dir) { throw "Mod '$ModName' not found under mods\ or templates\." }
    }
    $dir = (Resolve-Path -LiteralPath $dir).Path
    if (-not (Test-Path -LiteralPath (Join-DzPath $dir 'addons'))) { throw "Mod '$dir' has no addons\ folder." }
    return $dir
}

function Get-DzPboDirs {
    param([Parameter(Mandatory)][string]$ModDir)
    return @(Get-ChildItem -LiteralPath (Join-DzPath $ModDir 'addons') -Directory | Sort-Object Name)
}

function Get-DzPboPrefix {
    # $PBOPREFIX$ wins (source-side convention); otherwise <ModName>\<pbo folder>.
    param([Parameter(Mandatory)][string]$PboDir, [Parameter(Mandatory)][string]$ModName)
    $file = Join-DzPath $PboDir '$PBOPREFIX$'
    if (Test-Path -LiteralPath $file) {
        $line = (Get-Content -LiteralPath $file | Where-Object { $_.Trim() } | Select-Object -First 1)
        if ($line) { return ($line.Trim() -replace '^prefix\s*=\s*', '' -replace '/', '\').Trim('\') }
    }
    return "$ModName\$([System.IO.Path]::GetFileName($PboDir))"
}

function Test-DzPboNeedsBinarize {
    # Models, animations and worlds must go through Binarize; scripts/configs/paa can be pack-only.
    param([Parameter(Mandatory)][string]$PboDir)
    $hit = Get-ChildItem -LiteralPath $PboDir -Recurse -File -Include '*.p3d', '*.rtm', '*.wrp' -ErrorAction SilentlyContinue | Select-Object -First 1
    return [bool]$hit
}

function Set-DzJunction {
    # Creates (or verifies) a directory junction. Junctions need no admin rights.
    param([Parameter(Mandatory)][string]$Link, [Parameter(Mandatory)][string]$Target, [switch]$DryRun)
    if (Test-Path -LiteralPath $Link) {
        $item = Get-Item -LiteralPath $Link -Force
        $existing = $null
        if ($item.PSObject.Properties['Target'] -and $item.Target) { $existing = @($item.Target)[0] }
        if ($existing -and ((Resolve-Path -LiteralPath $existing).Path.TrimEnd('\') -eq (Resolve-Path -LiteralPath $Target).Path.TrimEnd('\'))) { return }
        throw "'$Link' already exists and is not a junction to '$Target'. Remove it manually."
    }
    Write-DzInfo "junction $Link -> $Target"
    if ($DryRun) { return }
    $parent = Split-Path -Parent $Link
    if ($parent -and -not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent | Out-Null }
    New-Item -ItemType Junction -Path $Link -Target $Target | Out-Null
}

function Resolve-DzBuiltMod {
    # Maps a mod name (or @folder / path) to its built folder under build\.
    param([Parameter(Mandatory)][string]$Mod)
    if (Test-Path -LiteralPath $Mod) { return (Resolve-Path -LiteralPath $Mod).Path }
    $name = $Mod.TrimStart('@')
    return (Join-DzPath $script:RepoRoot 'build' "@$name")
}

Export-ModuleMember -Function * -Variable AppIds
