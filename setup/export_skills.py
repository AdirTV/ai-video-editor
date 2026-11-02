"""Copy the live skills from ~/.claude/skills into the repo (and add-ons' skills into plugins/<name>/skills/)
as machine-neutral templates (paths → placeholders). Run before committing skill changes.

  python3 setup/export_skills.py
"""
import platform
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from mce.config import EDITING_ROOT, SFX_LIB  # noqa: E402
from mce.plugins import skill_dirs  # noqa: E402

SKILLS = {name: REPO / "skills" / name for name in ("video-edit", "sfx")} | {d.name: d for d in skill_dirs()}


def _home_form(p: Path) -> str:
    return "~/" + p.relative_to(HOME).as_posix() if p.is_relative_to(HOME) else p.as_posix()


# this machine's paths → placeholders (install_skills.py does the reverse); longest first
REPLACE = [
    (REPO.as_posix(), "{{MCE_HOME}}"),
    (SFX_LIB.as_posix(), "{{SFX_LIB}}"),
    (_home_form(SFX_LIB), "{{SFX_LIB}}"),
    (EDITING_ROOT.as_posix(), "{{EDITING_ROOT}}"),
    (_home_form(EDITING_ROOT), "{{EDITING_ROOT}}"),
]
if platform.system() == "Darwin":
    REPLACE += [("export PATH=/opt/homebrew/bin:$PATH; ", "{{PATH_PREFIX}}"),
                ("export PATH=/opt/homebrew/bin:$PATH;", "{{PATH_PREFIX}}")]

for name, dst in SKILLS.items():
    src = HOME / ".claude" / "skills" / name
    # files that exist only in the repo copy would be lost by the rmtree below — bring them into the live skill first
    if dst.exists():
        for f in dst.rglob("*"):
            live = src / f.relative_to(dst)
            if f.is_file() and not live.exists():
                live.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, live)
                print(f"kept {f} (copied into the live skill)")
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for f in dst.rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        for a, b in REPLACE:
            text = text.replace(a, b)
        left = re.findall(r"(?:/Users/|/home/|[A-Z]:\\Users\\)[^\s`'\")]+", text)
        if left:
            print(f"!! {f} still has machine paths: {left[:3]}")
        f.write_text(text, encoding="utf-8")
    print("exported", name)
