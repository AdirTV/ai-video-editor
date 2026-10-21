@echo off
rem Double-click to update the AI video editor (Windows).
cd /d "%~dp0"
uv run python setup\update.py
echo.
pause
