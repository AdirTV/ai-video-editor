---
name: video-edit
description: Edit any video in Adobe Premiere Pro with Claude, in any language (Hebrew, English, …) — gameplay, vlogs, talking-head, podcasts, news/update shorts, reels. Analyze recordings (transcript, laughs/screams, highlights), plan the story, build an editable Premiere sequence (cuts, J/L cuts, zooms, face-lock, speed-ups, layouts, transitions incl. Film Impact, captions, Remotion graphics, music with drops/crossfades, sound effects), render and self-review. Use whenever the user wants to edit, cut, build a sequence, make a short/reel, add captions/music/SFX, or fix an edit in Premiere (תערוך, עריכה, לחתוך, שורט, ריל, כתוביות, מוזיקה, פרמייר, סרטון).
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

**The creator's taste comes first.** Read `{{MCE_HOME}}/style.md` before every edit — it is this creator's own
style (formats, pacing, caption look, framing, music sources, everything they corrected before) and its
learned-preferences section overrides every default in this skill. `brand.json` (same folder) is the channel
name, colours, caption font/look and logo: the graphics fall back to it, so don't pass colours that just repeat
it. When the user states brand colours or a logo, write them there.

**Updates:** once per session, before the first edit, run `cd {{MCE_HOME}} && uv run python setup/update.py --check`
(it only reads, never changes anything). If updates are waiting, tell the user in a line what's new and offer to
run `uv run python setup/update.py` (then they restart Claude Code). Skip silently if it can't reach GitHub.

## What does this footage need? (check on every edit, without being asked)

While watching the sheets and reading the transcript, look for these situations and use the tool — then read
its reference file before using it the first time in a session:

| You notice… | Do | Read |
|---|---|---|
| A person talking to camera, several retakes of the same lines | `mce.retakes` → `mce.talkshort` | `talking-head.md` |
| The face moves inside a shot (leans in/out, walks, turns, handheld phone, a punch-in drifting to the edge, jumping back in a reaction) | **face-lock**: talkshort does it by itself (`face_lock: auto`); in other specs build the keys from `mce.faces.dense()` | `talking-head.md` |
| A chunk cut out of one continuous take (visible jump) | overlap the audio + cover with B-roll (`jump_cover`) | `sound.md` |
| The words name something the viewer should *see* | find B-roll yourself (`mce.broll`) | `tools.md` |
| Voice and game/music mixed in one stream | analyze with `--separate`; `mce.stems` for a clean track | `tools.md` |
| Noisy voice (hum, room, street, music under speech) or the user says it sounds bad | `mce.voice analyze` → `clean` at the lightest level that works | `tools.md` |
| A big word/title over a person, or the subject should pop out of the frame | text behind the subject (`mce.matte`) | `tools.md` |
| Someone else's footage/trailer with cuts | `mce.scenes` so B-roll in/out never crosses a cut | `tools.md` |
| A reaction, a pointer, a like/subscribe moment | Lottie sticker (`LottieFx`) + matching SFX | `tools.md` |
| A laugh/scream/impact that should finish, or a line that should start early | L-cut / J-cut | `sound.md` |
| Music in the edit | `mce.music` analyze → `music_fit` / `music_playlist` | `sound.md` |
| Things appear, move, change on screen | SFX (the `sfx` skill) | `sfx` skill |
| Animated graphics, slams, shakes, camera moves | Remotion catalog + motion recipes | `motion-recipes.md` |

Reference files are in `{{MCE_HOME}}/skills/video-edit/`. A row that applies is not optional polish: a
moving face left unlocked or a named thing left without a picture is a mistake the user will point out.

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
- `--separate`: voice and game/music in **one** audio stream (phone/camera clips, single-track OBS, someone else's
  video, a podcast with a music bed) → Demucs splits them first. Stems land in `<analysis>/audio/stems/`
  (`timeline.json` → `stems`) — use `vocals.wav` as a clean dialogue track. Not needed with separate streams.
- `--speakers auto|N` (podcasts, interviews, 2+ people): `transcript.md` lines get `S1:`/`S2:`, words get `speaker`.
  Needs `hf_token` in `~/.mce/config.json` (free Hugging Face account that accepted the
  pyannote/speaker-diarization-community-1 terms); without it the tool says so and stops.

## 2. Understand → paper edit → approval

1. Read `timeline.md` fully, then `transcript.md`; skim overview sheets to map the structure; look at moment sheets
   for every highlight you might keep. Go through the "What does this footage need?" table.
2. Write `<analysis-dir>/paper_edit.md` (user's language): title options, the hook (first ~3–15 s) with exact
   ranges, sections/chapters with kept ranges `[mm:ss–mm:ss]` + one-line reason, what was cut and why (grouped),
   estimated length, markers you'll leave, shorts candidates, and which tools from the table you'll use where.
3. **Don't build before the user approves** (unless they said to go straight through).

## 3. Build the sequence

Two builders, both produce FCP7 XML that Premiere imports as an editable sequence:
- **Single long recording** (gameplay, podcast, talking head): `edit_plan.json` → `uv run python -m mce.cli export <plan>`
  (`mce/fcpxml.py`: segments in order, speed-ups, facecam layout, mic/game tracks, markers, J/L cuts, `jump_cover`).
  Snap cut points to word boundaries (start ~0.08 s before the first word, end ~0.15 s after the last).
- **Multi-source / shorts / montage**: a spec for `mce/timeline_xml.py` (files, video tracks, audio tracks, markers;
  stills; any frame size; per-file frame rates — phone footage is snapped to its standard rate). Sequence `fps`
  may be 60, 59.94, 30, 29.97, 25… Clip fields: `scale`, `x`/`y` (sequence px), `keys` for animated zoom/move
  (`[{"t", "scale", "x", "y"}]`, t = seconds from clip start), `speed`, `gain_db`, `gain_keys`.
- **Talking-head vertical shorts**: `mce.talkshort` builds the spec for you — see `talking-head.md`.
- 16:9 into 9:16: fill = scale 177.78. Text-heavy or important-detail shots: smaller copy (~78%) on V2 over a
  blurred fill of the same clip on V1 — never black bars.
- Markers: types fix, broll, fx, graphic, highlight, chapter, music, note — notes must be actionable.

**One-shot pipeline** (preferred): put finishing intents on the spec, then
`uv run python -m mce.push <spec.json> --export <out.mp4>` — pulls the user's hand edits from the old version into
the spec (section 6), imports, applies effects/transitions, deletes the old version, saves, snapshots the new one,
renders, runs QA. Spec extras: clip `"effects": [{"name", "props"}]`, clip `"pop": start|end|both`
(Film Impact Pop Motion), top `"transitions": [{"name", "track", "t", "dur"}]`, `"replaces"`, `"vo_lufs": -14`,
`"music_fit"`, `"music_playlist"`, `"duck_music"`, `"auto_sfx"`, `"limit_db"`. Always set `"project"` when
several Premiere projects may be open — push opens and verifies it before importing.
The render goes to **Adobe Media Encoder** when it's installed (setting `export_via`: auto/ame/premiere) — a
crash or leak there can't take Premiere down; push waits for the finished file before QA, and falls back to
rendering inside Premiere if the hand-over fails. `--export-direct` forces the Premiere render. To render a
sequence without pushing: `uv run python -m mce.export <out.mp4> [--sequence NAME] [--qa]` — never the MCP
`export_sequence` tool directly (it always renders inside Premiere).

## 4. Voiceover-driven shorts (script + recorded VO)

1. Read the sequence the user cut: VO clips' in/out = final timing (`tl = src - inPoint + start`).
2. Time captions/cuts by **forced alignment of the script** (`mce.align.align_script(wav, [(in, out, text)], lang)`),
   not ASR timestamps — ASR mishears words and once shifted a section by 0.7 s. Spell numbers out the way they're
   spoken ("twenty twenty seven" / "אלפיים עשרים ושבע"); unplaceable words are interpolated.
3. B-roll (`tools.md`): show what's said — when the VO names a thing, show it (image/PNG pop, the real thumbnail
   on a YouTube card, etc.).

## 5. Finishing

- **Film Impact** (if installed) appears in the transition catalog: "Pop Motion", "Pull Motion", "Spin Motion",
  "Fold Motion", "Glitch", "Flash", "Whip", "Zoom Blur"… `add_transition_to_clip` (edge, ~0.25 s) pops overlays
  in/out; `add_transition` (track + cut second) for cuts. Avoid Pull Motion between two full-frame fills (shows a flat
  panel edge). "Gaussian Blur" via apply_effect may resolve to Impact Blur (param "Amount").
- **Captions / graphics**: Remotion (`remotion/`). **`remotion/CATALOG.md` lists every shared composition with a
  still, its props (types, required, notes) and a ready render command — read it before picking or rendering one.**
  The props are zod schemas in `remotion/src/schemas.ts`; bad `--props` fail fast with the field name.
  Render: `npx remotion render <Comp> out.mov --props='<json>'` — transparent ProRes 4444 is the default, no
  flags needed. Everything renders at 60 fps; `REMOTION_FPS=30 npx remotion render …` for a 30 fps edit.
  Give re-renders NEW filenames (Premiere caches by path). Premiere SRT captions: avoid (small, RTL number bugs).
  Layout: shared components by role in `src/{captions,text,promo,fx,maps,minecraft}/`; a graphic made for ONE
  video goes in `src/projects/<name>/index.tsx` (exports `Compositions`, auto-loaded) with media in
  `public/projects/<name>/` — both gitignored. Only move something into the shared folders when another creator
  would genuinely use it; then add its schema in `src/schemas.ts`, register it in `Root.tsx` with neutral
  defaults, and run `npm run catalog` (in `remotion/`).
- **Motion recipes** (slide-in + jelly land, text slam/stretch/fall-out, impact shake with Mirror ×4, flash shake,
  Mr Beast "ELIMINATED"): exact keyframes in `motion-recipes.md`. Read it before animating graphics or camera moves.
- Position keyframes must go through XML `keys` (MCP `add_keyframe` takes numbers only). Crop keyframes don't render
  on export — reposition instead.
- **Sound**: J/L cuts, music, loudness and jump-cut audio in `sound.md`; sound effects in the `sfx` skill.

## 6. Review loop (every time, before the user sees anything)

`mce.push --export` runs QA (black frames, a black flash in the top/bottom of the frame, frozen picture, −14 LUFS /
peaks under −2 dBTP, dead air, V1 gaps, 1–3 frame gaps, flash-short clips, overlapping graphics, overlays running
past the base picture) and writes contact sheets every 0.25 s to `<spec dir>/review/<render>/`. **Read every sheet
and the whole QA list, fix, re-push — then deliver**, saying what you checked. **Never filter push/QA output with
grep** — a 🔴 line hidden that way once shipped a black ending. Sound may not outlast the picture: the builder trims
any SFX/music tail at the last frame ("Tail: … trimmed"); a graphic must end on the same frame as the shot it covers
(in Remotion, durations are `sec(end) - sec(start)`, never `sec(end - start)` — rounding leaves an empty frame).
**Full-panel graphics that shake, zoom, blur or slide must cover their frame every frame** — the gap renders as a
black edge. Overscan backgrounds with an explicit size (`{left: -80, top: -80, width: W + 160, height: H + 160}`;
`inset: -80` on an AbsoluteFill only shifts it), scale a shaken/blurred layer up by what it moves, and before using
the graphic render a check pass with no page background, with alpha, and run
`uv run python -m mce.gfxcheck <check.mov>` — it lists every frame where an edge is uncovered. `export_sequence_review_frames` renders black video — don't trust it; screen captures are unreliable
while the user works.

**Hand edits survive iterations.** The user often edits the delivered sequence in Premiere (trims, razor cuts,
deleted/added clips, scale/position, volume, effects, transitions) before asking for the next round. push pulls
those edits into the spec automatically (from `replaces`, else the same name) and stops if one can't be placed
(`--force` drops them, `--no-pull` skips). Still, **start each new round with
`uv run python -m mce.pull <spec.json>`** and read its list before planning: what the user changed by hand is
feedback, and you plan on top of the current spec, never a stale one. Details:
- If the user touched a clip push generates (auto_sfx sounds, music_fit/playlist/duck music, vo_lufs volume), that
  group is frozen: written out as plain clips with its setting off. Add new SFX/music as plain clips after that.
- Applied changes are recorded in the spec's `_pulled` list, so pulling again won't undo your later edits; a spec
  regenerated by talkshort gets the edits re-applied (matched by media + source range).
- No snapshot (sequence pushed before pull existed): pull compares with the spec of that name next to it, or
  `--against <old spec.json>`; check its list more carefully.
- Clips get stable `"id"`s — keep them when copying a spec to the next version.

Feedback: the user drops markers with comments on the timeline → `uv run python -m mce.notes <spec.json>` lists each
note with the clips/transitions/sounds under it. Act, re-push, and write lasting preferences to style.md.

## 7. Premiere bridge notes

- Calls beyond the loaded MCP tools: `{{MCE_HOME}}/bin/pp call <tool> '<json>'` (`bin/pp list <filter>`,
  `bin/pp schema <tool>`); on Windows `uv run python -m mce.premiere call …`.
- A tool that stops with one ❌ line (ffmpeg failed, Premiere not answering) says what to do; for anything else
  the traceback is followed by a pointer to `uv run python setup/doctor.py`.
- HOST_RECOVERY_REQUIRED (after an uncertain or refused edit) is acknowledged automatically by `mce.premiere`;
  by hand: `inspect_operation_recovery {"backend":"cep"}`, check real state, `acknowledge_operation_recovery`.
- After deleting a sequence Premiere may switch timelines — confirm the active sequence before exporting (push does).
- Gain is capped at +15 dB in Premiere; push pre-boosts very quiet sources itself (XML levels clamp at +6 dB).
- Project layout: `{{EDITING_ROOT}}/<topic>/<project>/` with footage/ audio/ images/ graphics/ captions/ exports/ analysis/;
  copy shared assets in, don't move files other projects use.

## 8. Learn

Every correction ("cut later", "keep the laugh", "music too loud", "captions in one line") → a dated line in
style.md's learned-preferences section, so the next edit already follows it. Personal taste goes there, never
into this skill: the skill is shared with every creator who installs the editor.

## Sharing (repo upkeep)

Repo: github.com/AdirTV/ai-video-editor (local clone = {{MCE_HOME}}). Skills live in the repo's `skills/` (with
path placeholders); after changing them run `uv run python setup/install_skills.py` to update the installed copy.
If you edited the installed copy in `~/.claude/skills` instead, `python3 setup/export_skills.py` copies it back.
Run `uv run pytest -q` after changing `mce/`. Check `git status` holds no media/personal files (per-video Remotion
work stays in `remotion/src/projects/`), commit, push. Never hardcode paths in code — use `mce/config.py`.
