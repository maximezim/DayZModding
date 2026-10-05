<#
.SYNOPSIS
    Scaffolds mods\<ModName> from templates\<Template> (default ModTemplate).

.DESCRIPTION
    Copies the template and replaces the literal template name in file
    contents and paths. Produces an empty mod (CfgPatches only).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z][A-Za-z0-9_]*$')][string]$ModName,
    [string]$Template = 'ModTemplate',
    [string]$Author = '',
    [string]$DestinationRoot
)
$ErrorActionPreference = 'Stop'
Import-Module (Join-Path $PSScriptRoot '..\lib\DzCommon.psm1') -Force

$repo = Get-DzRepoRoot
$src  = Join-DzPath $repo 'templates' $Template
if (-not $DestinationRoot) { $DestinationRoot = Join-DzPath $repo 'mods' }
$dst  = Join-DzPath $DestinationRoot $ModName
if (-not (Test-Path -LiteralPath $src)) { throw "Template $src not found." }
if (Test-Path -LiteralPath $dst) { throw "$dst already exists." }

Copy-Item -LiteralPath $src -Destination $dst -Recurse
Remove-Item -LiteralPath (Join-DzPath $dst 'README.md') -ErrorAction SilentlyContinue
foreach ($f in Get-ChildItem -LiteralPath $dst -Recurse -File) {
    if ($f.Extension -in '.cpp', '.c', '.h', '.hpp', '.xml', '.json', '.txt', '.cfg', '.rvmat', '.layout', '') {
        $t = Get-Content -Raw -LiteralPath $f.FullName
        $t = $t.Replace($Template, $ModName)
        if ($f.Name -eq 'mod.cpp') { $t = $t -replace 'author = "";', ('author = "' + $Author + '";') }
        # No BOM: Bohemia config parsers do not expect one.
        [System.IO.File]::WriteAllText($f.FullName, $t, (New-Object System.Text.UTF8Encoding($false)))
    }
}
Get-ChildItem -LiteralPath $dst -Recurse | Sort-Object { $_.FullName.Length } -Descending |
    Where-Object { $_.Name -like "*$Template*" } |
    ForEach-Object { Rename-Item -LiteralPath $_.FullName -NewName ($_.Name.Replace($Template, $ModName)) }
Write-DzOk "Created $dst"
