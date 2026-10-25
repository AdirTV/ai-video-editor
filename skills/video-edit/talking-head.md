# Talking head → vertical short, and face-lock

Commands run from `{{MCE_HOME}}` with `{{PATH_PREFIX}}uv run python -m mce.<tool>`. The creator's own choices
(split ratio, caption look and position, framing, music sources) are in `style.md` — they override the defaults
below.

## Retakes → the takes to keep (`mce.retakes`)

**Never pick takes from the whole-file transcript alone.** On retake-heavy recordings whole-file ASR merges a
broken-off take with the full one after it, drops lines said twice and drifts word times by a second or more —
that has put half-sentences and stalled takes into delivered shorts. First:

```bash
uv run python -m mce.retranscribe <recording> --stream 0 --language he   # one ASR pass per speech region
```

It cuts the voice track at real pauses, transcribes each region on its own (`<recording>_transcript_regions.json`)
and lists regions with speech but no words. Use that transcript for everything below.

For a person talking to camera (often many retakes of the same lines), run
`uv run python -m mce.retakes <transcript_regions.json> --media <recording> --stream 0` (Hebrew, English, any
language; multi-clip transcripts too). `--media` makes it **listen** to every attempt (`mce.takecheck`): a take that
stalls mid-sentence, drags a word ("חייייב…", "sooo…") or trails off loses to a clean take of the same line, and
any flaw is printed with ⚠. It groups the attempts at each line, marks the best (complete, fluent, confident; later takes preferred),
cuts false starts ("so this is part one so this is part one of…") and off-script talk between takes ("okay",
"no", "רגע", "עוד פעם"), and writes `analysis/retakes.json` with `takes` = the ranges to keep.

**A flawed take is replaced, never trimmed.** Cutting out a mid-sentence stall only hides the hesitation behind a
jump cut — the viewer still hears the broken rhythm. If the only take with the full line has a flaw, join the clean
part of another take with the clean part of this one at a sentence boundary (e.g. "…ותירשמו לערוץ!" from take 2 +
"וביחד ננקום בו" from take 3), each checked with `uv run python -m mce.takecheck <recording> <transcript> a:b c:d`.
talkshort runs the same check on every take and **stops** on a flaw (`"allow_flaws": true` only when the user
asked to keep that take).

That's a proposal: read the groups, check the picks against the frames (skip takes where the speaker looks
down/reads or the delivery is flat), drop leftover chatter it can't know about ("let's just do the other one"),
and decide the "repeated word?" list (stutter → cut, emphasis like "ממש ממש" / "really really" → keep).

## The short (`mce.talkshort`)

List the final `takes` in a config (all fields: `uv run python -m mce.talkshort -h` and the module docstring),
then:

```bash
uv run python -m mce.talkshort <config.json> --render
uv run python -m mce.push <spec.json> --export <out.mp4>
```

`--render` builds the spec, renders the captions with Remotion to a new .mov, records it in the config and
rebuilds the spec with it — one step. (Without `--render` it only writes the spec and `caps_props.json`.)

talkshort does the handwork: cuts pauses (word gaps **and** measured silences — ASR stretches words over pauses)
and fillers, pre-masters the voice to a WAV (mic stream of multi-stream recordings), frames the face
(`mce.faces`, cached) and changes punch-in level at every cut and every ~1.8 s inside long sentences (picture only,
audio continuous), crossfades audio on alternating tracks, locks the frame to moving faces, and writes the captions.

- `"layout": "split"` = stream-clip look (game/B-roll top panel, face below, captions on the seam). Shots without
  B-roll fall back to full-frame face. `split_ratio` sets the top panel's share (default 0.4).
  B-roll `"at"` takes a shot id from the printed shot list (`"06a"`, `"06a+0.9"`) or `"word": "phrase"`; clips fill
  their shot and slow down (≥0.7×) if short; `zoom` hides letterboxing (find bars with `cropdetect`), panels are
  cropped at the seam.
- Pick B-roll by what is said (money → cash shots, "robbing a store" → robbery…): the top panel is a *literal*
  picture of the words. Fetch it yourself with `mce.broll` and cut it on shot boundaries (`tools.md`).
- Captions: `"captions": {"look": "stream" | "karaoke", …}`. `stream` = one line, same size, keyword colours
  (`hl`), fixed position: on the seam while the screen is split, lower third (`top`, default 1460) otherwise —
  never moving mid-phrase. `karaoke` = whole phrase shown, words light up as said. Which one, the colours and
  the position are the creator's taste — follow style.md.
- Framing knobs: `full_target_y` (face height on full-frame shots, default 620), `low_face_y` (face height in the
  bottom panel, default 0.42 of it), `full_base`, `punch`. Keep headroom tight: captions must not sit on the mouth.
- Music and SFX: add music (from the sources style.md allows) and SFX — talkshort auto-whooshes B-roll entries;
  add content hits in `"sfx"`.
- Always set `"project"` in the config — several Premiere projects may be open (other sessions); push opens and
  verifies it before importing.
- Hide anything unwanted in the picture (mic lowered, looking away, a flub) with a B-roll `"full": true` cutaway —
  audio keeps running. End on the last content line, not a filler question.

## Face-lock (frame locked to a face)

The frame follows the speaker's face so it stays fixed in the frame while the body/background moves — the
"camera locked to someone's face" reel look (in Premiere by hand: Object Mask on the face → Mask to Motion →
Convert to Motion → Stabilize). Ours: `mce.faces.dense()` tracks the face every 0.1 s (YuNet detector, anchored to
the speaker, occluded/odd-size boxes dropped, smoothed) → position keyframes per shot.

- **When it's needed:** the face moves inside a shot — leaning in/out or sideways, turning, walking, handheld
  phone footage, a close punch-in where the face drifts toward the edge, a reaction where they jump back. Also as a
  deliberate style beat (hold the face dead-centre while the world moves). Check this on every talking shot,
  not only when the user asks.
- **When not:** a still speaker (static framing reads calmer; locking adds micro-wobble), the face is mostly
  covered (hands, looking down — the tracker can't see it), or the shot wants the movement (they walk out of frame).
- talkshort: `"face_lock": "auto"` (default) locks only shots whose face moves ≥ `lock_threshold` (0.25 face
  widths) and was found in ≥60% of samples; prints `face-lock: 07b (0.38)`. `true` forces it, `false` disables.
  `lock_scale` (default off) also holds the face size — only for real in/out moves; occlusion fakes size changes.
- Multi-source specs and fcpxml plans: build the same `keys` by hand from `dense()` (`frame_face` per sample) on
  every shot where the face moves.
