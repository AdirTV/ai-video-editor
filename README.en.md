# AI video editor for Premiere (with Claude)

**[עברית](README.md)**

> **Easiest way:** open Claude Code, paste this repo's link and say *"install this for me"*.
> Claude reads [INSTALL_FOR_CLAUDE.md](INSTALL_FOR_CLAUDE.md) and installs everything — it only asks where your
> editing folder is and which language your videos are in.

A toolkit that lets Claude edit **any kind of video** in Adobe Premiere Pro — gaming, vlogs, talking head,
podcasts, shorts and reels — **in English or Hebrew**: analyze recordings, build sequences, add effects,
transitions, captions, graphics, music and sound effects, and render a check.

## What's inside
| | |
|---|---|
| **Premiere bridge** | [premiere-pro-mcp](https://github.com/leancoderkavy/premiere-pro-mcp) (open source, MIT) + a redesigned panel inside Premiere |
| **Editing tools** (`mce/`) | transcription in English/Hebrew/any language (auto-detected), recording analysis (laughs, screams, strongest moments), forced alignment of scripts, sequence builders, J/L cuts, automatic sound effects, music (smart starts/endings, drops on cue, crossfades between songs), loudness, quality checks, voice/music/game separation (Demucs), speaker labels, shot detection (PySceneDetect), subject cutouts for text-behind-subject (SAM 2) |
| **Graphics** (`remotion/`) | animated captions, CTAs, pop-up graphics, Lottie animations and animated emoji — built in Remotion and layered into Premiere with transparency; text direction follows the language |
| **Skills** (`skills/`) | what teaches Claude how to edit: `video-edit` (general), `minecraft-edit` (Minecraft layer), `sfx` (sound effects) |

## Requirements
- Mac (Apple Silicon) or Windows 10/11
- Adobe Premiere Pro 2024 or later
- A Claude subscription (Pro or Max) for Claude Code

## Install

### Let Claude do it
Open Claude Code (desktop app → Code tab, or `claude` in a terminal), paste
`https://github.com/AdirTV/ai-video-editor` and say "install this".

### By hand — Mac
```bash
git clone https://github.com/AdirTV/ai-video-editor.git ~/ai-video-editor
bash ~/ai-video-editor/setup/install-mac.sh --language en
```
It asks for your Mac password (to install Homebrew) and where your editing projects live.

### By hand — Windows
Download the ZIP from the green **Code** button, extract it somewhere permanent (e.g. `Documents\ai-video-editor`)
and double-click **`install-windows.bat`** — or in PowerShell:
```powershell
winget install --id Git.Git -e
git clone https://github.com/AdirTV/ai-video-editor.git $HOME\ai-video-editor
powershell -ExecutionPolicy Bypass -File $HOME\ai-video-editor\setup\install-windows.ps1 -Language en
```

### After installing (once)
1. The first time you run `claude`, sign in with your Claude account.
2. Restart Premiere.
3. In Premiere: **Window → Extensions → MCP for Adobe Premiere Pro** → check the connector is running (press Start if not).

## How to use it
1. Open your project in Premiere with the MCP panel open.
2. In a terminal in your project folder: `claude`
3. Just talk to it, e.g.:
   - "Edit this recording into an 8-minute video"
   - "Cut this podcast and pull 3 shorts out of it"
   - "Make a short from the voiceover I recorded, with this clip behind it"
   - "Add sound effects"
4. **Notes:** instead of explaining in chat, drop markers with comments on the Premiere timeline and say "read my notes".

## Not making Minecraft videos?
The editor is general. The Minecraft layer only activates for Minecraft footage, and you can leave it out
entirely at install: `--no-minecraft` (Mac) or `-NoMinecraft` (Windows). If Claude installs it, it will ask.

## Language
Chosen at install: English / Hebrew / auto (`language` in `~/.mce/config.json`). In auto mode the language is
detected per video: Hebrew is transcribed with ivrit.ai's model, English and other languages with Whisper
large-v3-turbo. Captions and graphics lay out left-to-right or right-to-left from the text itself.

## Sound effects
The library isn't in the repo (it's huge and everyone has their own). The installer creates an `SFX` folder in
your editing folder with `whoosh pop riser impact ding click magic glitch minecraft` subfolders. Drop sounds in
(or a whole pack into `SFX/`) and tell Claude "index the SFX library".

## Your style
`style.md` is created at install from `style.template.en.md` (or the Hebrew template). Claude records every
correction you make there, so it learns your taste from video to video. It's personal and never pushed to the repo.

## Health check
```bash
uv run python setup/doctor.py
```
Shows ✅/❌ for every part and how to fix it.

## Updating
```bash
cd ~/ai-video-editor && git pull && uv run python setup/install_skills.py
```

## Licenses
- premiere-pro-mcp — MIT, by leancoderkavy (installed from npm, not included here)
- Remotion — free for individuals and companies of up to 3 people; beyond that a license is required ([remotion.pro](https://remotion.pro))
- Hebrew transcription model — [ivrit.ai](https://huggingface.co/ivrit-ai); Whisper — OpenAI (MIT)
- Demucs (MIT), PySceneDetect (BSD-3), SAM 2 and RT-DETR (Apache-2.0), Noto animated emoji (CC BY 4.0); speaker labels — pyannote (needs a Hugging Face account that accepted the model terms)
- The videos, music and sounds you use are your responsibility (copyright, Content ID)

## Troubleshooting
- **"heartbeat is stale"** — the MCP panel in Premiere is closed or stuck: Window → Extensions → MCP for Adobe Premiere Pro.
- **After a premiere-pro-mcp update the panel looks old again** — `bash panel/install.sh` (Mac) or re-run the installer.
- **Windows** — the tools were developed on Mac; they should work on Windows, but if something breaks, send the error message.
