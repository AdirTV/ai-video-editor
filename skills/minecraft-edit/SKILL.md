---
name: minecraft-edit
description: Minecraft-specific layer for editing Minecraft gameplay and Minecraft news/update videos (any language) — HUD detection (health, menus, death screen), progression milestones, the "Minecraft but…" format, Minecraft sounds and graphics. Use together with the video-edit skill whenever the footage or topic is Minecraft.
---

# Minecraft editing (format layer)

Load and follow the **`video-edit`** skill for the whole workflow (analyze → paper edit → build → finish → review).
This skill only adds what's specific to Minecraft.

## Analysis profile

Run analysis with `--profile minecraft` (or set `"profile": "minecraft"` in `~/.mce/config.json`):
```bash
cd {{MCE_HOME}} && uv run python -m mce.cli analyze "<video>" --profile minecraft [--mic 0 --game 1]
```
Adds HUD signals read from pixels: health per sample (💔 drops, low-health clutch), inventory/crafting panels
(📦 → usually cut), death screen (☠️). They're heuristics calibrated on assumptions — confirm on the sheets before
building the story on them. Also primes transcription with Minecraft vocabulary (Hebrew/English).

## "Minecraft but…" structure

Survival with one gimmick until the Ender Dragon. Milestones: wood → stone tools → iron → diamonds → Nether →
blaze rods → ender pearls → stronghold → End → dragon. The story is **how the gimmick changes each milestone**,
not a list of achievements.
- Hook (0–15 s): the gimmick in one line + a promise/question + 1–3 s flash of the craziest moment.
- Chapters by milestone; keep only moments where the gimmick matters, danger, laughs or clear progress.
- Escalation chapter to chapter; open loops before chapter changes ("but I didn't know what waited in the Nether…").
- Climax = dragon fight, least compressed. Ending + CTA to the next episode.
- Compression: ~1 recorded hour → ~8 min (≈13%), the script decides.
- Speed up (×4–×8) travel/mining/building/crafting instead of cutting when it's part of the story; time-lapse
  builds; cut menus and dead time.
- Layout: 3840×1080 recordings with facecam on one half → gameplay full frame on V1, facecam scaled into a corner on
  V2 with drop shadow (`mce/fcpxml.py` layout facecam_left/right).

## Minecraft assets

- Sounds: the SFX library's Minecraft folders (every mob/block/UI sound, level up…) — `sfx` skill, `mce.sfx search <mob> <action>`.
  Use the real game sound when a mob/item appears on screen.
- Images: renders from minecraft.wiki (e.g. mobs, items) as PNG pops.
- Graphics (Remotion): `Advancement` (real Minecraft advancement toast; `lang: "en"` → "Advancement Made!"),
  `YouDied`, `Frost`, `LightMeter`, `RouteMap`, `Morph` (one mob turns into another).
- Official footage for news/update videos: Minecraft's YouTube channel (yt-dlp, H.264), Mojang's articles.
  Trailer music can trigger Content ID — use your own music under trailer footage. `mce.stems` strips the music
  and keeps the trailer's game sounds/dialogue (`no_vocals` = music+SFX, so for "SFX without music" use
  `--stems all` and keep `other` + `drums` only where they're game sounds — listen first).
- Shot lists of trailers / Minecraft Live segments: `mce.scenes` (adaptive detector) — exact cuts even though the
  camera is always moving; pick B-roll inside one shot.
- Own gameplay: `mce.scenes` on a continuous recording finds hard visual changes, not "shots" — death screen,
  portal/dimension change, teleport, loading/menu screens, alt-tab. Useful as extra markers; the mouse-look motion
  doesn't trigger it with `adaptive` (use `content` only on edited footage). For a 3840×1080 facecam recording the
  facecam half dilutes it — run it on the gameplay half if you need precision (crop first with ffmpeg).
- Single-track recordings (voice and game mixed): `analyze --separate`.
