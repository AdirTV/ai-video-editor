---
name: minecraft-edit
description: Auto-edit a Minecraft gameplay recording (Hebrew commentary, "מיינקראפט אבל..." format) into an editable Adobe Premiere Pro sequence — analyze the recording, find highlights, write a paper edit for approval, then export FCP7 XML with cuts, speed-ups, facecam layout and colored-comment markers. Use when the user wants to edit / cut / build a sequence from a Minecraft recording, plan a Minecraft video structure, or find highlights/shorts in gameplay.
---

# Minecraft auto-edit

Tooling lives in `{{MCE_HOME}}` (CLI: `uv run mce …`). Always prefix shell
commands with `{{PATH_PREFIX}}` — ffmpeg lives there and the Bash tool
doesn't load the login profile. Talk to the user in Hebrew.

Read `{{MCE_HOME}}/style.md` first, every time. Its "העדפות שנלמדו"
section overrides everything else.

## 1. Analyze

```bash
{{PATH_PREFIX}}cd {{MCE_HOME}} && uv run mce analyze "<video>" [--mic 0 --game 1] [--layout auto]
```
- Takes ~5–15 min per recorded hour (transcription dominates); run it in the background for long files.
- Ask which audio stream is the mic and which is game sound if `ffprobe` shows stream titles that don't make it obvious. Default: stream 0 = mic, 1 = game.
- Output folder `<video>_analysis/`:
  - `timeline.md` — ranked candidate moments + a 10-second-per-row timeline (speech, health, flags 🔥💥💔☠️📦💤⭐). Start here.
  - `transcript.md` / `transcript.json` (word-level timestamps — use these for exact cut points).
  - `timeline.json` — raw: speech segments, menus, idle, health drops, death candidates, highlights.
  - `sheets/overview_*.jpg` — 9 gameplay frames per sheet, every 20 s. `sheets/moment_*.jpg` — 9 frames around each top highlight.
- Extra frames on demand: `uv run mce moment <analysis-dir> <seconds> [...]`.

Signals are heuristics. Health/death/menu detection is pixel-based and calibrated on assumptions
until verified on real footage — confirm important moments by looking at the sheets before
building the story on them. Game-audio spikes alone are weak evidence.

## 2. Understand the footage

1. Read `timeline.md` fully, then `transcript.md`.
2. Look at the overview sheets (Read the jpgs) to map milestones: where each dimension/stage starts, where the gimmick shows on screen. Skim — don't read every sheet if the transcript already makes the structure clear.
3. Look at moment sheets for every highlight you're considering keeping.

## 3. Paper edit → user approval

Write `<analysis-dir>/paper_edit.md` in Hebrew and show the user a summary:
- Proposed title(s) and the hook (first 15 s): exact source ranges + why.
- Chapters by milestone. For each kept range: `[mm:ss–mm:ss]` source time, speed, one-line reason.
- What was cut and why (grouped, not every cut).
- Estimated final length vs. the ~13% compression norm from style.md.
- Markers you'll leave and suggested voice-over lines for missing open loops.
- Shorts candidates.

**Do not export before the user approves** (or explicitly says to go straight through).

## 4. Edit plan → Premiere XML

Write `<analysis-dir>/edit_plan.json` (schema in `mce/fcpxml.py` docstring):
- `segments` in final order, source seconds. Snap cut points to word boundaries from `transcript.json` (start ~0.08 s before the first word, end ~0.15 s after the last). Speed-ups: `"speed": 4`; they drop mic/game audio unless `"keep_audio": true`.
- `markers` use source seconds + a type from style.md (fix, broll, fx, graphic, highlight, chapter, music, note). Notes must be actionable ("זום ל-150% על הפנים + סאונד ויין בום").
- `layout` and `audio` come from `timeline.json`.

```bash
{{PATH_PREFIX}}cd {{MCE_HOME}} && uv run mce export "<analysis-dir>/edit_plan.json"
```

## 5. Into Premiere

- If the `premiere` MCP tools are available: verify the connection first, import the XML into the open project (`import_fcp_xml`), then apply a Drop Shadow effect to every clip on V2 (facecam) and read back that it applied. Report anything that didn't verify.
- Otherwise tell the user: File → Import → the `.xml` file; the sequence appears in the project panel.

## Shorts from a script + recorded voiceover (news/update shorts)

1. Read the sequence the user cut (`get_active_sequence`): VO clips' in/out on A1/A2 = the final timing.
2. Caption/cut timing: FORCED-ALIGN the user's script against the VO (`whisperx.align([{start,end,text}], ...)` with the he model per VO clip), not ASR word times — ASR mis-hears words ("והוא"→"טוב הוא") and shifted a section by 0.7 s. Transliterate English/digits for the aligner ("דה סיפט", "אלפיים עשרים ושבע"); numbers are often spoken as words, so time graphics to the spoken words. Map to timeline with `tl = src - inPoint + start`.
3. B-roll source: `yt-dlp` (prefer H.264 — check codec; AV1 is poorly supported in Premiere). Contact sheets at 1 fps to pick shots.
4. Write a spec for `mce.timeline_xml.build` (multi-source, stills, vertical). Fill 16:9 into 9:16 = scale 177.78; text-heavy shots = ~78% on V2 over a blurred fill on V1.
5. Import with `import_fcp_xml` (into_open_project), then apply effects via MCP (Gaussian Blur → resolves to Impact Blur here; Drop Shadow), import the SRT and `create_caption_track`.
6. Verify by `export_sequence` + ffmpeg frames. `export_sequence_review_frames` renders black video here — don't trust it; screen captures are unreliable while the user works.
7. Film Impact (installed) shows up in the transition catalog under its own names: "Pop Motion" (=Impact Pop, the user's favourite), "Pull Motion", "Spin Motion", "Fold Motion", "Glitch", "Flash", "Whip", "Zoom Blur"… `add_transition_to_clip` (start edge, ~0.3 s) pops a PNG in; `add_transition` (track_index + cut_point_seconds) for cuts. "Gaussian Blur" via apply_effect resolves to Impact Blur ("Amount").
8. Zooms/moves: put `"keys": [{"t", "scale", "x", "y"}]` on a timeline_xml clip (t = seconds from clip start). `add_keyframe` only takes numbers, so Position keys must go through XML.
9. Animated graphics (CTA arrow, pop-up text): Remotion project at `{{MCE_HOME}}/remotion` (composition `CTA`, props label/accent). Render with alpha: `npx remotion render CTA out.mov --image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444`, then place on a top video track.
10. Project layout: `{{EDITING_ROOT}}/<topic>/<project>/` with footage/ audio/ images/ graphics/ captions/ exports/ analysis/. Copy shared assets in (don't move files other projects use).
11. If a bridge call returns HOST_RECOVERY_REQUIRED: `inspect_operation_recovery {"backend":"cep"}`, check real state (list_project_items), then `acknowledge_operation_recovery` with both revisions.
12. One-shot pipeline: put "effects"/"pop" on clips and "transitions"/"replaces" at the top of the spec, then
    `uv run python -m mce.push <spec.json> --export <out.mp4>` (imports, applies, deletes the old version, saves, renders).
13. Captions: Remotion `SiftCaptions`-style component (src/sift/Captions.tsx, data in caps.ts) — Rubik 900, 118px, thick stroke,
    keyword colours, pop in/out, centred ~y=980. Premiere SRT captions were rejected by the user (small, bidi bugs with numbers).
15. A refused `delete_multiple_project_items` (item in use) still leaves HOST_RECOVERY_REQUIRED — acknowledge after each refusal. Re-rendered overlays get NEW filenames (Premiere caches media by path).
16. Film Impact "Pull Motion" between two full-frame fills showed a flat teal panel edge — prefer Zoom Blur/Flash/Whip for fill-to-fill cuts.
14. Crop keyframes (AE.ADBE AECrop) store fine but did NOT render on export here — avoid; reposition with XML keys instead.
17. Sound effects: use the `sfx` skill — mark clips with "pop"/"sfx", add top-level "sfx" hits, set "auto_sfx": true before `mce.push`.
Bridge calls beyond the essential MCP pack: `{{MCE_HOME}}/bin/pp call <tool> '<json>'` (`bin/pp list <filter>`, `bin/pp schema <tool>`).

## 6. Learn

When the user corrects the edit ("cut later here", "keep the laugh"), append a dated line to the
"העדפות שנלמדו" section of style.md so the next edit already follows it.

## Review loop (do this every time — the user should see v1 at the quality that used to be v3)

1. `mce.push` exports and then automatically runs QA (black frames, frozen picture, loudness vs −14 LUFS /
   −1 dBTP, dead air, V1 gaps, flash-short clips, overlapping graphics) and writes full contact sheets every
   0.25 s to `<analysis>/review/<render>/`. **Read every sheet and the QA list, fix what's wrong, re-push —
   only then send the render to the user**, saying what you checked.
2. Set `"vo_lufs": -14` on specs with a voiceover (the first uploaded short was −27 LUFS — far too quiet) and
   `"duck_music": true` when there is music (lifts it in speech pauses).
3. User feedback via Premiere markers: ask the user to drop markers with comments on the sequence, then
   `uv run python -m mce.notes <spec.json>` lists each note with the clips/transitions/sounds under it.
   Markers created by the spec itself are skipped. Act on each, re-push, and record lasting preferences in style.md.

## Perception helpers

- `mce.events` (AST AudioSet classifier, runs on Apple GPU): laugh / scream / gasp on the mic, explosion on game
  audio. `mce analyze` already folds these into highlight scoring (😂 / 😱 / 💣 flags in timeline.md) — a laugh
  is the strongest "this was funny" signal you have, since you cannot hear.
- `mce.music analyze <song> --plot x.png`: where the song really starts (skips silence), where it "gets going",
  tempo, bars, sections (intro / build / drop / main / break / outro) and drops. Look at the plot when choosing music.
- Choosing where to start a song: `mce.music fit <song> --duration D [--hit T]`, or in a spec
  `"music_fit": {"hit": T}` (e.g. T = the hook's payoff cut). It starts the song on a bar line so a drop lands
  exactly on T (delaying the music < 1 bar if needed), or without a hit picks the strongest stretch with no break.
  Adds a short fade in/out. Never start music at 0:00 of the file by default — intros are usually the weakest part.
- `mce.beats <music>` + `beats.snap()` for snapping montage cuts to beats; never snap cuts that sit on a spoken word.

## J-cuts and L-cuts

The picture and its sound don't have to cut at the same frame.
- **J-cut** (sound first): the next shot's audio starts under the current picture, then the picture follows.
  Use to *pull* the viewer forward: hear the creeper hiss / explosion / "אחי תראה" before seeing it; start a
  sentence a breath early so it doesn't sound clipped; enter a new scene or chapter softly.
- **L-cut** (sound lingers): the current audio keeps going over the next picture.
  Use to *let something land*: a laugh, scream or explosion tail finishing over the next shot; keep talking
  while showing what you're talking about (B-roll, the result, a reaction); smooth a jump cut in commentary.
- Lengths: 0.1–0.3 s to hide a cut inside speech; 0.3–0.8 s for reactions/impact tails; 1–2 s only for scene or
  chapter transitions. Longer than that feels like a mistake.
- **Don't**: on the punchline cut (in comedy the hard cut *is* the joke); when two people/words would overlap;
  into or out of sped-up segments; when there's no source handle (the tool clamps to available media).
- Shorts with a separate voiceover don't need J/L on the VO — use it on game/footage audio and SFX tails.

How (gameplay edit plans, `mce/fcpxml.py`): on a segment, `"j": 0.3` = its audio starts 0.3 s early; `"l": 0.5` =
its audio runs 0.5 s past its picture. The neighbour's audio is trimmed to make room; video cuts stay put.
Automatic first pass: `uv run python -m mce.jl <edit_plan.json> <timeline.json>` — L where a laugh/scream/explosion
rings over the cut and the next segment isn't talking; J where the next segment opens on a word or a game bang
and the outgoing one is quiet. Review its report, then adjust by taste.

## Music: starts, endings, several songs

- Start: `mce.music fit` / `"music_fit"` (above) — on a bar line, a drop on the payoff, never the weak intro.
- End: `"music_fit": {"end": "fade"}` (default) fades over one bar into the last frame;
  `{"end": "natural"}` lands the song's own ending on the last frame (best when the song has a real ending).
- Several songs: `"music_playlist": {"songs": [{"file": "m1", "until": 30}, {"file": "m2"}], "xfade": null}`.
  Songs alternate between two audio tracks; at each switch the next song starts on its own track under the
  end of the previous one and they crossfade (constant-power, −3 dB at the midpoint; default length 2 bars,
  1–4 s). The incoming song is cut so its drop / "gets going" moment arrives exactly as the old song is gone.
  Switch songs at chapter changes or mood changes, not mid-sentence of an important line.
- In Premiere these are volume keyframes (visible and editable), equivalent to an audio Constant Power cross fade.
