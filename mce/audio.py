"""Audio extraction and loudness-based event detection.

All detectors work on a dB envelope sampled every HOP seconds. Thresholds are
relative to each recording's own noise floor / speech level, so mic gain and
game volume don't need calibrating.
"""
import subprocess
import wave

import numpy as np

SR = 16000
HOP = 0.05  # seconds per envelope frame


def extract(src: str, stream: int, out: str) -> None:
    """Extract one audio stream (0-based among audio streams) as 16 kHz mono wav."""
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", src, "-map", f"0:a:{stream}",
         "-ac", "1", "-ar", str(SR), out],
        check=True,
    )


def load(path: str) -> np.ndarray:
    with wave.open(path) as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def envelope(x: np.ndarray) -> np.ndarray:
    hop = int(SR * HOP)
    n = len(x) // hop
    frames = x[: n * hop].reshape(n, hop)
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    return 20 * np.log10(rms + 1e-6)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Start/end indices (end exclusive) of True runs."""
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def _smooth(db: np.ndarray, seconds: float) -> np.ndarray:
    k = max(1, int(seconds / HOP))
    return np.convolve(db, np.ones(k) / k, mode="same")


def speech_segments(db: np.ndarray, max_gap: float = 0.35, min_len: float = 0.2) -> list[tuple[float, float]]:
    """Voice-activity segments on the mic track, in seconds."""
    floor = np.percentile(db, 10)
    loud = np.percentile(db, 95)
    thr = floor + max(10.0, 0.35 * (loud - floor))
    runs = _runs(db > thr)
    merged: list[list[int]] = []
    for s, e in runs:
        if merged and (s - merged[-1][1]) * HOP <= max_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s * HOP, e * HOP) for s, e in merged if (e - s) * HOP >= min_len]


def excitement(db: np.ndarray, speech: list[tuple[float, float]], z_thr: float = 1.8) -> list[dict]:
    """Moments where the commentator is much louder than their usual speaking level."""
    if not speech:
        return []
    short = _smooth(db, 0.6)
    in_speech = np.zeros(len(db), bool)
    for s, e in speech:
        in_speech[int(s / HOP): int(e / HOP)] = True
    ref = short[in_speech]
    med, std = np.median(ref), max(np.std(ref), 1.0)
    z = (short - med) / std
    events = []
    for s, e in _runs((z > z_thr) & in_speech):
        peak = s + int(np.argmax(z[s:e]))
        events.append({"t": round(peak * HOP, 2), "start": round(s * HOP, 2),
                       "end": round(e * HOP, 2), "score": round(float(z[peak]), 2)})
    return _merge_events(events, 2.0)


def game_events(db: np.ndarray, jump_db: float = 12.0, max_len: float = 2.5) -> list[dict]:
    """Short, sudden spikes on the game track (explosions, hits, deaths).

    A spike has to jump well above the previous ~3 s and fall back quickly, so
    sustained loud audio (music discs, ambient caves, mining loops) is ignored.
    """
    block = int(1.0 / HOP)
    nb = len(db) // block
    if nb < 4:
        return []
    block_med = np.median(db[: nb * block].reshape(nb, block), axis=1)
    baseline = np.full(len(db), np.inf)
    for b in range(3, nb):
        baseline[b * block:(b + 1) * block] = np.median(block_med[b - 3:b])
    floor = np.percentile(db, 10)
    short = _smooth(db, 0.15)
    mask = (short - baseline > jump_db) & (short > floor + 20)
    events = []
    for s, e in _runs(mask):
        if (e - s) * HOP > max_len:
            continue
        peak = s + int(np.argmax(short[s:e]))
        events.append({"t": round(peak * HOP, 2), "score": round(float(short[peak] - baseline[peak]), 1)})
    return _merge_events(events, 1.0)


def _merge_events(events: list[dict], window: float) -> list[dict]:
    out: list[dict] = []
    for ev in sorted(events, key=lambda e: e["t"]):
        if out and ev["t"] - out[-1]["t"] < window:
            if ev["score"] > out[-1]["score"]:
                out[-1] = {**out[-1], **ev, "start": out[-1].get("start", ev.get("start"))}
        else:
            out.append(ev)
    return out
