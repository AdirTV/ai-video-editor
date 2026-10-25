"""Update the AI editor to the latest version from GitHub, and apply whatever the new version needs.

  uv run python setup/update.py           pull + reinstall only what changed (deps, panel, skills)
  uv run python setup/update.py --check   just say whether an update is waiting (and what's in it)

Double-click: update-mac.command (Mac) / update-windows.bat (Windows).
Your personal files (style.md, vocab.txt, brand.json, remotion/src/projects/, media) are never touched.
A ZIP install (no git) is turned into a git checkout on the first update, so later updates are one step.
"""
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
URL = "https://github.com/AdirTV/ai-video-editor.git"
BRANCH = "main"
WIN = platform.system() == "Windows"
HOME = Path.home()
sys.stdout.reconfigure(line_buffering=True)  # keep our lines in order with the subprocesses


def run(*cmd: str, cwd: Path = REPO, check: bool = True, quiet: bool = False) -> str:
    exe = shutil.which(cmd[0]) or cmd[0]  # npm is npm.cmd on Windows
    r = subprocess.run([exe, *cmd[1:]], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode:
        sys.exit(f"❌ {' '.join(cmd)} failed:\n{r.stderr.strip() or r.stdout.strip()}")
    if not quiet and r.stdout.strip():
        print(r.stdout.strip())
    return r.stdout.strip()


def git(*args: str, **kw) -> str:
    return run("git", *args, quiet=True, **kw)


def step(t: str) -> None:
    print(f"\n== {t}")


def mcp_version(rev: str | None = None) -> str:
    """premiere-pro-mcp version pinned in mce/config.py (older versions pinned it in setup/install-mac.sh)."""
    for path, pat in (("mce/config.py", r'PREMIERE_MCP_VERSION = "([\d.]+)"'), ("setup/install-mac.sh", r"premiere-pro-mcp@([\d.]+)")):
        text = git("show", f"{rev}:{path}", check=False) if rev else (REPO / path).read_text(encoding="utf-8")
        if m := re.search(pat, text):
            return m.group(1)
    return ""


def fetch() -> bool:
    try:
        r = subprocess.run(["git", "fetch", "-q", "origin", BRANCH], cwd=REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
    except subprocess.TimeoutExpired:
        print("⚠️  Couldn't reach GitHub (timed out) — skipping the update for now.")
        return False
    if r.returncode:
        print("⚠️  Couldn't reach GitHub:", (r.stderr.strip().splitlines() or ["?"])[-1])
        print("   (offline, or the network blocks GitHub — try again later)")
    return r.returncode == 0


# The last version whose packages/panel/skills were applied on this computer. Kept inside .git so it's
# never committed. If an update stops halfway (say npm failed), the next run re-applies from here.
APPLIED = REPO / ".git" / "mce-applied"


if not shutil.which("git"):
    sys.exit("❌ git is missing. Windows: winget install --id Git.Git -e | Mac: xcode-select --install — then run this again.")

if "--check" in sys.argv and not (REPO / ".git").exists():
    print("ℹ️  This is a ZIP install, so it can't tell whether an update is waiting.")
    print("Run: uv run python setup/update.py  (turns it into a git checkout once, then updates)")
    sys.exit(0)

if not (REPO / ".git").exists():
    # ZIP install: make it a checkout of the repo. Tracked files are replaced by the latest version;
    # personal and ignored files stay as they are.
    step("Turning this ZIP install into a git checkout (one time)")
    git("init", "-q")
    git("remote", "add", "origin", URL)
    if not fetch():
        sys.exit(1)
    git("reset", "-q", "--hard", f"origin/{BRANCH}")
    git("branch", "-q", "-M", BRANCH)
    git("branch", "-q", "--set-upstream-to", f"origin/{BRANCH}")
    old = None
else:
    if not fetch():
        sys.exit(1)
    old = git("rev-parse", "HEAD")

behind = int(git("rev-list", "--count", f"HEAD..origin/{BRANCH}") or 0) if old else 0
if "--check" in sys.argv:
    if behind:
        print(f"⬆️  {behind} update(s) waiting:")
        print(git("log", "--format=  • %s", f"HEAD..origin/{BRANCH}"))
        print("Run: uv run python setup/update.py")
    elif APPLIED.exists() and APPLIED.read_text(encoding="utf-8").strip() != old:
        print("⚠️  The last update didn't finish installing. Run: uv run python setup/update.py")
    else:
        print("✅ Up to date.")
    sys.exit(0)

if old:
    changed_files = git("status", "--porcelain", "--untracked-files=no").splitlines()
    if changed_files:
        print("❌ These repo files were changed on this computer, so the update would overwrite them:")
        print("\n".join("   " + c for c in changed_files))
        print("Your own settings belong in style.md, vocab.txt, brand.json and remotion/src/projects/ (never overwritten).")
        print("To throw the local changes away and update: git checkout -- . && uv run python setup/update.py")
        sys.exit(1)
    if not behind:
        unfinished = APPLIED.exists() and APPLIED.read_text(encoding="utf-8").strip() != old
        if unfinished:
            print("Finishing the last update (it stopped before everything was installed).")
        else:
            print("✅ Already up to date.")
            if "--force" not in sys.argv:
                sys.exit(0)
    else:
        step(f"Getting {behind} update(s)")
        print(git("log", "--format=  • %s", f"HEAD..origin/{BRANCH}"))
        git("merge", "-q", "--ff-only", f"origin/{BRANCH}")

new = git("rev-parse", "HEAD")
# diff from what was last *applied* (not just checked out), so a half-finished update is completed
base = (APPLIED.read_text(encoding="utf-8").strip() if APPLIED.exists() else old) if old else None
if base and subprocess.run(["git", "cat-file", "-e", f"{base}^{{commit}}"], cwd=REPO, capture_output=True).returncode:
    base = None  # unknown commit (history rewritten): re-apply everything
changed = set(git("diff", "--name-only", base, new).splitlines()) if base and "--force" not in sys.argv else None
touched = lambda *prefixes: changed is None or any(f.startswith(prefixes) for f in changed)  # noqa: E731
old_mcp = mcp_version(base) if base else ""

if touched("pyproject.toml", "uv.lock"):
    step("Python packages")
    run("uv", "sync", quiet=True)
if touched("remotion/package.json", "remotion/package-lock.json"):
    step("Remotion packages")
    run("npm", "install", "--loglevel=error", cwd=REPO / "remotion", quiet=True)

cep = (Path.home() / "AppData" / "Roaming" if WIN else HOME / "Library" / "Application Support") / "Adobe" / "CEP" / "extensions" / "MCPBridgeCEP"
restart_premiere = False
if mcp_version() and mcp_version() != old_mcp:
    step(f"Premiere bridge {old_mcp or '?'} → {mcp_version()}")
    run("npm", "install", "-g", "--loglevel=error", f"premiere-pro-mcp@{mcp_version()}", quiet=True)
    run("premiere-pro-mcp", "--install-cep")
    restart_premiere = True
sys.path.insert(0, str(REPO / "setup"))
from patch_mcp import patch  # noqa: E402  (a reinstall drops the local fixes: re-apply every update)
for problem in patch():
    print("⚠️", problem)
if (restart_premiere or touched("panel/")) and cep.exists():
    step("Premiere panel design")
    for f in ("index.html", "styles.css"):
        shutil.copy2(REPO / "panel" / f, cep / f)
    restart_premiere = True

step("Skills")
run(sys.executable, str(REPO / "setup" / "install_skills.py"))

for personal, template in (("brand.json", "brand.example.json"),):
    if not (REPO / personal).exists() and (REPO / template).exists():
        shutil.copy2(REPO / template, REPO / personal)
        print(f"created {personal} from {template} (your channel name, colours, logo)")

step("Health check")
subprocess.run([sys.executable, str(REPO / "setup" / "doctor.py")], cwd=REPO)

APPLIED.write_text(new, encoding="utf-8")
print("\n✅ Updated.")
print("→ Restart Claude Code so it loads the new skills.")
if restart_premiere:
    print("→ Restart Premiere (the panel changed).")
