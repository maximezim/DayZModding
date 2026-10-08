<#
.SYNOPSIS
    Creates a DayZ signing keypair (.biprivatekey + .bikey) OUTSIDE the repo.

.DESCRIPTION
    Uses DayZ Tools\Bin\DsUtils\DSCreateKey.exe, which writes
    <KeyName>.biprivatekey and <KeyName>.bikey to the current directory.
    Keys go to signing.keyDir (default %USERPROFILE%\.dayz-keys); the folder
    ACL is restricted to the current user. The key name is saved in the
    git-ignored workspace.config.json.

    Back up the .biprivatekey somewhere safe (password manager / offline).
    Losing it means every server must swap to a new .bikey; leaking it lets
    anyone ship PBOs your servers will trust.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9_]+$')][string]$KeyName,
    [string]$KeyDir
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$cfg   = Get-DzConfig
$paths = Get-DzPaths -Config $cfg
if (-not $KeyDir) { $KeyDir = $paths.KeyDir }
$KeyDir = [System.IO.Path]::GetFullPath($KeyDir)
if (Test-DzPathInRepo $KeyDir) {
    throw "Refusing to create keys inside the repository ($KeyDir)."
}
Assert-DzTool 'DSCreateKey.exe' $paths.DSCreateKey

$priv = Join-DzPath $KeyDir "$KeyName.biprivatekey"
$pub  = Join-DzPath $KeyDir "$KeyName.bikey"
if ((Test-Path -LiteralPath $priv) -or (Test-Path -LiteralPath $pub)) {
    throw "Key '$KeyName' already exists in $KeyDir. Pick another name; never overwrite a released key."
}

Write-DzStep "Create keypair '$KeyName' in $KeyDir"
New-Item -ItemType Directory -Force -Path $KeyDir | Out-Null
# Owner-only access: drop inherited ACEs, grant full control to the current user.
& icacls $KeyDir /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" | Out-Null

Invoke-DzTool -FilePath $paths.DSCreateKey -ArgumentList @($KeyName) -WorkingDirectory $KeyDir | Out-Null
if (-not (Test-Path -LiteralPath $priv) -or -not (Test-Path -LiteralPath $pub)) { throw 'DSCreateKey did not produce both key files.' }

Set-DzConfigValue -Key 'signing.keyName' -Value $KeyName
Set-DzConfigValue -Key 'signing.keyDir'  -Value $KeyDir
Write-DzOk "Private: $priv  (keep secret, back it up)"
Write-DzOk "Public : $pub   (ship in @Mod\keys, install in <server>\keys)"
