"""Add-ons: optional folders in plugins/<name>/ (gitignored) that extend the editor for one kind of video.

A plugin may ship, all optional:
  skills/<skill>/SKILL.md   installed with the editor's skills (setup/install_skills.py)
  remotion/index.tsx        exports `Compositions`; Studio and renders pick it up (remotion/src/loadProjects.tsx)
  public/                   copied into remotion/public/ by setup/install_skills.py (images, fonts)
  mce_plugin.py             Python hooks, all optional:
      PROFILES = {"<name>": {
          "prompts": {"he": "...", "en": "..."},   words that prime transcription (`--profile <name>`)
          "hud": fn(frame_rgb_int16) -> dict,       per-sample picture signals: heart_px, menu (0..1), …
          "finish": fn(samples) -> None,            after the scan, e.g. turn heart pixels into health 0-10
      }}
      SFX_KINDS = {"<kind>": {"folder": "<word in a folder name>", "level": -24, "max_len": 5}}
          an extra sound-effects kind (its folders win over filename keywords)
"""
import importlib.util
from functools import cache
from pathlib import Path

from .config import MCE_HOME

PLUGINS_DIR = MCE_HOME / "plugins"


@cache
def modules() -> list:
    out = []
    for f in sorted(PLUGINS_DIR.glob("*/mce_plugin.py")):
        spec = importlib.util.spec_from_file_location(f"mce_plugin_{f.parent.name.replace('-', '_')}", f)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out.append(mod)
    return out


def profiles() -> dict[str, dict]:
    """Analysis profiles the add-ons provide ("general" is built in and has no hooks)."""
    return {name: p for m in modules() for name, p in getattr(m, "PROFILES", {}).items()}


def profile(name: str) -> dict:
    return profiles().get(name, {})


def sfx_kinds() -> dict[str, dict]:
    return {k: v for m in modules() for k, v in getattr(m, "SFX_KINDS", {}).items()}


def skill_dirs() -> list[Path]:
    return sorted(d for d in PLUGINS_DIR.glob("*/skills/*") if (d / "SKILL.md").exists())
