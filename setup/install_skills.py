"""Install this repo's skills into ~/.claude/skills with this machine's paths.

  uv run python setup/install_skills.py [--skip minecraft-edit]
"""
import platform
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(REPO))
from mce.config import EDITING_ROOT, SFX_LIB  # noqa: E402

subs = {
    "{{MCE_HOME}}": REPO.as_posix(),
    "{{EDITING_ROOT}}": EDITING_ROOT.as_posix(),
    "{{SFX_LIB}}": SFX_LIB.as_posix(),
    "{{PATH_PREFIX}}": "export PATH=/opt/homebrew/bin:$PATH; " if platform.system() == "Darwin" else "",
}
skip = set(sys.argv[sys.argv.index("--skip") + 1].split(",")) if "--skip" in sys.argv else set()
target = Path.home() / ".claude" / "skills"
for src in sorted((REPO / "skills").iterdir()):
    if not src.is_dir() or src.name in skip:
        continue
    dst = target / src.name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    for f in dst.rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        for k, v in subs.items():
            text = text.replace(k, v)
        f.write_text(text, encoding="utf-8")
    print("installed skill:", src.name)
