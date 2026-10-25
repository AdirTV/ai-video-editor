"""Per-machine settings, so the same tools run on any Mac or Windows PC.

Read from ~/.mce/config.json (written by the installer), overridable with env vars:
  editing_root  MCE_EDITING_ROOT  where projects live      (default ~/Desktop/editing)
  sfx_lib       MCE_SFX_LIB       sound-effects library    (default <editing_root>/SFX)
  language      MCE_LANGUAGE      "he" | "en" | "auto"     (default auto: detected from the audio)
  profile       MCE_PROFILE       "general" | "minecraft"  (default general; minecraft adds HUD detection)
  hf_token      HF_TOKEN          Hugging Face token       (only for speaker diarization: --speakers)
  export_via    MCE_EXPORT_VIA    "auto" | "ame" | "premiere"  (default auto: Media Encoder when installed)
"""
import json
import os
import shutil
from pathlib import Path

MCE_HOME = Path(__file__).resolve().parent.parent
_cfg_path = Path.home() / ".mce" / "config.json"
_cfg = json.loads(_cfg_path.read_text(encoding="utf-8-sig")) if _cfg_path.exists() else {}

EDITING_ROOT = Path(os.environ.get("MCE_EDITING_ROOT") or _cfg.get("editing_root") or Path.home() / "Desktop" / "editing").expanduser()
LANGUAGE = (os.environ.get("MCE_LANGUAGE") or _cfg.get("language") or "auto").lower()
PROFILE = (os.environ.get("MCE_PROFILE") or _cfg.get("profile") or "general").lower()
HF_TOKEN = os.environ.get("HF_TOKEN") or _cfg.get("hf_token")  # None → huggingface-cli login cache
SFX_LIB = Path(os.environ.get("MCE_SFX_LIB") or _cfg.get("sfx_lib") or EDITING_ROOT / "SFX").expanduser()
MINECRAFT = bool(_cfg.get("minecraft", True))  # installer: --no-minecraft → False
EXPORT_VIA = (os.environ.get("MCE_EXPORT_VIA") or _cfg.get("export_via") or "auto").lower()
PREMIERE_MCP_VERSION = "1.24.1"  # the one place this is pinned; installers, update and doctor read it from here


def premiere_server() -> list[str]:
    """Command that starts the premiere-pro-mcp server on this machine."""
    exe = shutil.which("premiere-pro-mcp") or shutil.which("premiere-pro-mcp.cmd")
    if not exe:  # npm global bin not on PATH (common with user-local Node installs)
        for d in (Path.home() / ".local" / "node" / "bin", Path(os.environ.get("APPDATA", "")) / "npm"):
            for name in ("premiere-pro-mcp", "premiere-pro-mcp.cmd"):
                if (d / name).exists():
                    exe = str(d / name)
    if exe:
        return [exe]
    # Windows: npx is npx.cmd, which Popen only finds by its full name
    return [shutil.which("npx") or shutil.which("npx.cmd") or "npx", "-y", f"premiere-pro-mcp@{PREMIERE_MCP_VERSION}"]
