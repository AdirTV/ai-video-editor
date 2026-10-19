@echo off
rem Double-click to install the AI video editor (Windows).
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\install-windows.ps1"
echo.
pause
