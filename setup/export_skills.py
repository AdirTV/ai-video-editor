"""Copy the live skills from ~/.claude/skills into the repo as machine-neutral
templates (paths → placeholders). Run before committing skill changes.

  python3 setup/export_skills.py
"""
import re
import shutil
from pathlib import Path

HOME = Path.home()
REPO = Path(__file__).resolve().parent.parent
SKILLS = ["minecraft-edit", "sfx"]

REPLACE = [
    (str(REPO), "{{MCE_HOME}}"),
    ("/Users/adirgreen/claude/mc-editor", "{{MCE_HOME}}"),
    ("/Users/adirgreen/Desktop/editing/אדיר טיוי/SFX", "{{SFX_LIB}}"),
    ("/Users/adirgreen/Desktop/editing/אדיר טיוי", "{{EDITING_ROOT}}"),
    ("~/Desktop/editing/אדיר טיוי", "{{EDITING_ROOT}}"),
    ("export PATH=/opt/homebrew/bin:$PATH; ", "{{PATH_PREFIX}}"),
    ("export PATH=/opt/homebrew/bin:$PATH;", "{{PATH_PREFIX}}"),
    ("Adir's", "the user's"),
    ("Adir ", "the user "),
    ("Adir.", "the user."),
]

for name in SKILLS:
    src, dst = HOME / ".claude" / "skills" / name, REPO / "skills" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for f in dst.rglob("*.md"):
        text = f.read_text()
        for a, b in REPLACE:
            text = text.replace(a, b)
        left = re.findall(r"/Users/[^\s`'\")]+", text)
        if left:
            print(f"!! {f.relative_to(REPO)} still has machine paths: {left[:3]}")
        f.write_text(text)
    print("exported", name)
