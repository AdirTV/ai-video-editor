"""Keep every clip's level inside what Premiere accepts from XML.

Premiere's FCP-XML import clamps the "Audio Levels" effect at +6 dB (and pops a "Translation Report"
dialog). Quiet sources — Minecraft SFX, soft music intros — often need more. Instead of clip gain, such
clips get a pre-boosted copy of their audio (32-bit float WAV, so the boost can't clip) and the clip gain
drops by the same amount: same sound, no dialog.

  from mce.headroom import fit_gain
  report = fit_gain(spec)   # in place; build() calls it, so every timeline is covered
"""
import hashlib
import math
import os
from pathlib import Path

from . import ff

MAX_CLIP_DB = 6.0   # Premiere clamps XML audio levels above this
TARGET_DB = 5.0     # after boosting, the loudest point of a clip sits here (1 dB margin)
CACHE = Path.home() / ".mce" / "cache" / "boost"


def _peak_db(c: dict) -> float:
    """Loudest level the clip asks for: gain_db, gain_keys and fades (fades are relative to gain_db)."""
    return max([c.get("gain_db", 0.0)] + [d for _, d in c.get("gain_keys", [])])


def _boosted(path: str, stream: int, boost: int) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    tag = hashlib.md5(f"{Path(path).resolve()}|{Path(path).stat().st_mtime}".encode()).hexdigest()[:10]
    out = CACHE / f"{Path(path).stem[:40]}_{tag}_a{stream}_+{boost}dB.wav"
    if not out.exists():
        tmp = out.with_suffix(f".{os.getpid()}.tmp.wav")  # per process: parallel runs don't clash
        ff.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-map", f"0:a:{stream - 1}", "-vn",
                "-af", f"volume={boost}dB", "-c:a", "pcm_f32le", str(tmp)])
        os.replace(tmp, out)  # rename() fails on Windows when out already exists
    return str(out)


def fit_gain(spec: dict) -> list[str]:
    report = []
    files = spec.setdefault("files", {})
    for track in spec.get("audio", []):
        for c in track:
            peak = _peak_db(c)
            if peak <= MAX_CLIP_DB:
                continue
            boost = math.ceil(peak - TARGET_DB)
            src = files[c["file"]]["path"]
            stream = int(c.get("stream", 1))
            key = f"{c['file']}+{boost}dB"
            if key not in files:
                files[key] = {"path": _boosted(src, stream, boost)}
            c["file"], c["stream"] = key, 1
            if "gain_db" in c:
                c["gain_db"] = round(c["gain_db"] - boost, 2)
            if c.get("gain_keys"):
                c["gain_keys"] = [[t, round(d - boost, 2)] for t, d in c["gain_keys"]]
            report.append(f"{c.get('name', key)}: needed {peak:+.1f} dB > +{MAX_CLIP_DB:g} → "
                          f"pre-boosted copy +{boost} dB, clip {_peak_db(c):+.1f} dB")
    return report
