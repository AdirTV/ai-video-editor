#!/bin/bash
# AI video editor for Premiere — one-shot installer for macOS.
# Run from the repo:  bash setup/install-mac.sh [--editing-root PATH] [--language he|en|auto] [--no-minecraft] [--yes]
#   --yes  never prompt (for an AI assistant running the install); default editing root is
#          ~/Desktop/editing unless --editing-root is given.
# Exit code 10 = Homebrew must be installed by the user first (it needs their password).
set -e
cd "$(dirname "$0")/.."
YES=0; ER=""; LANG_OPT="auto"; MC=1
while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y) YES=1 ;;
    --editing-root) ER="$2"; shift ;;
    --language) LANG_OPT="$2"; shift ;;
    --no-minecraft) MC=0 ;;
  esac
  shift
done
REPO="$(pwd)"
step() { printf "\n\033[1;35m== %s\033[0m\n" "$1"; }

step "1/8 Homebrew"
if [ ! -x /opt/homebrew/bin/brew ] && ! command -v brew >/dev/null; then
  if [ "$YES" = 1 ] || [ ! -t 0 ]; then
    echo "Homebrew is missing and its installer needs the user's password."
    echo 'Ask the user to run this in their own Terminal, then re-run this script:'
    echo '  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
    exit 10
  fi
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || brew shellenv)"
grep -q 'brew shellenv' ~/.zprofile 2>/dev/null || echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile

step "2/8 ffmpeg, Node, uv, yt-dlp"
brew install ffmpeg node uv yt-dlp

step "3/8 Claude Code"
if ! command -v claude >/dev/null && [ ! -x "$HOME/.local/bin/claude" ]; then
  curl -fsSL https://claude.ai/install.sh | bash
fi
CLAUDE="$(command -v claude || echo "$HOME/.local/bin/claude")"

step "4/8 Premiere MCP bridge + panel"
npm install -g premiere-pro-mcp@1.24.1
premiere-pro-mcp --install-cep
bash panel/install.sh

step "5/8 Editing tools (Python + Remotion)"
uv sync
(cd remotion && npm install)

step "6/8 Settings"
if [ -z "$ER" ] && [ "$YES" = 0 ] && [ -t 0 ]; then
  read -r -p "Where do you keep your editing projects? [~/Desktop/editing]: " ER
fi
ER="${ER:-~/Desktop/editing}"
uv run python - "$ER" "$LANG_OPT" "$MC" <<'PY'
import json, sys
from pathlib import Path
root, language, mc = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
cfg = Path.home() / ".mce" / "config.json"
cfg.parent.mkdir(exist_ok=True)
cfg.write_text(json.dumps({"editing_root": root, "sfx_lib": root.rstrip("/") + "/SFX", "language": language,
                           "profile": "general", "minecraft": mc}, ensure_ascii=False))
lib = Path(root).expanduser() / "SFX"
for k in ["whoosh", "pop", "riser", "impact", "ding", "click", "magic", "glitch"] + (["minecraft"] if mc else []):
    (lib / k).mkdir(parents=True, exist_ok=True)
print("settings:", cfg, "| SFX library:", lib)
PY
if [ ! -f style.md ]; then
  if [ "$LANG_OPT" = "en" ]; then cp style.template.en.md style.md; else cp style.template.md style.md; fi
fi
[ -f vocab.txt ] || : > vocab.txt

step "7/8 Skills"
if [ "$MC" = 1 ]; then uv run python setup/install_skills.py; else uv run python setup/install_skills.py --skip minecraft-edit; fi
npx -y skills add remotion-dev/skills -g -a claude-code -y

step "8/8 Connect Premiere to Claude"
"$CLAUDE" mcp remove premiere -s user >/dev/null 2>&1 || true
"$CLAUDE" mcp add premiere -s user -e PREMIERE_MCP_TOOL_PACKS=essential,inspection,captions -- premiere-pro-mcp

uv run python setup/doctor.py || true
printf "\n\033[1;32mDone.\033[0m Next: restart Premiere → Window > Extensions > MCP for Adobe Premiere Pro → Start.\n"
printf "Then open a terminal in your project folder and run: claude\n"
