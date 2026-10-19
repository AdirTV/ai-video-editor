---
name: sfx
description: Add sound effects to a video edit — whooshes on transitions, pops on pop-ins, impacts on big text, magic on transformations, dings on call-to-actions, risers into reveals — synced to the visual peak and levelled under the voiceover, from the user's SFX library. Use when the user asks to add/place/sync sound effects (סאונד אפקטים, SFX, whoosh, pop), wants an edit to "sound" better, or when finishing any short/edit built with the minecraft-edit tooling. Also use to manage the library: index new sounds, find what's missing, fill gaps.
---

# Sound effects

Tooling: `{{MCE_HOME}}/mce/sfx.py`. Prefix shell commands with
`{{PATH_PREFIX}}` and run from `{{MCE_HOME}}`.
Talk to the user in Hebrew.

## The library

`{{SFX_LIB}}/`
- **Curated kit** — `whoosh pop riser impact ding click magic glitch` folders (~8 each). Auto-placement
  picks ONLY from these when a kind has any, so they define the sound of every edit. the user can audition,
  delete what he dislikes, and drop favourites in.
- **`Jota Pack/`** — 13.9k sounds (22 GB) from "Jota Biggest Minecraft Pack" (Whooshes, Impacts, Risers
  and Swells, Notifications, Minecraft Sounds — every mob/block/UI sound —, Anime, Ed Edd Eddy, Hacking…).
  Used as fallback for kinds with no curated sounds, and for specific picks.
- `minecraft`/`meme` kinds come from the pack (mob sounds, level up, vine-boom style memes).

Commands (from `{{MCE_HOME}}`):
- `uv run python -m mce.sfx index` — rescan after adding/removing sounds (~30 s, parallel). Writes
  `sfx_index.json` (kind, duration, **peak time**, loudness, path tags).
- `uv run python -m mce.sfx search rabbit hurt` — find specific sounds (all words must appear in the path).
  Use it for content-matched hits: a rabbit sound when a rabbit appears, "levelup" on an achievement,
  zombie groan for a zombie. Put the chosen file as an explicit hit (see below, `"file"` key) .
- `uv run python -m mce.sfx starter` — rebuild the curated kit from the pack (only if the user asks; it
  replaces what he curated — never run it over his own picks without asking).

Classification: Minecraft folders → `minecraft`; then filename keywords; then folder names; else `other`.

## Placing sounds on an edit

Works on a `mce.timeline_xml` spec (see the minecraft-edit skill). Mark intent on the spec:

- `transitions` → a whoosh per V1 cut (Glitch transitions get a glitch sound).
- clip `"pop": "start" | "end" | "both"` → pop on the pop-in (softer on the pop-out).
- clip `"sfx": "<kind>"` (+ optional `"sfx_at"` seconds into the clip, `"sfx_align": "start"`)
  → e.g. `impact` on a big "2027", `magic` at a transformation's swap frame, `ding` on a CTA.
- top-level `"sfx": [{"t": 2.417, "kind": "riser"}]` → explicit hits; add `"file": "<path>"` to force a
  specific sound (e.g. the Minecraft rabbit sound from `search`) (a riser peaking on the
  hook's payoff cut is the classic).

Then either set `"auto_sfx": true` and run `uv run python -m mce.push <spec.json> --export …`
(plans, imports, finishes, renders), or preview the plan first with
`uv run python -m mce.sfx plan <spec.json>` (edits the spec in place and prints every hit).

How it syncs: by default the sound's **loudest moment** lands on the event time (a whoosh
peaks on the cut, a riser peaks on the reveal); `align: "start"` starts it on the event
instead (pops, dings). Sounds rotate within a kind so consecutive hits differ. SFX go on two
extra audio tracks (sweeps vs. hits) and never overlap on one track.

## Taste rules

- Sync to what the eye sees (the frame where the pop/flash/zoom peaks), not to the audio.
- Not every cut needs a sound. In a 15 s short, ~6–10 hits; skip ones closer than ~0.4 s.
- Levels: voiceover is king. Per-kind targets live in `LEVEL` in sfx.py (whoosh −26, pop −24,
  impact −22 dBFS around the peak); music bed −20 dB. If the user says SFX are too loud/quiet,
  change `LEVEL` (and note it in style.md) rather than per-clip gains.
- After rendering, listen-check isn't possible for you — check the plan's timings against the
  cut list and tell the user which hits to listen for.
- Record the user's feedback on sounds (too many, too loud, favourite whoosh) in
  `{{MCE_HOME}}/style.md` under "העדפות שנלמדו".
