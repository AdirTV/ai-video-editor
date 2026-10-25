"""Check that every part of the AI editor is installed and connected.

  uv run python setup/doctor.py          (exit code 0 = all required parts OK)

Prints ✅ / ❌ per part with the fix for anything missing. Safe to run any time;
it changes nothing.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
HOME = Path.home()
WIN = platform.system() == "Windows"
results: list[tuple[bool, bool, str, str]] = []  # (ok, required, name, fix)


def check(name: str, ok: bool, fix: str, required: bool = True) -> None:
    results.append((ok, required, name, fix))


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


installer = "setup\\install-windows.ps1 -Yes" if WIN else "bash setup/install-mac.sh --yes"

check("ffmpeg", have("ffmpeg"), "Windows: winget install Gyan.FFmpeg | Mac: brew install ffmpeg (then reopen the terminal)")
check("Node.js / npm", have("npm"), "Windows: winget install OpenJS.NodeJS.LTS | Mac: brew install node")
check("uv (Python)", have("uv"), "Windows: winget install astral-sh.uv | Mac: brew install uv")
check("Python environment", (REPO / ".venv").exists(), f"run: uv sync   (in {REPO})")
check("Remotion packages", (REPO / "remotion" / "node_modules").exists(), "run: cd remotion && npm install")
check("git (updates)", have("git"), "Windows: winget install Git.Git | Mac: xcode-select --install")
check("Claude Code in the terminal", have("claude") or (HOME / ".local" / "bin" / ("claude.exe" if WIN else "claude")).exists(),
      "only needed to run `claude` in a terminal (the desktop app has its own) — Windows: irm https://claude.ai/install.ps1 | iex"
      " | Mac: curl -fsSL https://claude.ai/install.sh | bash", required=False)
check("yt-dlp (B-roll search)", have("yt-dlp"), "Windows: winget install yt-dlp.yt-dlp | Mac: brew install yt-dlp", required=False)
if WIN:
    check("Python UTF-8 mode (Hebrew output)", os.environ.get("PYTHONUTF8") == "1",
          '[Environment]::SetEnvironmentVariable("PYTHONUTF8","1","User"), then reopen the terminal', required=False)

from mce.config import EDITING_ROOT, PREMIERE_MCP_VERSION, SFX_LIB, premiere_server  # noqa: E402

cfg = HOME / ".mce" / "config.json"
check("settings (~/.mce/config.json)", cfg.exists(), f"re-run the installer: {installer}")
check(f"editing folder ({EDITING_ROOT})", EDITING_ROOT.exists(), "create it, or re-run the installer with --editing-root")
check(f"SFX library ({SFX_LIB})", SFX_LIB.exists(), "re-run the installer (creates the folders); add sounds later", required=False)

srv = premiere_server()
installed = "npx" not in Path(srv[0]).name.lower()
check("premiere-pro-mcp", installed, f"npm install -g premiere-pro-mcp@{PREMIERE_MCP_VERSION}")
if installed:
    try:
        v = subprocess.run([srv[0], "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=20).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        v = ""
    if v:
        check(f"premiere-pro-mcp version ({v})", PREMIERE_MCP_VERSION in v,
              f"npm install -g premiere-pro-mcp@{PREMIERE_MCP_VERSION}", required=False)
if installed:
    from patch_mcp import patch  # noqa: E402  (same folder as this script)
    probs = patch()
    check("premiere-pro-mcp local fixes (no XML dialogs)", not probs, "; ".join(probs), required=False)
cep = (Path(os.environ.get("APPDATA", "")) / "Adobe" / "CEP" / "extensions" / "MCPBridgeCEP") if WIN else \
      (HOME / "Library" / "Application Support" / "Adobe" / "CEP" / "extensions" / "MCPBridgeCEP")
check("Premiere panel installed", (cep / "index.html").exists(), "premiere-pro-mcp --install-cep, then restart Premiere")
check("panel design", (cep / "index.html").exists() and "cmd-count" in (cep / "index.html").read_text(errors="ignore"),
      "bash panel/install.sh (Mac) or re-run the installer", required=False)

skills = HOME / ".claude" / "skills"
_cfgd = json.loads(cfg.read_text(encoding="utf-8-sig")) if cfg.exists() else {}
for s in ("video-edit", "sfx") + (("minecraft-edit",) if _cfgd.get("minecraft", True) else ()):
    md = skills / s / "SKILL.md"
    check(f"skill: {s}", md.exists(), "uv run python setup/install_skills.py")
    if md.exists() and "uv run" in (text := md.read_text(encoding="utf-8")):
        # skills have this repo's path baked in: a moved repo needs them re-installed
        check(f"skill {s} points at this folder", REPO.as_posix() in text, "uv run python setup/install_skills.py")
check("your style file (style.md)", (REPO / "style.md").exists(),
      "copy style.template.md (Hebrew) or style.template.en.md (English) to style.md", required=False)
check("your vocabulary file (vocab.txt)", (REPO / "vocab.txt").exists(), "create an empty vocab.txt", required=False)
check("Remotion skills", any(skills.glob("remotion-*")),
      "npx -y skills add remotion-dev/skills -g -a claude-code -y", required=False)

check("brand (brand.json: channel name, colours, logo)", (REPO / "brand.json").exists(),
      "cp brand.example.json brand.json, then set your channel name and colours", required=False)
try:
    behind = subprocess.run(["git", "rev-list", "--count", "HEAD..origin/main"], cwd=REPO, capture_output=True,
                            text=True, encoding="utf-8", errors="replace").stdout.strip()
    check("up to date (as of the last check)", behind in ("", "0"), f"{behind} update(s) waiting: uv run python setup/update.py",
          required=False)
except OSError:
    pass

claude_json = HOME / ".claude.json"
registered = False
if claude_json.exists():
    try:
        registered = "premiere" in json.loads(claude_json.read_text(encoding="utf-8")).get("mcpServers", {})
    except json.JSONDecodeError:
        pass
check("Premiere connected to Claude Code", registered,
      "claude mcp add premiere -s user -e PREMIERE_MCP_TOOL_PACKS=essential,inspection,captions -- premiere-pro-mcp")

# Live check (optional): only works while Premiere is open with the panel running.
live = False
try:
    from mce.premiere import Client
    c = Client()
    try:
        live = '"connected": true' in c.call("ping", {})
    finally:
        c.close()
except Exception:
    pass
check("Premiere is open and the panel is running", live,
      "open Premiere → Window > Extensions > MCP for Adobe Premiere Pro → Start", required=False)

bad = 0
for ok, required, name, fix in results:
    mark = "✅" if ok else ("❌" if required else "⚠️ ")
    print(f"{mark} {name}" + ("" if ok else f"\n     → {fix}"))
    bad += (not ok) and required
print("\nAll required parts are installed." if not bad else f"\n{bad} required part(s) missing — fix the ❌ lines above.")
sys.exit(1 if bad else 0)
