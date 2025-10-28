$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) # bell_player
$dist = Join-Path $root "dist/BellPlayer"
if (!(Test-Path $dist)) { throw "dist/BellPlayer not found. Build first." }

$zipOut = Join-Path $root "dist/BellPlayer-portable.zip"
if (Test-Path $zipOut) { Remove-Item $zipOut -Force }

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($dist, $zipOut)

Write-Host "Created portable ZIP: $zipOut" -ForegroundColor Green







