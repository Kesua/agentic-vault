@echo off
REM Agentic Vault -- double-click this file to set up.
REM It launches PowerShell which does the real work.

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "_setup\bootstrap_windows.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo Setup encountered an error. See above for details.
)
pause
