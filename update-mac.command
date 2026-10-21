#!/bin/bash
# Double-click in Finder to update the AI video editor.
cd "$(dirname "$0")"
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || brew shellenv 2>/dev/null)"
uv run python setup/update.py
echo
read -n 1 -s -r -p "Press any key to close"
