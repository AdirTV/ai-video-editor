"""Local fixes to the installed premiere-pro-mcp, re-applied after every (re)install. Idempotent.

- XML export with suppressUI: without it Premiere pops a "Translation Report" dialog on every pull
  (effects XML can't hold), and pull deletes the report anyway.

  uv run python setup/patch_mcp.py
"""
import shutil
import subprocess
from pathlib import Path

PATCHES = [  # (file in the package, original, patched)
    ("dist/tools/export.js",
     "seq.exportAsFinalCutProXML(outputFile.fsName);",
     'seq.exportAsFinalCutProXML(outputFile.fsName, 1); // 1 = suppressUI: no "Translation Report" dialog'),
]


def package_dir() -> Path | None:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    roots = [Path.home() / ".local" / "node" / "lib" / "node_modules"]
    if npm:
        try:
            roots.insert(0, Path(subprocess.run([npm, "root", "-g"], capture_output=True, text=True,
                                                timeout=30).stdout.strip()))
        except (OSError, subprocess.TimeoutExpired):
            pass
    return next((r / "premiere-pro-mcp" for r in roots if (r / "premiere-pro-mcp" / "package.json").exists()), None)


def patch() -> list[str]:
    """Applies what's missing; returns problems (empty = all patched)."""
    pkg = package_dir()
    if not pkg:
        return ["premiere-pro-mcp not installed globally"]
    problems = []
    for rel, old, new in PATCHES:
        p = pkg / rel
        text = p.read_text(encoding="utf-8") if p.exists() else ""
        if new in text:
            continue
        if text.count(old) != 1:
            problems.append(f"{rel}: code changed upstream, patch not applied")
            continue
        p.write_text(text.replace(old, new), encoding="utf-8")
    return problems


if __name__ == "__main__":
    probs = patch()
    print("\n".join(probs) or "premiere-pro-mcp patched (restart Claude Code to load it)")
