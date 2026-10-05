<#
.SYNOPSIS
    Installs missing toolchain components, asking before each one.

.DESCRIPTION
    Detects first; only offers to install what is missing. Every install is
    confirmed interactively unless -Yes is given. Large/system-wide installs
    go through winget (per-machine) or Steam (steam:// protocol, needs the
    Steam client logged in). Components that cannot be automated (Mikero's
    tools, Blender P3D add-on) open their download page and are reported.

.PARAMETER Only
    Restrict to some components: Steam, DayZ, DayZTools, DayZServer, Git,
    GitLFS, VSCode, VSCodeExtensions, Blender, BlenderAddon, Python, Pillow,
    Mikero, GitHooks.

.EXAMPLE
    .\tools\setup\Install-Toolchain.ps1
    .\tools\setup\Install-Toolchain.ps1 -Only DayZServer
#>
[CmdletBinding()]
param(
    [string[]]$Only = @(),
    [switch]$Yes,
    [string]$SteamUser
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force
if (-not (Test-DzWindows)) { throw 'This installer only runs on Windows.' }

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
$log   = New-Object System.Collections.Generic.List[object]

function Want([string]$name) { return ($Only.Count -eq 0 -or $Only -contains $name) }
function Confirm-Install([string]$what) {
    if ($Yes) { return $true }
    $a = Read-Host "Install $what ? [y/N]"
    return ($a -match '^(y|yes|o|oui)$')
}
function Record([string]$name, [string]$result) {
    $log.Add([pscustomobject]@{ Component = $name; Result = $result })
    Write-DzInfo "$name : $result"
}
function Install-Winget([string]$name, [string]$id, [string]$detectExe) {
    if (-not (Want $name)) { return }
    if ($detectExe -and (Find-DzOnPath $detectExe)) { Record $name 'already installed'; return }
    $listed = (& winget list --id $id -e --accept-source-agreements 2>$null | Out-String)
    if ($listed -match [regex]::Escape($id)) { Record $name 'already installed (winget)'; return }
    if (-not (Confirm-Install "$name (winget $id)")) { Record $name 'skipped by user'; return }
    & winget install --id $id -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -eq 0) { Record $name 'installed - open a NEW terminal so PATH updates' } else { Record $name "winget failed ($LASTEXITCODE)" }
}
function Install-SteamApp([string]$name, [int]$appId, [string]$present) {
    if (-not (Want $name)) { return }
    if ($present) { Record $name "already installed ($present)"; return }
    if (-not (Get-DzSteamDir -Config $cfg)) { Record $name 'needs Steam first'; return }
    if (-not (Confirm-Install "$name via Steam (appid $appId)")) { Record $name 'skipped by user'; return }
    Start-Process "steam://install/$appId"
    Record $name 'Steam install dialog opened - finish it in Steam, then re-run Get-ToolchainStatus.ps1'
}

if (-not (Find-DzOnPath 'winget')) {
    Write-DzWarn 'winget not found (App Installer). winget-based installs will be skipped.'
}

Write-DzStep 'Core'
if (Get-DzSteamDir -Config $cfg) { if (Want 'Steam') { Record 'Steam' 'already installed' } }
else { Install-Winget 'Steam' 'Valve.Steam' '' }
Install-Winget 'Git'     'Git.Git' 'git'
Install-Winget 'GitLFS'  'GitHub.GitLFS' 'git-lfs'
if (-not (Find-DzOnPath 'code-insiders')) { Install-Winget 'VSCode'  'Microsoft.VisualStudioCode' 'code' }
elseif (Want 'VSCode') { Record 'VSCode' 'already installed (Insiders)' }
Install-Winget 'Blender' 'BlenderFoundation.Blender' 'blender'
Install-Winget 'Python'  'Python.Python.3.13' 'python'

Write-DzStep 'Steam content'
Install-SteamApp 'DayZ'      $AppIds.DayZ      $paths.DayZDir
Install-SteamApp 'DayZTools' $AppIds.DayZTools $paths.DayZToolsDir

if (Want 'DayZServer') {
    Write-DzStep 'DayZ Server via SteamCMD'
    $serverExe = Join-DzPath $paths.ServerDir 'DayZServer_x64.exe'
    if (Test-Path -LiteralPath $serverExe) { Record 'DayZServer' "already installed ($($paths.ServerDir))" }
    elseif (Confirm-Install "SteamCMD + DayZ Server (~3 GB) into $($paths.ServerDir)") {
        $scDir = $paths.SteamCmdDir
        $sc = Join-DzPath $scDir 'steamcmd.exe'
        if (-not (Test-Path -LiteralPath $sc)) {
            New-Item -ItemType Directory -Force -Path $scDir | Out-Null
            $zip = Join-DzPath $env:TEMP 'steamcmd.zip'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip' -OutFile $zip
            Expand-Archive -LiteralPath $zip -DestinationPath $scDir -Force
        }
        # Anonymous login works for 223350 per current community docs; fall back to an account if refused.
        $login = @('anonymous')
        if ($SteamUser) { $login = @($SteamUser) }
        & $sc +force_install_dir $paths.ServerDir +login @login +app_update 223350 validate +quit
        if (-not (Test-Path -LiteralPath $serverExe) -and -not $SteamUser) {
            Write-DzWarn 'Anonymous download is refused ("No subscription") for 223350 now. Re-run with -SteamUser <account that owns DayZ> (password / Steam Guard prompt appears in this console), or install "DayZ Server" from the Steam library Tools list.'
            Record 'DayZServer' 'FAILED anonymous - retry with -SteamUser'
        } elseif (Test-Path -LiteralPath $serverExe) { Record 'DayZServer' "installed ($($paths.ServerDir))" }
        else { Record 'DayZServer' 'FAILED - see SteamCMD output' }
    } else { Record 'DayZServer' 'skipped by user' }
}

if (Want 'GitLFS') {
    if (Find-DzOnPath 'git') { & git lfs install | Out-Null; Record 'GitLFS init' 'git lfs install done (user scope)' }
}
if (Want 'GitHooks') {
    if (Find-DzOnPath 'git') { & git -C (Get-DzRepoRoot) config core.hooksPath .githooks; Record 'GitHooks' 'core.hooksPath=.githooks' }
}
if (Want 'Pillow') {
    if (Find-DzOnPath 'python') {
        # 5.1 turns redirected native stderr into a terminating error under 'Stop' (QA RG-M1)
        $eap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
        & python -c 'import PIL, numpy, yaml' 2>$null      # the asset generators / checks need all three
        $probe = $LASTEXITCODE
        $ErrorActionPreference = $eap
        if ($probe -eq 0) { Record 'Pillow' 'already installed' }
        elseif (Confirm-Install 'Pillow + numpy + PyYAML (pip --user)') { & python -m pip install --user --upgrade Pillow numpy PyYAML; Record 'Pillow' "pip exit $LASTEXITCODE" }
        else { Record 'Pillow' 'skipped by user' }
    } else { Record 'Pillow' 'needs Python first (new terminal after installing)' }
}
if (Want 'VSCodeExtensions') {
    & (Join-DzPath $PSScriptRoot 'Install-VSCodeExtensions.ps1')
    Record 'VSCodeExtensions' 'see output above'
}

Write-DzStep 'Manual downloads'
if (Want 'Mikero') {
    if ($paths.PboProject -and (Test-Path -LiteralPath $paths.PboProject)) { Record 'Mikero' 'already installed' }
    else {
        # No unattended installer/licence-free direct link: user must download and run the installers.
        Record 'Mikero' 'MANUAL: install DePbo + pboProject (+ dependencies) from https://mikero.bytex.digital/Downloads'
        if (Confirm-Install 'nothing - just open the Mikero download page') { Start-Process 'https://mikero.bytex.digital/Downloads' }
    }
}
if (Want 'BlenderAddon') {
    # DayZ Object Builder (Blender 4.4+), installed through Blender's own extension CLI.
    $blender = Find-DzOnPath 'blender'
    if (-not $blender) {
        $blender = Get-ChildItem "$env:ProgramFiles\Blender Foundation" -Recurse -Filter blender.exe -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $blender) { Record 'BlenderAddon' 'needs Blender first' }
    elseif (Confirm-Install 'DayZ Object Builder add-on into Blender (GitHub SXDIST/DayZObjectBuilder latest release)') {
        $rel = Invoke-RestMethod 'https://api.github.com/repos/SXDIST/DayZObjectBuilder/releases/latest' -Headers @{ 'User-Agent' = 'dayz-workspace' }
        $zip = Join-DzPath $env:TEMP 'DZObjectBuilder.zip'
        Invoke-WebRequest -UseBasicParsing -Uri $rel.assets[0].browser_download_url -OutFile $zip
        & $blender --command extension install-file -r user_default --enable $zip
        Record 'BlenderAddon' "DZOB $($rel.tag_name) installed (exit $LASTEXITCODE)"
    } else { Record 'BlenderAddon' 'skipped by user' }
}

Write-DzStep 'Summary'
$log | Format-Table -AutoSize | Out-String | Write-Host
Write-DzInfo 'Next: tools\setup\Initialize-WorkDrive.ps1, New-SigningKey.ps1, Initialize-TestServer.ps1, Test-Toolchain.ps1'
