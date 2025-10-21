param(
    [Parameter(Mandatory=$true)]
    [string]$Source
)

$ErrorActionPreference = "Stop"

function Resolve-PathStrict([string]$p) {
    $full = Resolve-Path -Path $p -ErrorAction Stop
    return $full.Path
}

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) # bell_player
$dist = Join-Path $root "dist/BellPlayer"
if (!(Test-Path $dist)) {
    throw "dist/BellPlayer not found. Build the app first (PyInstaller)."
}

$src = Resolve-PathStrict $Source

# Accept either: path to ffmpeg root (containing bin\ffplay.exe) OR directly bin folder
$ffplayPath = Join-Path $src "bin/ffplay.exe"
if (!(Test-Path $ffplayPath)) {
    $ffplayPath = Join-Path $src "ffplay.exe"
    if (!(Test-Path $ffplayPath)) {
        throw "ffplay.exe not found under '$Source'. Provide path to FFmpeg 'bin' folder or FFmpeg root."
    }
    $srcBin = Split-Path -Parent $ffplayPath
} else {
    $srcBin = Split-Path -Parent $ffplayPath
}

$dest = Join-Path $dist "ffmpeg/bin"
New-Item -ItemType Directory -Path $dest -Force | Out-Null

Write-Host "Copying FFmpeg binaries from '$srcBin' -> '$dest'" -ForegroundColor Cyan
Copy-Item -Path (Join-Path $srcBin "*") -Destination $dest -Recurse -Force

Write-Host "Portable FFmpeg bundled successfully at: $dest" -ForegroundColor Green



