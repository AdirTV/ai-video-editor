# Installing this repo — instructions for Claude

You are Claude Code, and a user gave you this repo's link and asked you to install it. Follow these steps
in order. Talk to the user in their language (usually Hebrew). Explain briefly what each step does; don't
dump command output on them.

## 0. Before you start
- This needs **Claude Code with shell access** (the desktop app's Code tab or the `claude` CLI). If you are
  a chat-only Claude without a terminal, tell the user to open Claude Code and paste the link there.
- Ask the user two questions: **where do they keep their editing projects?** (default: `~/Desktop/editing`
  on Mac, `%USERPROFILE%\Desktop\editing` on Windows), and **which language their videos are in** —
  Hebrew (`he`), English (`en`) or mixed/other (`auto`, detected per video). Also ask whether they make
  **Minecraft** videos — if not, add `--no-minecraft` (Mac) / `-NoMinecraft` (Windows) so only the general
  editor is installed. If **Adobe Media Encoder** is installed (Mac: `ls -d "/Applications/Adobe Media Encoder"*`,
  Windows: `Test-Path "$env:ProgramFiles\Adobe\Adobe Media Encoder*"`), ask whether exports should render
  there — Premiere stays free during a render and an export crash can't take it (and unsaved work) down;
  recommended — and pass `--export-via ame` or `--export-via premiere` (Windows: `-ExportVia ame|premiere`).
  Without it the default is `auto` (Media Encoder when installed). Optionally ask for their **channel name** (and brand colours / logo if they have
  them) for step 3b. Everything else has defaults.
- Detect the OS (`uname` / `$env:OS`).

## 1. Get the code
Clone to a permanent place (not Downloads):
- Mac: `git clone https://github.com/AdirTV/ai-video-editor.git ~/ai-video-editor`
- Windows: `git clone https://github.com/AdirTV/ai-video-editor.git "$HOME\ai-video-editor"`
  (if `git` is missing: `winget install --id Git.Git -e`, then open a new shell)

The repo is public, so no GitHub account is needed. If git can't be installed, download the ZIP from the repo
page and extract it to the same place (its first update turns it into a git checkout).

## 2. Run the installer (non-interactive)
- **Mac**: `bash ~/ai-video-editor/setup/install-mac.sh --yes --editing-root "<folder>" --language <he|en|auto>`
  - **Exit code 10** = Homebrew is missing. Its installer needs the user's password, which you must not
    handle. Ask the user to paste this into their own Terminal app, wait for it to finish, then re-run step 2:
    `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`
- **Windows**: `powershell -ExecutionPolicy Bypass -File "$HOME\ai-video-editor\setup\install-windows.ps1" -Yes -EditingRoot "<folder>" -Language <he|en|auto>`
  - winget may show permission (UAC) pop-ups — tell the user to click **Yes** on them.

If a step fails, fix what the error says and run the same command again — the installer is safe to re-run
and keeps existing settings (`~/.mce/config.json`).

The installer is long (several minutes, downloads ~2 GB of Python/Node packages). Run it in the
background or with a long timeout and report progress per step (it prints `== n/8 ...`).
It installs: ffmpeg, Node, uv, yt-dlp, the Premiere bridge (premiere-pro-mcp) and its panel, the Python
and Remotion dependencies, the skills (`video-edit`, `sfx`, Remotion's, and `minecraft-edit` unless `--no-minecraft`), and registers the
`premiere` MCP server with Claude Code.

## 3. Verify
`cd <repo> && uv run python setup/doctor.py` — every required line must be ✅. For each ❌ it prints the
fix; apply it and run doctor again. The "Premiere is open" line is expected to be ⚠️ until step 4.

## 3b. Brand (optional)
The installer creates `brand.json` in the repo (from `brand.example.json`). Put the user's channel name in
`channel`; if they gave colours, set `accent` (CTA, big text, highlights) and `accent2` (stickers). A logo goes
in `remotion/public/brand/` with `"logo": "brand/<file>"`. The graphics use these whenever a prop isn't passed.

## 4. Hand-off to the user (they must do these themselves)
1. **Restart Claude Code** (new skills and the new MCP server load only in a new session).
2. **Restart Premiere Pro**, then **Window → Extensions → MCP for Adobe Premiere Pro** → make sure it
   says the connector is running (press Start if needed).
3. Optional: put sound effects into `<editing folder>/SFX/<kind>/` (whoosh, pop, beep, click, shutter,
   typing, riser, impact, ding, magic, glitch, minecraft) and ask Claude to "index the SFX library".

Then tell them how to use it, in their language, e.g. open Claude Code in a project folder and say:
"edit this recording into an 8-minute video", "make a short from this voiceover with this clip behind it",
"add sound effects", "read my notes" (after leaving markers with comments on the Premiere timeline).
It works for any kind of video (gaming, vlogs, talking head, podcasts, shorts) in Hebrew or English.

## Updating later
`cd <repo> && uv run python setup/update.py` — pulls the latest version and re-applies only what changed
(Python/Remotion packages, the Premiere bridge and panel, the skills). Users can also double-click
`update-mac.command` / `update-windows.bat`. A ZIP install becomes a git checkout on its first update.
Personal files (`style.md`, `vocab.txt`, `brand.json`, `remotion/src/projects/`) are never touched.
