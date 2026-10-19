---
name: video-edit
description: Edit any video in Adobe Premiere Pro with Claude, in any language (Hebrew, English, …) — gameplay, vlogs, talking-head, podcasts, news/update shorts, reels. Analyze recordings (transcript, laughs/screams, highlights), plan the story, build an editable Premiere sequence (cuts, J/L cuts, zooms, speed-ups, layouts, transitions incl. Film Impact, captions, Remotion graphics, music with drops/crossfades, sound effects), render and self-review. Use whenever the user wants to edit, cut, build a sequence, make a short/reel, add captions/music/SFX, or fix an edit in Premiere.
---

# AI video editing in Premiere

Tooling: `{{MCE_HOME}}` (Python CLI `uv run python -m mce.<tool>`, graphics in `remotion/`).
Prefix shell commands with `{{PATH_PREFIX}}` (ffmpeg; the Bash tool doesn't load the login profile).

**Language:** talk to the user in the language they write in. The video's language (captions, on-screen text,
markers, reports) follows what is spoken in it — the tools detect it (`mce.i18n`, transcript language) or use
`language` in `~/.mce/config.json` ("he" | "en" | "auto"). Graphics pick text direction from the text itself
(Hebrew → RTL, English → LTR); components with built-in words take `lang: "en" | "he"`.

**Format profiles:** most edits are `general`. Format-specific skills add their own signals and structure —
e.g. `minecraft-edit` (HUD health/menus/death, milestones, "Minecraft but…"). If the footage is a game or a
format with its own skill, load that skill too.

Read `{{MCE_HOME}}/style.md` first, every time — its learned-preferences section overrides everything.

## 1. Analyze footage

```bash
cd {{MCE_HOME}} && uv run python -m mce.cli analyze "<video>" [--mic 0 --game 1] [--layout auto] [--language auto] [--profile general]
```
- ~5–15 min per recorded hour; run long files in the background.
- Streams: 0 = mic/voice, 1 = game/second source if present; ask if stream titles don't make it obvious.
- Output `<video>_analysis/`: `timeline.md` (ranked moments + 10-s rows with flags 🔥voice 😂laugh 😱scream 💣boom 💤idle ⭐clip),
  `transcript.md/json` (word timestamps), `timeline.json`, `sheets/` (overview every 20 s + 9 frames around each top moment).
  More frames: `uv run python -m mce.cli moment <analysis-dir> <seconds>...`.
- Signals: classified sound events (`mce.events`: laugh, scream, gasp, explosion) are the strongest "something happened"
  evidence — you cannot hear, a laugh is how you know it was funny. Loudness spikes alone are weak.
- Transcription: Hebrew → ivrit.ai model; other languages → Whisper large-v3-turbo; `auto` detects. Add names/terms
  the speaker uses to `vocab.txt` (one per line) to bias spelling.

## 2. Understand → paper edit → approval

1. Read `timeline.md` fully, then `transcript.md`; skim overview sheets to map the structure; look at moment sheets
   for every highlight you might keep.
2. Write `<analysis-dir>/paper_edit.md` (user's language): title options, the hook (first ~3–15 s) with exact
   ranges, sections/chapters with kept ranges `[mm:ss–mm:ss]` + one-line reason, what was cut and why (grouped),
   estimated length, markers you'll leave, shorts candidates.
3. **Don't build before the user approves** (unless they said to go straight through).

## 3. Build the sequence

Two builders, both produce FCP7 XML that Premiere imports as an editable sequence:
- **Single long recording** (gameplay, podcast, talking head): `edit_plan.json` → `uv run python -m mce.cli export <plan>`
  (`mce/fcpxml.py`: segments in order, speed-ups, facecam layout, mic/game tracks, markers, J/L cuts).
  Snap cut points to word boundaries (start ~0.08 s before the first word, end ~0.15 s after the last).
- **Multi-source / shorts / montage**: a spec for `mce/timeline_xml.py` (files, video tracks, audio tracks, markers;
  stills; any frame size; per-file frame rates). Clip fields: `scale`, `x`/`y` (sequence px), `keys` for animated
  zoom/move (`[{"t", "scale", "x", "y"}]`, t = seconds from clip start), `speed`, `gain_db`, `gain_keys`.
- 16:9 into 9:16: fill = scale 177.78. Text-heavy or important-detail shots: smaller copy (~78%) on V2 over a
  blurred fill of the same clip on V1 — never black bars.
- Markers: types fix, broll, fx, graphic, highlight, chapter, music, note — notes must be actionable.

**One-shot pipeline** (preferred): put finishing intents on the spec, then
`uv run python -m mce.push <spec.json> --export <out.mp4>` — imports, applies effects/transitions, deletes the old
version, saves, renders, runs QA. Spec extras: clip `"effects": [{"name", "props"}]`, clip `"pop": start|end|both`
(Film Impact Pop Motion), top `"transitions": [{"name", "track", "t", "dur"}]`, `"replaces"`, `"vo_lufs": -14`,
`"music_fit"`, `"music_playlist"`, `"duck_music"`, `"auto_sfx"`.

## 3b. Talking-head → vertical short (`mce.talkshort`)

For a person talking to camera (often many retakes of the same lines): you pick the best take of each line
from `transcript.md` (the last clean, complete take is usually the keeper; skip takes where the speaker looks
down/reads — check frames), list them as `takes` in a config, and `uv run python -m mce.talkshort <config.json>`
does the handwork: cuts pauses (word gaps **and** measured silences — ASR stretches words over pauses) and
fillers, pre-masters the voice to a WAV (mic stream of multi-stream recordings), frames the face (`mce.faces`,
cached) and changes punch-in level at every cut and every ~1.8 s inside long sentences (picture only, audio
continuous), crossfades audio on alternating tracks, and writes `caps_props.json` for Remotion `Captions`.
- `"layout": "split"` = stream-clip look (game/B-roll top half, face bottom, captions on the seam, `look: "stream"`,
  font `carlito`). Shots without B-roll fall back to full-frame face. B-roll `"at"` takes a shot id from the printed
  shot list (`"06a"`, `"06a+0.9"`); clips fill their shot and slow down (≥0.7×) if short; `zoom` hides letterboxing
  (find bars with `cropdetect`), panels are cropped at the seam.
- Pick B-roll by what is said (money → cash shots, "robbing a store" → robbery…). Find shot boundaries with
  `select='gt(scene,0.3)'` so in/out never crosses a cut. Official trailers via `yt-dlp` (H.264) → CFR 60.
- Order: config → talkshort → render captions (new filename each time) → talkshort again (picks up the .mov) → push.

## 4. Voiceover-driven shorts (script + recorded VO)

1. Read the sequence the user cut: VO clips' in/out = final timing (`tl = src - inPoint + start`).
2. Time captions/cuts by **forced alignment of the script** (`mce.align.align_script(wav, [(in, out, text)], lang)`),
   not ASR timestamps — ASR mishears words and once shifted a section by 0.7 s. Spell numbers out the way they're
   spoken ("twenty twenty seven" / "אלפיים עשרים ושבע"); unplaceable words are interpolated.
3. B-roll: `yt-dlp` (prefer H.264; convert VFR/30 fps to CFR before use; verify in/out against real frames).
4. Show what's said: when the VO names a thing, show it (image/PNG pop, the real thumbnail on a YouTube card, etc.).

## 5. Finishing toolbox

- **Film Impact** (if installed) appears in the transition catalog: "Pop Motion", "Pull Motion", "Spin Motion",
  "Fold Motion", "Glitch", "Flash", "Whip", "Zoom Blur"… `add_transition_to_clip` (edge, ~0.25 s) pops overlays
  in/out; `add_transition` (track + cut second) for cuts. Avoid Pull Motion between two full-frame fills (shows a flat
  panel edge). "Gaussian Blur" via apply_effect may resolve to Impact Blur (param "Amount").
- **Captions / graphics**: Remotion (`remotion/`): `Captions` (word groups, pop in/out, keyword colours, one line,
  auto-shrink, direction from text), `CTA`, `BigText`, `Morph` (A turns into B), `Sticker`, `Alarm`, `YouTubeCard`,
  `Advancement`, `RouteMap`… Render with alpha:
  `npx remotion render <Comp> out.mov --props='<json>' --image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444`.
  Give re-renders NEW filenames (Premiere caches by path). Premiere SRT captions: avoid (small, RTL number bugs).
- **J/L cuts** (see section 7). **Music** and **SFX** (sections 8 and the `sfx` skill).
- Position keyframes must go through XML `keys` (MCP `add_keyframe` takes numbers only). Crop keyframes don't render
  on export — reposition instead.

## 5b. Pro tips we follow (learned from editors' tutorials)

- **Jump cuts inside one take** (a chunk was cut out of a continuous talking clip): never leave the visible jump —
  (1) put the audio of the two sides on alternating tracks overlapping ~0.1 s each way with short fades, so the
  jump isn't heard, and (2) cover the cut with a B-roll shot from ~0.5 s before to ~1 s after, so it isn't seen.
  In fcpxml plans: `"jump_cover": {"broll": [paths], "overlap": 0.12, "pre": 0.5, "post": 1.0}` does both
  (without B-roll files it drops a 🟡 B-ROLL marker on each jump). In multi-source specs, do it by hand.
  "Small details like this separate a noob from a professional."
- **Never ship a render QA calls silent** (−70 LUFS): a Hard Limiter whose amplitude didn't verify once muted a whole
  short; push now removes unverified limiters. Prefer pre-mastered voice (talkshort does it) over `limit_db`.
- **Don't trust your ears for loudness** (laptop speakers lie; phones are where it's watched): measure.
  Target −14 LUFS integrated for YouTube, peaks under −2 dB. In Premiere that's a **Loudness Meter** (YouTube
  preset) and a **Hard Limiter** (Maximum Amplitude −2 dB) on the Mix track. The API can't add Mix-track effects,
  so: spec `"limit_db": -2` puts a Hard Limiter on every audio clip, `"vo_lufs"` sets the voice level, and QA
  measures the render (integrated LUFS + true peak, tells you how much to change vo_lufs). Suggest the user also
  keeps Loudness Meter + Hard Limiter on the Mix track of their sequence template.
- **Sound effects** follow what happens on screen (see the `sfx` skill): whoosh for movement transitions, mouse
  click / camera shutter for quick cuts, pop/beep for things appearing, sparkle for emphasis, ASMR typing as text types on.

## 6. Review loop (every time, before the user sees anything)

`mce.push --export` runs QA (black frames, frozen picture, −14 LUFS / −1 dBTP, dead air, V1 gaps, flash-short clips,
overlapping graphics) and writes contact sheets every 0.25 s to `<spec dir>/review/<render>/`. **Read every sheet
and the QA list, fix, re-push — then deliver**, saying what you checked. `export_sequence_review_frames` renders
black video — don't trust it; screen captures are unreliable while the user works.

Feedback: the user drops markers with comments on the timeline → `uv run python -m mce.notes <spec.json>` lists each
note with the clips/transitions/sounds under it. Act, re-push, and write lasting preferences to style.md.

## 7. J-cuts and L-cuts

- **J-cut** (sound first): next shot's audio starts under the current picture — pull the viewer forward (hear the
  explosion / "look at this" before seeing it; start a sentence a breath early; enter a scene softly).
- **L-cut** (sound lingers): current audio runs over the next picture — let a laugh/scream/impact finish; keep
  talking over B-roll or the result; smooth a jump cut.
- Lengths: 0.1–0.3 s inside speech; 0.3–0.8 s for reactions/tails; 1–2 s only for scene/chapter changes.
- Don't: on the punchline (the hard cut is the joke), when words would overlap, around sped-up segments.
- How: segment `"j": 0.3` / `"l": 0.5` in fcpxml plans; first pass `uv run python -m mce.jl <plan> <timeline.json>`.
  In multi-source specs, offset the audio clip's start/in from its video clip's.

## 8. Music

- `uv run python -m mce.music analyze <song> --plot x.png` — real start (skips silence), where it gets going,
  tempo, bars, sections (intro/build/drop/main/break/outro), drops. Look at the plot.
- `"music_fit": {"hit": T, "end": "fade"|"natural"}` — start on a bar line so a drop lands exactly on T (e.g. the
  hook's payoff); `natural` lands the song's own ending on the last frame. Never start at 0:00 of the file by default.
- `"music_playlist": {"songs": [{"file": "m1", "until": 30}, {"file": "m2"}]}` — songs on alternating tracks,
  constant-power crossfades; the next song's drop arrives as the old one is gone. Switch at section/mood changes.
- `"duck_music": true` lifts music in speech pauses; `"vo_lufs": -14` sets the voice loudness (the mix lands near
  YouTube's −14 LUFS; if QA says it's ~2.5 dB low with stereo VO, use −11.5).
- `mce.beats` + `beats.snap()` for beat-cut montages (never snap cuts sitting on a word).

## 9. Premiere bridge notes

- Calls beyond the loaded MCP tools: `{{MCE_HOME}}/bin/pp call <tool> '<json>'` (`bin/pp list <filter>`,
  `bin/pp schema <tool>`); on Windows `uv run python -m mce.premiere call …`.
- HOST_RECOVERY_REQUIRED (after an uncertain or refused edit) is acknowledged automatically by `mce.premiere`;
  by hand: `inspect_operation_recovery {"backend":"cep"}`, check real state, `acknowledge_operation_recovery`.
- After deleting a sequence Premiere may switch timelines — confirm the active sequence before exporting (push does).
- Gain is capped at +15 dB in Premiere; very quiet sources need pre-processing.
- Project layout: `{{EDITING_ROOT}}/<topic>/<project>/` with footage/ audio/ images/ graphics/ captions/ exports/ analysis/;
  copy shared assets in, don't move files other projects use.

## 10. Learn

Every correction ("cut later", "keep the laugh", "music too loud") → a dated line in style.md's learned-preferences
section, so the next edit already follows it.

## Sharing (repo upkeep)

Repo: github.com/AdirTV/ai-video-editor (local clone = {{MCE_HOME}}). After changing tools or skills:
`python3 setup/export_skills.py` (skills → `skills/` with paths as placeholders), check `git status` holds no
media/personal files, commit, push. Never hardcode paths in code — use `mce/config.py`.
