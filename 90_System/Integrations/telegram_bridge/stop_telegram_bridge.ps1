$ErrorActionPreference = "Stop"

$runtimeDir = Join-Path $PSScriptRoot "runtime"
$pidFile = Join-Path $runtimeDir "bridge.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Output "Bridge PID file not found. Bridge is likely not running."
    exit 0
}

$pidText = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
if (-not $pidText) {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Output "Bridge PID file was empty. Removed stale PID file."
    exit 0
}

$bridgePid = 0
if (-not [int]::TryParse($pidText, [ref]$bridgePid)) {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    throw "Invalid bridge PID file content: $pidText"
}

$process = Get-Process -Id $bridgePid -ErrorAction SilentlyContinue
if (-not $process) {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    Write-Output "Bridge process $bridgePid was not running. Removed stale PID file."
    exit 0
}

Stop-Process -Id $bridgePid -Force
Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue

Write-Output "Bridge process $bridgePid stopped."
