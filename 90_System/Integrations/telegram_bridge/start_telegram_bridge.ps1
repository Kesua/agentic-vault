$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$script = Join-Path $PSScriptRoot "telegram_bridge.py"
$config = Join-Path $repoRoot "90_System\secrets\telegram_bridge.env"
$runtimeDir = Join-Path $PSScriptRoot "runtime"
$pidFile = Join-Path $runtimeDir "bridge.pid"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtualenv not found at $python"
}

if (-not (Test-Path -LiteralPath $script)) {
    throw "Bridge script not found at $script"
}

if (-not (Test-Path -LiteralPath $config)) {
    throw "Bridge config not found at $config"
}

New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null

if (Test-Path -LiteralPath $pidFile) {
    $existingPidText = (Get-Content -LiteralPath $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($existingPidText) {
        $existingPid = 0
        if ([int]::TryParse($existingPidText, [ref]$existingPid)) {
            $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
            if ($existingProcess) {
                Write-Output "Bridge is already running with PID $existingPid."
                exit 0
            }
        }
    }
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
}

$env:PYTHONIOENCODING = "utf-8"
$process = Start-Process -FilePath $python -ArgumentList @($script, "--config", $config) -WorkingDirectory $repoRoot -PassThru -WindowStyle Hidden
Start-Sleep -Seconds 2

$runningProcess = Get-Process -Id $process.Id -ErrorAction SilentlyContinue
if (-not $runningProcess) {
    Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
    throw "Bridge process exited immediately after startup. Check 90_System\\Logs\\telegram_bridge\\*.log for details."
}

Set-Content -LiteralPath $pidFile -Value $process.Id -Encoding ascii

Write-Output "Bridge started with PID $($process.Id)."
