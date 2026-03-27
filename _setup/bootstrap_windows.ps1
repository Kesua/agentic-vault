# bootstrap_windows.ps1 -- Agentic Vault setup for Windows
# Called by Setup_Windows.bat.  Do not run directly unless you
# are already in the vault root with -ExecutionPolicy Bypass.

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

$MIN_PYTHON_MAJOR = 3
$MIN_PYTHON_MINOR = 9
$VENV_DIR         = ".venv"
$SECRETS_DIR      = "90_System\secrets"
$WIZARD_SCRIPT    = "_setup\wizard\server.py"
$WIZARD_MODULE    = "_setup.wizard.server"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Get-PythonVersion {
    param([string]$Cmd)
    try {
        $raw = & $Cmd --version 2>&1 | Out-String
        if ($LASTEXITCODE -ne 0) { return $null }
        # Guard against the Microsoft Store stub that prints nothing useful
        if ($raw -match "Microsoft Store") { return $null }
        if ($raw -match 'Python (\d+)\.(\d+)\.(\d+)') {
            return @{
                Major = [int]$Matches[1]
                Minor = [int]$Matches[2]
                Patch = [int]$Matches[3]
                Cmd   = $Cmd
                Raw   = $raw.Trim()
            }
        }
    } catch {}
    return $null
}

function Test-PythonMinVersion {
    param([hashtable]$Info)
    return ($Info.Major -eq $MIN_PYTHON_MAJOR -and $Info.Minor -ge $MIN_PYTHON_MINOR)
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  ============================================"
Write-Host "    Agentic Vault Setup"
Write-Host "  ============================================"
Write-Host ""

# ---------------------------------------------------------------------------
# Phase 1 -- Python detection
# ---------------------------------------------------------------------------

Write-Host "  [1/5] Checking Python..."

$PYTHON_CMD = $null

foreach ($candidate in @("python", "python3", "py")) {
    if ($candidate -eq "py") {
        # Python Launcher uses -3 to target Python 3
        $info = Get-PythonVersion "py -3"
        if ($null -eq $info) { $info = Get-PythonVersion "py" }
    } else {
        $info = Get-PythonVersion $candidate
    }
    if ($null -ne $info -and (Test-PythonMinVersion $info)) {
        $PYTHON_CMD = $info.Cmd
        Write-Host "         Found $($info.Raw) at $(Get-Command $candidate -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue)"
        break
    } elseif ($null -ne $info) {
        Write-Host "         Found $($info.Raw) but $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ is required -- skipping"
    }
}

# Fallback: try winget auto-install
if ($null -eq $PYTHON_CMD) {
    $wingetAvailable = Get-Command winget -ErrorAction SilentlyContinue
    if ($wingetAvailable) {
        Write-Host "         Python not found. Installing via winget..."
        $ErrorActionPreference = "Continue"
        winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent 2>&1 | Out-Null
        $ErrorActionPreference = "Stop"

        # Refresh PATH so the new install is visible
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                    [System.Environment]::GetEnvironmentVariable("Path", "User")

        foreach ($candidate in @("python", "python3")) {
            $info = Get-PythonVersion $candidate
            if ($null -ne $info -and (Test-PythonMinVersion $info)) {
                $PYTHON_CMD = $info.Cmd
                Write-Host "         Installed $($info.Raw)"
                break
            }
        }
    }
}

if ($null -eq $PYTHON_CMD) {
    Write-Host ""
    Write-Host "  Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR+ is required but was not found."
    Write-Host "  Please download it from: https://www.python.org/downloads/"
    Write-Host "  After installing, re-run this setup."
    Start-Process "https://www.python.org/downloads/"
    exit 1
}

# ---------------------------------------------------------------------------
# Phase 2 -- Virtual environment
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  [2/5] Creating virtual environment..."

$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"

if (Test-Path $VENV_PYTHON) {
    # Validate the existing venv still works
    try {
        & $VENV_PYTHON --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "         .venv already exists and is valid"
        } else {
            throw "broken"
        }
    } catch {
        Write-Host "         .venv is broken, recreating..."
        Remove-Item -Recurse -Force $VENV_DIR -ErrorAction SilentlyContinue
        & $PYTHON_CMD -m venv $VENV_DIR
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  ERROR: Could not create virtual environment."
            Write-Host "  Try deleting the .venv folder and running setup again."
            exit 1
        }
        Write-Host "         Recreated .venv"
    }
} else {
    & $PYTHON_CMD -m venv $VENV_DIR
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Could not create virtual environment."
        Write-Host "  Try deleting the .venv folder and running setup again."
        exit 1
    }
    Write-Host "         Created .venv"
}

# ---------------------------------------------------------------------------
# Phase 3 -- Dependency installation
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  [3/5] Installing dependencies (this may take a minute)..."

$PIP = Join-Path $VENV_DIR "Scripts\pip.exe"
$UV = Join-Path $VENV_DIR "Scripts\uv.exe"

$ErrorActionPreference = "Continue"
if (-not (Test-Path $UV)) {
    & $PIP install uv --quiet 2>&1 | Out-Null
}

& $UV pip install -r requirements.txt --quiet 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  ERROR: Some packages failed to install."
    Write-Host "  Common fix: install Visual Studio Build Tools from:"
    Write-Host "  https://visualstudio.microsoft.com/visual-cpp-build-tools/"
    Write-Host ""
    Write-Host "  Then re-run this setup."
    exit 1
}

try {
    $ErrorActionPreference = "Continue"
    $pkgCount = (& $UV pip list --format=columns 2>&1 | Measure-Object -Line).Lines - 2
    $ErrorActionPreference = "Stop"
    if ($pkgCount -lt 0) { $pkgCount = 0 }
} catch { $pkgCount = "?" }
Write-Host "         Installed $pkgCount packages"

# ---------------------------------------------------------------------------
# Phase 4 -- Secrets folder
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  [4/5] Preparing secrets folder..."

if (-not (Test-Path $SECRETS_DIR)) {
    New-Item -ItemType Directory -Path $SECRETS_DIR -Force | Out-Null
    Write-Host "         Created $SECRETS_DIR"
} else {
    Write-Host "         $SECRETS_DIR already exists"
}

# ---------------------------------------------------------------------------
# Phase 5 -- Launch wizard
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  [5/5] Starting setup wizard..."

if (-not (Test-Path $WIZARD_SCRIPT)) {
    Write-Host "  ERROR: Wizard not found at $WIZARD_SCRIPT"
    Write-Host "  Your download may be incomplete. Re-download the vault."
    exit 1
}

Write-Host ""
Write-Host "  --------------------------------------------"
Write-Host "  The setup wizard is running."
Write-Host "  When you are done, press Ctrl+C to stop."
Write-Host "  --------------------------------------------"
Write-Host ""

# Run wizard in foreground; server.py opens the browser via webbrowser.open()
& $VENV_PYTHON -m $WIZARD_MODULE
