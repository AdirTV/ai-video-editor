# Extra tools: B-roll, stems, shots, cutouts, Lottie, voice clean-up

All `cd {{MCE_HOME}} && {{PATH_PREFIX}}uv run python -m mce.<tool> …`; each prints its usage with `-h`.

## B-roll — find it yourself (`mce.broll`)

When the words name something the viewer should *see* (a block, a mob, a place, a product, money, a game
mechanic), find the shot — don't leave a marker for the user unless nothing usable exists. One literal picture
per idea, a few seconds each, matching what is said at that moment.
1. Own footage first: the project's `footage/`, earlier projects in the editing folder (search file names and
   transcripts), the official clips already downloaded there.
2. `uv run python -m mce.broll search "<thing> <game/brand>"` — prefer the official channel (Minecraft, Rockstar,
   the brand), then clear tutorials/showcases; search in English even for Hebrew videos (more footage).
3. `uv run python -m mce.broll scan <id>` → a frame sheet across the whole video (low-res, fast): look at it and find
   where the thing is actually on screen. Not there → next result.
4. `uv run python -m mce.broll get <id> --from M:SS --to M:SS --name <what> --dir <project>/footage/broll` → H.264 CFR
   60 (or `--fps` of the edit), plus a sheet of the clip: confirm it shows the right thing, with no facecam, UI
   overlays or watermarks you don't want; `mce.scenes` for exact cuts inside it. Strip the source's music with
   `mce.stems` if it would clash (or Content-ID).
5. Client / sponsored work (e.g. a brand video): only footage the user has rights to — their own, the client's,
   or free-licence stock (Pexels, Pixabay — download from the site). Ask if unsure.

## Takes — `mce.retranscribe` and `mce.takecheck`

- `mce.retranscribe <media> [--stream N] [--language he]` → one ASR pass per speech region (cut at measured
  pauses): word times you can cut on, no merged or dropped takes. Prints regions with speech but no words.
- `mce.takecheck <media> <transcript.json> 12.3:20.1 … [--stream N]` → listens to each range: **stall** (quiet
  mid-sentence, no punctuation before it), **drawn-out word** (far longer than the speaker's other words),
  **trail-off** (the voice fades to a mumble and stops inside a sentence). A flagged take is replaced by a clean
  take of the line, not trimmed. talkshort and `mce.retakes --media` run it for you.

## Graphics coverage — `mce.gfxcheck <render-with-alpha.mov>`

Exact check that a full-panel graphic (a top panel, a full-screen card) covers its frame on every frame: render it
with alpha and no page background, and any edge a shake/zoom/blur/slide uncovered is transparent. Lists the sides
and time ranges. Run it on every animated panel before it goes into the edit.

## Stems — `mce.stems <media> [--stream N] [--start S --end E] [--stems voice|all]`

Demucs, ~8× real time: `vocals.wav` + `no_vocals.wav` (or vocals/drums/bass/other), same timing as the source so
they sit 1:1 under it. Uses: kill a trailer's music and keep its dialogue/SFX (Content ID; put our own music under
it); remove the narrator from B-roll; a clean dialogue track when the voice is buried in game noise; lift the voice
and duck the game separately; an a-cappella/instrumental of a song for a beat drop. Listen to the stems (or
QA-measure) — artefacts show on heavy distortion.

## Shots — `mce.scenes <video> [--start S --end E] [--detector adaptive|content|fade] [--json out.json]`

PySceneDetect, ~15-30× real time: shot list with exact cut times. Use for B-roll in/out from trailers and news
footage (never cross a cut), splitting a montage or VOD into shots, finding someone else's jump cuts.
`adaptive` (default) ignores steady camera motion — right for games and handheld; `content` catches more (fast
whip-pans too); `fade` finds fades to black. Shots shorter than `--min-len` (0.5 s) merge into neighbours.
Fast handheld / cinematic trailer camera can fool `adaptive` into a "shot" every ~0.5 s — if the list is mostly
sub-second shots, rerun with `--detector content`.

## Subject cutout — `mce.matte <video> --start S --end E [--point x,y] [--neg x,y] [--box x0,y0,x1,y1]`

SAM 2 video, ~3 frames/s on Apple Silicon → keep it to the seconds you need. ProRes 4444 with alpha of the subject
alone, at the source size/fps, starting at `--start`. No prompt = the main person (biggest, most central); for a
game character/object give a point or box in source pixels (look at a frame first). `--mask` writes a black/white
matte instead (Premiere Track Matte Key).
- **Text behind the subject**: V1 the shot · V2 the text (Remotion `BigText`/`Sticker`, alpha .mov) · V3 the
  cutout — same timeline start as the V1 piece with in = (V1 in − S), and the **same** scale/x/y/keys as V1 so it
  lines up. Big, bold words, 1–3 per beat; works best when the subject is in the lower/middle of frame and the
  text sits behind the head/shoulders.
- Also: background blur/darken/replace behind a talking head (V1 effected copy, V2 cutout), a glow/outline on the
  subject, the subject breaking out of a frame/card.
- Check the cutout on a coloured background before using it (edges, lost hands/hair, a second person grabbed);
  add `--point`/`--neg` and rerun if wrong.

## Lottie animations — Remotion `LottieFx`

Ready-made animated stickers/icons with alpha:
`npx remotion render LottieFx out.mov --props='{"emoji":"😂","size":420,"x":540,"y":700,"seconds":2}'`.
`emoji` = any Noto animated emoji (😂🔥💀😱🤯👀💯🎉❤️…; common ones are cached in `public/lottie/noto/`, others are
fetched — `npm run emoji` in `remotion/` caches every emoji used in the code); `src` = a LottieFiles animation fetched
with `uv run python -m mce.lottie <url.json|url.lottie> <name>` → `"src": "lottie/<name>.json"` (`--list` shows the
library). Props: `size`, `x`/`y` (centre px), `loop`, `speed`, `pop` (pop in/out, default on), `rotate`.
Use for reactions next to a face, arrows/circles pointing at something, subscribe/like animations, icons
(money, alarm, check/cross) — small and short (1–2 s), timed to the word, with a matching SFX.

## Voice clean-up — only when it's needed, at the lightest level that works

Every voice already goes through the normal master (high-pass, light denoise, EQ, de-ess, compression, loudness).
Extra clean-up is for real problems — the user asks for it, or the audio is noisy (room hum, street, kitchen,
crowd, music under the speech). Over-cleaning sounds watery/robotic and is worse than a little room tone.
1. `uv run python -m mce.voice analyze <media> [--stream N] [--transcript …]` → voice vs background level (SNR),
   steady (fan/hiss/AC) vs changing (people/street/music/game) background, mains hum (50/60 Hz), clipping,
   bandwidth, and a suggested level. "clean recording" → do nothing extra.
2. Unsure, or it matters (a client video, a long VO)? `mce.voice compare <media>` → the same 20 s at
   original/light/medium/strong, same loudness, in `<media>_voice_compare/`. Let the user listen and choose.
3. `mce.voice clean <media> --level light|medium|strong [--hum 50] [--declip]` → a mastered, lip-synced WAV for
   the dialogue track (mute the camera audio under it, don't delete it).
   - light = steady hiss/fan under a decent recording · medium = noisy room, pulls the room down in the pauses ·
     strong = Demucs separates the voice from a changing background (music, game, street, crowd) — slow.
   - With strong, the background stem is kept: when the sound around the voice is part of the story (the store,
     the cooking, the game, the crowd's reaction), lay it on its own track 12-18 dB under the voice instead of
     losing it. Silence around a voice in a busy place sounds fake.
   - Can't fix: heavy echo/reverb, very narrow (phone) bandwidth, heavy clipping. For echo, tell the user about
     Premiere's Essential Sound → Dialogue → **Enhance Speech** (Premiere 2024+, one click per clip, very good) or
     Adobe Podcast Enhance — those are clicks for the user. A re-record beats any repair.
4. Talkshort configs already master the voice; to use a cleaned file instead, point the edit at the WAV from step 3.
