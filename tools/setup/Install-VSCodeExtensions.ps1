<#
.SYNOPSIS
    Installs the VS Code extensions recommended in .vscode/extensions.json.

.DESCRIPTION
    yuval.enfusion-script - Enforce Script highlighting / go-to-definition.
      After install, point it at the extracted vanilla scripts (P:\scripts)
      as its README describes (VS Code > Settings > search "enfusion").
    ms-vscode.cpptools    - C/C++ (config.cpp, model.cfg, rvmat are C-like).
    redhat.vscode-xml     - XML (types.xml, cfgspawnabletypes.xml, ...).
    eamodio.gitlens       - GitLens.
    ms-vscode.powershell  - for the workspace scripts.
#>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$code = Find-DzOnPath 'code'
if (-not $code) { $code = Find-DzOnPath 'code.cmd' }
if (-not $code) { throw 'VS Code CLI "code" not on PATH. Install VS Code (and reopen the terminal).' }

$wanted = (Get-Content -Raw (Join-DzPath (Get-DzRepoRoot) '.vscode\extensions.json') | ConvertFrom-Json).recommendations
$have = @(& $code --list-extensions)
foreach ($e in $wanted) {
    if ($have -contains $e) { Write-DzOk "$e already installed"; continue }
    & $code --install-extension $e --force | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-DzOk "$e installed" } else { Write-DzFail "$e failed ($LASTEXITCODE)" }
}
