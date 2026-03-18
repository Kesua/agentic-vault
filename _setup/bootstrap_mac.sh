#!/usr/bin/env bash
# bootstrap_mac.sh -- Agentic Vault setup for macOS / Linux
# Called by Setup_Mac.command.  Can also be run directly:
#   bash _setup/bootstrap_mac.sh

set -euo pipefail

VAULT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$VAULT_ROOT"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=9
VENV_DIR=".venv"
SECRETS_DIR="90_System/secrets"
WIZARD_SCRIPT="_setup/wizard/server.py"
PYTHON_CMD=""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

detect_python() {
    for cmd in python3 python; do
        if command -v "$cmd" &>/dev/null; then
            local raw
            raw=$("$cmd" --version 2>&1) || continue
            if [[ "$raw" =~ Python\ ([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
                local major="${BASH_REMATCH[1]}"
                local minor="${BASH_REMATCH[2]}"
                if (( major == MIN_PYTHON_MAJOR && minor >= MIN_PYTHON_MINOR )); then
                    PYTHON_CMD="$cmd"
                    echo "         Found $raw at $(command -v "$cmd")"
                    return 0
                else
                    echo "         Found $raw but ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required -- skipping"
                fi
            fi
        fi
    done
    return 1
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

echo ""
echo "  ============================================"
echo "    Agentic Vault Setup"
echo "  ============================================"
echo ""

# ---------------------------------------------------------------------------
# Phase 1 -- Python detection
# ---------------------------------------------------------------------------

echo "  [1/5] Checking Python..."

if ! detect_python; then
    if command -v brew &>/dev/null; then
        echo "         Python not found. Installing via Homebrew..."
        brew install python@3.12
        if ! detect_python; then
            echo "  ERROR: Homebrew installed Python but it is not on PATH."
            echo "  Try opening a new terminal and re-running setup."
            exit 1
        fi
    else
        echo ""
        echo "  Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required but was not found."
        echo "  Install options:"
        echo "    1. Install Homebrew: https://brew.sh"
        echo "    2. Download Python:  https://www.python.org/downloads/"
        echo ""
        echo "  After installing, re-run this setup."
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Phase 2 -- Virtual environment
# ---------------------------------------------------------------------------

echo ""
echo "  [2/5] Creating virtual environment..."

VENV_PYTHON="$VENV_DIR/bin/python"

if [[ -x "$VENV_PYTHON" ]]; then
    if "$VENV_PYTHON" --version &>/dev/null; then
        echo "         .venv already exists and is valid"
    else
        echo "         .venv is broken, recreating..."
        rm -rf "$VENV_DIR"
        "$PYTHON_CMD" -m venv "$VENV_DIR"
        echo "         Recreated .venv"
    fi
else
    "$PYTHON_CMD" -m venv "$VENV_DIR" || {
        echo "  ERROR: Could not create virtual environment."
        echo "  On some systems you may need:  sudo apt install python3-venv"
        exit 1
    }
    echo "         Created .venv"
fi

# ---------------------------------------------------------------------------
# Phase 3 -- Dependency installation
# ---------------------------------------------------------------------------

echo ""
echo "  [3/5] Installing dependencies (this may take a minute)..."

PIP="$VENV_DIR/bin/pip"

"$PIP" install -r requirements.txt --quiet 2>&1 || {
    echo ""
    echo "  ERROR: Some packages failed to install."
    echo "  If you see compiler errors, try:  xcode-select --install"
    echo "  Then re-run this setup."
    exit 1
}

PKG_COUNT=$("$PIP" list --format=columns 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
echo "         Installed ${PKG_COUNT} packages"

# ---------------------------------------------------------------------------
# Phase 4 -- Secrets folder
# ---------------------------------------------------------------------------

echo ""
echo "  [4/5] Preparing secrets folder..."

if [[ ! -d "$SECRETS_DIR" ]]; then
    mkdir -p "$SECRETS_DIR"
    echo "         Created $SECRETS_DIR"
else
    echo "         $SECRETS_DIR already exists"
fi

# ---------------------------------------------------------------------------
# Phase 5 -- Launch wizard
# ---------------------------------------------------------------------------

echo ""
echo "  [5/5] Starting setup wizard..."

if [[ ! -f "$WIZARD_SCRIPT" ]]; then
    echo "  ERROR: Wizard not found at $WIZARD_SCRIPT"
    echo "  Your download may be incomplete. Re-download the vault."
    exit 1
fi

echo ""
echo "  --------------------------------------------"
echo "  The setup wizard is running."
echo "  When you are done, press Ctrl+C to stop."
echo "  --------------------------------------------"
echo ""

# Run wizard in foreground; server.py opens the browser via webbrowser.open()
"$VENV_DIR/bin/python" "$WIZARD_SCRIPT"
