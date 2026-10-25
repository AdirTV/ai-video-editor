"""Voiceover loudness normalisation for timeline specs.

The voiceover dominates a short's loudness, so gaining the VO clips to the
YouTube target (-14 LUFS integrated) lands the whole mix close to it; music and
SFX levels are already set relative to the voice.
"""
import re
import tempfile
from pathlib import Path

from . import ff


def lufs_of_ranges(path: str, ranges: list[tuple[float, float]]) -> float:
    """Integrated loudness of the given source ranges, measured as one stream."""
    with tempfile.TemporaryDirectory() as d:
        parts = []
        for i, (a, b) in enumerate(ranges):
            p = Path(d) / f"{i}.wav"
            ff.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", path,
                    "-ac", "2", "-ar", "48000", str(p)])
            parts.append(f"file '{p.as_posix()}'")  # concat lists treat backslashes as escapes (Windows paths)
        lst = Path(d) / "l.txt"
        lst.write_text("\n".join(parts), encoding="utf-8")
        _, log = ff.run(["ffmpeg", "-hide_banner", "-nostats", "-f", "concat", "-safe", "0", "-i", str(lst),
                         "-af", "ebur128", "-f", "null", "-"])
    found = re.findall(r"I:\s*(-?[\d.]+) LUFS", log)
    if not found:
        raise ff.FFError(f"couldn't measure the loudness of {path}")
    return float(found[-1])


def normalize_vo(spec: dict, vo_file: str = "vo", target: float = -14.0) -> str:
    clips = [c for track in spec.get("audio", []) for c in track if c["file"] == vo_file]
    if not clips:
        return "no voiceover clips"
    measured = lufs_of_ranges(spec["files"][vo_file]["path"], [(c["in"], c["out"]) for c in clips])
    gain = round(target - measured, 1)
    for c in clips:
        c["gain_db"] = gain
    return f"voiceover {measured:.1f} LUFS → {gain:+.1f} dB (target {target:.0f})"


def duck_music(spec: dict, music_file: str = "music", under: str = "vo", lift_db: float = 7.0,
               min_gap: float = 0.6, ramp: float = 0.2) -> str:
    """Keep music at its gain under speech and lift it by lift_db in pauses >= min_gap."""
    speech = sorted((c["start"], c["start"] + c["out"] - c["in"])
                    for tr in spec.get("audio", []) for c in tr if c["file"] == under)
    merged: list[list[float]] = []
    for a, b in speech:
        if merged and a - merged[-1][1] < min_gap:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    n = 0
    for tr in spec.get("audio", []):
        for c in tr:
            if c["file"] != music_file:
                continue
            base, s0 = c.get("gain_db", 0), c["start"]
            e0 = s0 + c["out"] - c["in"]
            # Pauses: before first speech, between speech blocks, after last.
            edges = [s0] + [x for ab in merged for x in ab] + [e0]
            keys = []
            for gs, ge in zip(edges[0::2], edges[1::2]):
                gs, ge = max(gs, s0), min(ge, e0)
                if ge - gs < min_gap:
                    continue
                for t, d in ((gs, base), (gs + ramp, base + lift_db), (ge - ramp, base + lift_db), (ge, base)):
                    keys.append([round(t - s0, 3), d])
            if keys:
                c["gain_keys"] = [[0, base]] + keys + [[round(e0 - s0, 3), base]]
                n += 1
    if not n:
        return (f"music stays at its level: no pause of {min_gap:g}s+ in the speech to lift it in "
                f"({len(merged)} speech block(s))")
    return f"ducked {n} music clip(s) around {len(merged)} speech block(s)"
