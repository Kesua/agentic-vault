$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$script = Join-Path $PSScriptRoot "telegram_bridge.py"
$config = Join-Path $repoRoot "90_System\secrets\telegram_bridge.env"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python virtualenv not found at $python"
}

if (-not (Test-Path -LiteralPath $config)) {
    throw "Bridge config not found at $config"
}

$env:PYTHONIOENCODING = "utf-8"
& $python $script --config $config
