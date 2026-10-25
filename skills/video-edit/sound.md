# Sound: jump cuts, loudness, J/L cuts, music

Commands run from `{{MCE_HOME}}` with `{{PATH_PREFIX}}uv run python -m mce.<tool>`. Sound effects: the `sfx` skill.

## Jump cuts inside one take

A chunk was cut out of a continuous talking clip: never leave the visible jump —
(1) put the audio of the two sides on alternating tracks overlapping ~0.1 s each way with short fades, so the
jump isn't heard, and (2) cover the cut with a B-roll shot from ~0.5 s before to ~1 s after, so it isn't seen.
In fcpxml plans: `"jump_cover": {"broll": [paths], "overlap": 0.12, "pre": 0.5, "post": 1.0}` does both
(without B-roll files it drops a 🟡 B-ROLL marker on each jump). talkshort does the audio part itself and changes
the punch-in level at every cut. In other multi-source specs, do it by hand.

## Loudness

- **Never ship a render QA calls silent** (−70 LUFS): a Hard Limiter whose amplitude didn't verify once muted a whole
  short; push removes unverified limiters. Prefer pre-mastered voice (talkshort does it) over `limit_db`.
- **Don't trust your ears** (laptop speakers lie; phones are where it's watched): measure. Target −14 LUFS
  integrated for YouTube, peaks under −2 dBTP. In Premiere that's a **Loudness Meter** (YouTube preset) and a
  **Hard Limiter** (Maximum Amplitude −2 dB) on the Mix track. The API can't add Mix-track effects, so: spec
  `"limit_db": -2` puts a Hard Limiter on every audio clip, `"vo_lufs"` sets the voice level, and QA measures the
  render (integrated LUFS + true peak, tells you how much to change vo_lufs). Suggest the user also keeps Loudness
  Meter + Hard Limiter on the Mix track of their sequence template.

## J-cuts and L-cuts

- **J-cut** (sound first): next shot's audio starts under the current picture — pull the viewer forward (hear the
  explosion / "look at this" before seeing it; start a sentence a breath early; enter a scene softly).
- **L-cut** (sound lingers): current audio runs over the next picture — let a laugh/scream/impact finish; keep
  talking over B-roll or the result; smooth a jump cut.
- Lengths: 0.1–0.3 s inside speech; 0.3–0.8 s for reactions/tails; 1–2 s only for scene/chapter changes.
- Don't: on the punchline (the hard cut is the joke), when words would overlap, around sped-up segments.
- How: segment `"j": 0.3` / `"l": 0.5` in fcpxml plans; first pass `uv run python -m mce.jl <plan> <timeline.json>`.
  In multi-source specs, offset the audio clip's start/in from its video clip's.

## Music

Which music sources are allowed (own library, stock sites, game soundtracks) is the creator's call — check style.md;
anything commercial may get a Content ID claim, so say so.
- `uv run python -m mce.music analyze <song> --plot x.png` — real start (skips silence), where it gets going,
  tempo, bars, sections (intro/build/drop/main/break/outro), drops. Look at the plot. (Cached per file.)
- `"music_fit": {"hit": T, "end": "fade"|"natural"}` — start on a bar line so a drop lands exactly on T (e.g. the
  hook's payoff); `natural` lands the song's own ending on the last frame. Never start at 0:00 of the file by default.
- `"music_playlist": {"songs": [{"file": "m1", "until": 30}, {"file": "m2"}]}` — songs on alternating tracks,
  constant-power crossfades; the next song's drop arrives as the old one is gone. Switch at section/mood changes.
- `"duck_music": true` lifts music in speech pauses; `"vo_lufs": -14` sets the voice loudness (the mix lands near
  YouTube's −14 LUFS; if QA says it's ~2.5 dB low with stereo VO, use −11.5).
- `mce.beats` + `beats.snap()` for beat-cut montages (never snap cuts sitting on a word).
