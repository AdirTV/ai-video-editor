# Editing style

A living file. Claude reads it before every edit. Every correction you make is added at the end under
"Learned preferences" and overrides the general rules.

## General principles (any kind of video)
- **Hook** in the first 3–15 seconds: what the video promises + a glimpse of its strongest moment.
- **Never more than ~8 seconds without a change**: a new line, shot, zoom, graphic or event.
- **Pauses inside speech**: cut anything over ~0.4 s (unless it's a deliberate dramatic beat). Repeated takes → keep the last good one.
- **Show what's said**: when something is mentioned, we see it (image, clip, graphic).
- **Sound**: the voice always on top; music under it, lifting in pauses; sound effects on transitions and pop-ins, not on every cut.
- **Loudness**: −14 LUFS for YouTube.
- **Vertical short (9:16)**: a 16:9 clip fills the frame (177.78%); if the whole frame matters, a smaller copy over a blurred fill — never black bars.
- **Jump inside a take** (a chunk cut from mid-speech): overlapped audio on two tracks + B-roll over the cut — never leave a visible jump.
- **Sound effects**: whoosh for movement transitions, click/camera shutter for quick cuts, pop for things appearing, sparkle for emphasis, typing as text types on.
- **Don't trust your ears**: measure — Loudness Meter (−14 LUFS) and a Hard Limiter at −2 dB.
- **Captions**: word by word or 2–4 words, one line, big, popping; key words coloured.

## Formats (examples — add your own)
- **News/update short from a voiceover**: finished VO → shots following what's said → captions → CTA at the end.
- **Long gaming video**: ~1 recorded hour ≈ 8 min; speed up travel/mining/building instead of cutting; cut menus and dead time.
- **"Minecraft but…"**: see the minecraft-edit skill (milestones, gimmick, escalation, dragon).
- **Talking head / podcast**: J/L cuts to smooth jump cuts, B-roll on every line that describes something.

## Markers (what Claude leaves for you)
🔴 FIX · 🟡 B-ROLL · 🟣 FX · 🔵 GRAPHIC · 🟢 HIGHLIGHT · 📍 CHAPTER · 🎵 MUSIC · 📝 NOTE

## Learned preferences
<!-- Claude: add every correction from the user here, with a date, e.g.:
- 2026-10-20: don't cut the laugh after a death — keep 1–2 s of reaction.
-->

## Technical lessons (shared)
- Scripted ripple edits don't move Premiere's caption track, and there's no API to edit/delete captions — fix captions before cutting, or ask the user to delete the track. In RTL SRT captions, leave out punctuation (! ? flip).
- Premiere caps clip gain at +15 dB — very quiet SFX can't be raised further; pre-process instead. Raw voiceover peaking near 0 dB → lower ~2.5 dB before boosting.
- Pre-master raw voiceover in ffmpeg (compressor + loudnorm −14 + alimiter after aresample) so boosting never clips. The Premiere mix lands ~2.5 dB under vo_lufs with stereo VO → vo_lufs −11.5 gives ~−14 LUFS. Per-hit peak ceiling for SFX (PEAK_CEIL in sfx.py).
- yt-dlp clips in VFR/30 fps open at the wrong time in Premiere — cut and convert to CFR 60 fps 1080p first. Verify in/out of live footage against real frames (1 fps ffmpeg sheets can be off by half a second).
