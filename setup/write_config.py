"""Write ~/.mce/config.json for the installers (Mac and Windows), keeping what's already there.

  uv run python setup/write_config.py [--editing-root PATH] [--language he|en|auto] [--minecraft 1|0]
                                       [--export-via auto|ame|premiere]

Re-running the installer only changes what was asked for: an existing editing folder, hf_token or any other
setting stays. Also creates the SFX library folders. Written as UTF-8 without a BOM on every OS.
"""
import argparse
import json
from pathlib import Path

DEFAULT_ROOT = "~/Desktop/editing"
SFX_KINDS = ["whoosh", "pop", "beep", "click", "shutter", "typing", "riser", "impact", "ding", "magic", "glitch"]

ap = argparse.ArgumentParser()
ap.add_argument("--editing-root", default="")
ap.add_argument("--language", default="")
ap.add_argument("--minecraft", choices=["0", "1"], default="")
ap.add_argument("--export-via", choices=["auto", "ame", "premiere"], default="",
                help="render exports in Adobe Media Encoder (auto: when installed) or inside Premiere")
a = ap.parse_args()

path = Path.home() / ".mce" / "config.json"
path.parent.mkdir(exist_ok=True)
try:
    cfg = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
except json.JSONDecodeError:
    path.replace(path.with_suffix(".broken.json"))
    print(f"⚠️  {path} was unreadable; kept a copy as config.broken.json and started fresh")
    cfg = {}

root = a.editing_root or cfg.get("editing_root") or DEFAULT_ROOT
if a.editing_root or "sfx_lib" not in cfg:  # a moved editing folder takes its SFX library along
    cfg["sfx_lib"] = str(Path(root) / "SFX")
cfg["editing_root"] = root
cfg["language"] = a.language or cfg.get("language") or "auto"
cfg.setdefault("profile", "general")
if a.minecraft:
    cfg["minecraft"] = a.minecraft == "1"
cfg.setdefault("minecraft", True)
if a.export_via:
    cfg["export_via"] = a.export_via
cfg.setdefault("export_via", "auto")
path.write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")

lib = Path(cfg["sfx_lib"]).expanduser()
for k in SFX_KINDS + (["minecraft"] if cfg["minecraft"] else []):
    (lib / k).mkdir(parents=True, exist_ok=True)
print("settings:", path, "| editing folder:", Path(root).expanduser(), "| SFX library:", lib,
      "| exports:", {"auto": "Media Encoder when installed", "ame": "Media Encoder", "premiere": "inside Premiere"}
      .get(cfg["export_via"], cfg["export_via"]))
