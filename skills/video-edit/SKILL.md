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
- `--separate`: voice and game/music are mixed in **one** audio stream (phone/camera clips, single-track OBS,
  someone else's video, a podcast with a music bed) → Demucs splits them first; transcript, laughs/screams and
  speech run on the clean voice, game-sound events on the rest. Stems land in `<analysis>/audio/stems/`
  (`timeline.json` → `stems`) — use `vocals.wav` as a clean dialogue track in the edit. Not needed when mic and game
  are already separate streams.
- `--speakers auto|N` (podcasts, interviews, 2+ people): labels who speaks — `transcript.md` lines get `S1:`/`S2:`,
  `transcript.json` segments/words get `speaker`. Needs `hf_token` in `~/.mce/config.json` (free Hugging Face
  account that accepted the pyannote/speaker-diarization-community-1 terms); without it the tool says so and stops.

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
  `mce.scenes` (section 5c) so in/out never crosses a cut. Official trailers via `yt-dlp` (H.264) → CFR 60.
- Talking-head shorts (see style.md): split 40/60 (`split_ratio`), top = a *literal* picture of what is said;
  captions **white, one line, same size** (`look: "stream"`): **on the seam while the screen is split, lower third
  (`top` ≈1460) otherwise** — never moving mid-phrase. the user rejected 2-line karaoke. Keep headroom tight (`full_target_y` ≈620, `low_face_y` ≈0.30).
  Add music (never Epidemic/Artlist — skip `ES_` files) and SFX (talkshort auto-whooshes b-roll entries; add
  content hits in `"sfx"`).
- Always set `"project"` in the config — several Premiere projects may be open (other sessions); push opens and
  verifies it before importing.
- Hide anything unwanted in the picture (mic lowered, looking away, a flub) with a B-roll `"full": true` cutaway —
  audio keeps running. End on the last content line, not a filler question.
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

## 5a. Face-lock (camera locked to a face)

The frame follows the speaker's face so it stays fixed in the frame while the body/background moves — the
"camera locked to someone's face" reel look (in Premiere by hand: Object Mask on the face → Mask to Motion →
Convert to Motion → Stabilize). Ours: `mce.faces.dense()` tracks the face every 0.1 s (stricter detector, anchored
to the speaker, occluded/odd-size boxes dropped, smoothed) → position keyframes per shot.
- **When it's needed:** the face moves inside a shot — leaning in/out or sideways, turning, walking, handheld
  phone footage, a close punch-in where the face drifts toward the edge, a reaction where they jump back. Also as a
  deliberate style beat (hold the face dead-centre while the world moves).
- **When not:** a still speaker (static framing reads calmer; locking adds micro-wobble), the face is mostly
  covered (hands, looking down — the tracker can't see it), or the shot wants the movement (they walk out of frame).
- talkshort: `"face_lock": "auto"` (default) locks only shots whose face moves ≥ `lock_threshold` (0.25 face
  widths) and was found in ≥60% of samples; prints `face-lock: 07b (0.38)`. `true` forces it, `false` disables.
  `lock_scale` (default off) also holds the face size — only for real in/out moves; occlusion fakes size changes.
- Multi-source specs: build the same keys by hand from `dense()` (`frame_face` per sample).

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

## 5c. Extra tools (stems, shots, cutouts, Lottie)

All `cd {{MCE_HOME}} && uv run python -m mce.<tool> …`; each prints its usage with `-h`.

- **Stems — `mce.stems <media> [--stream N] [--start S --end E] [--stems voice|all]`** (Demucs, ~8× real time):
  `vocals.wav` + `no_vocals.wav` (or vocals/drums/bass/other), same timing as the source so they sit 1:1 under it.
  Uses: kill a trailer's music and keep its dialogue/SFX (Content ID; put our own music under it); remove the
  narrator from B-roll; a clean dialogue track when the voice is buried in game noise; lift the voice and duck the game
  separately; an a-cappella/instrumental of a song for a beat drop. Listen to the stems (or QA-measure) — artefacts
  show on heavy distortion.
- **Shots — `mce.scenes <video> [--start S --end E] [--detector adaptive|content|fade] [--json out.json]`**
  (PySceneDetect, ~15-30× real time): shot list with exact cut times. Use for B-roll in/out from trailers and news
  footage (never cross a cut), splitting a montage or VOD into shots, finding someone else's jump cuts.
  `adaptive` (default) ignores steady camera motion — right for games and handheld; `content` catches more (fast
  whip-pans too); `fade` finds fades to black. Shots shorter than `--min-len` (0.5 s) merge into neighbours.
- **Subject cutout — `mce.matte <video> --start S --end E [--point x,y] [--neg x,y] [--box x0,y0,x1,y1]`**
  (SAM 2 video, ~3 frames/s on Apple Silicon → keep it to the seconds you need): ProRes 4444 with alpha of the
  subject alone, at the source size/fps, starting at `--start`. No prompt = the main person (biggest, most central);
  for a game character/object give a point or box in source pixels (look at a frame first). `--mask` writes a
  black/white matte instead (Premiere Track Matte Key).
  - **Text behind the subject**: V1 the shot · V2 the text (Remotion `BigText`/`Sticker`, alpha .mov) · V3 the
    cutout — same timeline start as the V1 piece with in = (V1 in − S), and the **same** scale/x/y/keys as V1 so it
    lines up. The words look like they're behind the person. Big, bold words, 1–3 per beat; works best when the
    subject is in the lower/middle of frame and the text sits behind the head/shoulders.
  - Also: background blur/darken/replace behind a talking head (V1 effected copy, V2 cutout), a glow/outline on the
    subject, the subject breaking out of a frame/card.
  - Check the cutout on a coloured background before using it (edges, lost hands/hair, a second person grabbed);
    add `--point`/`--neg` and rerun if wrong.
- **Lottie animations — Remotion `LottieFx`**: ready-made animated stickers/icons with alpha.
  `npx remotion render LottieFx out.mov --props='{"emoji":"😂","size":420,"x":540,"y":700,"seconds":2}' …(alpha flags)`.
  `emoji` = any Noto animated emoji (no download; 😂🔥💀😱🤯👀💯🎉❤️…); `src` = a LottieFiles animation fetched with
  `uv run python -m mce.lottie <url.json|url.lottie> <name>` → `"src": "lottie/<name>.json"` (`--list` shows the
  library). Props: `size`, `x`/`y` (centre px), `loop`, `speed`, `pop` (pop in/out, default on), `rotate`.
  Use for reactions next to a face, arrows/circles pointing at something, subscribe/like animations, icons
  (money, alarm, check/cross) — small and short (1–2 s), timed to the word, with a matching SFX.

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
