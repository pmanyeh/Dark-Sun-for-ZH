[CmdletBinding()]
param(
    [string]$GameDirectory,
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

if (-not $GameDirectory) {
    $GameDirectory = Join-Path $projectRoot 'from Steam\games\Dark Sun-ENG\GAME\DARKSUN'
}
if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $projectRoot 'localization\opends'
}

$openDsRoot = Join-Path $projectRoot 'vendor\opends'
$releaseDir = Join-Path $openDsRoot 'target\release'
$disassembler = Join-Path $releaseDir 'gpl-disasm.exe'
$gffCat = Join-Path $releaseDir 'gff-cat.exe'
$extractor = Join-Path $openDsRoot 'tools\dialog-extract\dialog-extract.py'
$gplData = Join-Path $GameDirectory 'GPLDATA.GFF'
$resource = Join-Path $GameDirectory 'RESOURCE.GFF'

foreach ($required in @($disassembler, $gffCat, $extractor, $gplData, $resource)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required file not found: $required"
    }
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$env:PATH = $releaseDir + [IO.Path]::PathSeparator + $env:PATH

$transcript = Join-Path $OutputDirectory 'ds1-dialog.txt'
$json = Join-Path $OutputDirectory 'ds1-dialog.json'

& python $extractor $gplData --text-source $resource --format transcript -o $transcript
if ($LASTEXITCODE -ne 0) { throw "Transcript extraction failed with exit code $LASTEXITCODE" }

& python $extractor $gplData --text-source $resource --pretty -o $json
if ($LASTEXITCODE -ne 0) { throw "JSON extraction failed with exit code $LASTEXITCODE" }

Get-Item -LiteralPath $transcript, $json | Select-Object Name, Length, FullName
