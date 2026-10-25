---
name: sfx
description: Add sound effects to a video edit — whooshes on transitions, pops on pop-ins, impacts on big text, magic on transformations, dings on call-to-actions, risers into reveals — synced to the visual peak and levelled under the voiceover, from the user's SFX library. Use when the user asks to add/place/sync sound effects (סאונד אפקטים, SFX, whoosh, pop), wants an edit to "sound" better, or when finishing any short/edit built with the video-edit tooling. Also use to manage the library: index new sounds, find what's missing, fill gaps.
---

# Sound effects

Tooling: `{{MCE_HOME}}/mce/sfx.py`. Prefix shell commands with
`{{PATH_PREFIX}}` and run from `{{MCE_HOME}}`.
Talk to the user in the language they write in.

## The library

`{{SFX_LIB}}/`
- **Curated kit** — one folder per kind (`whoosh pop beep click shutter typing riser impact ding magic glitch`,
  created by the installer). Auto-placement picks ONLY from these when a kind has any, so they define the sound
  of every edit. The user can audition, delete what they dislike, and drop favourites in.
- **Packs** — any sound pack dropped into the library as its own folder is indexed too: used as fallback for
  kinds with no curated sounds, and for specific picks (`search`). Look at the library's top-level folders to
  see which packs this user has.
- `minecraft`/`meme` kinds come from packs (game sounds — only relevant for Minecraft videos —, vine-boom style memes).

Commands (from `{{MCE_HOME}}`):
- `uv run python -m mce.sfx index` — scan the library (parallel; only new/changed files are analyzed). Writes
  `sfx_index.json` (kind, duration, **peak time**, loudness, path tags). Planning refreshes the index by itself
  when sounds were added, removed or replaced, so this is only needed to see the counts.
- `uv run python -m mce.sfx search rabbit hurt` — find specific sounds (all words must appear in the path).
  Use it for content-matched hits: a rabbit sound when a rabbit appears, "levelup" on an achievement,
  zombie groan for a zombie. Put the chosen file as an explicit hit (see below, `"file"` key) .
- `uv run python -m mce.sfx starter` — rebuild the curated kit from the packs (only if the user asks; it
  replaces what they curated — never run it over their own picks without asking).

Classification: Minecraft folders → `minecraft`; then filename keywords; then folder names; else `other`.

## What sound goes where (rules from a pro editor — follow them)

| On screen | Sound | How to mark it |
|---|---|---|
| Movement transition (whip, zoom, push, slide, spin) | **whoosh** | automatic from `transitions` |
| Quick cut / flash | **mouse click** or **camera shutter** | automatic (Flash → shutter; `"name": "Cut"` → click), or `"sfx": "click"` on the transition |
| Object/graphic appearing | **pop** (or **beep** for small UI-like things) | clip `"pop": "start"` / `"sfx": "beep"` |
| Highlighting something | **sparkle** (magic/shimmer/glitter reveal) | clip `"emphasis": true` (`"emphasis_at"` s into the clip) |
| Text appearing | **ASMR typing** for as long as it types on | clip `"text": true` (`"text_dur"` seconds) — generated from single keystrokes in `typing/` |

Kinds in the library: whoosh, pop, beep, click, shutter, typing, riser, impact, ding, magic, glitch (+ minecraft, meme).

## Placing sounds on an edit

Works on a `mce.timeline_xml` spec (see the video-edit skill). Mark intent on the spec:

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
  `{{MCE_HOME}}/style.md`, in its learned-preferences section ("העדפות שנלמדו" / "Learned preferences").
