@echo off
rem Double-click to install the AI video editor (Windows).
cd /d "%~dp0"
set PYTHONUTF8=1
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\install-windows.ps1"
echo.
pause
