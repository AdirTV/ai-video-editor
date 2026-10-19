"""Music beat grid, for cutting on the beat.

  uv run python -m mce.beats <music> [--offset SECONDS]   tempo + beat/downbeat times

`snap(t, beats, window)` moves a cut to the nearest beat when one is close
enough; cuts that must stay on a spoken word should not be snapped.
"""
import argparse
import json


def beats(path: str, offset: float = 0.0, duration: float | None = None) -> dict:
    import librosa

    y, sr = librosa.load(path, sr=22050, mono=True, offset=offset, duration=duration)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr, units="frames")
    times = librosa.frames_to_time(frames, sr=sr) + offset
    onset = librosa.onset.onset_strength(y=y, sr=sr)
    # Strongest beat of each group of 4 approximates the downbeat.
    strength = onset[frames] if len(frames) else []
    phase = max(range(4), key=lambda p: sum(strength[p::4])) if len(frames) >= 4 else 0
    return {"tempo": round(float(tempo[0] if hasattr(tempo, "__len__") else tempo), 1), "beats": [round(float(t), 3) for t in times],
            "downbeats": [round(float(t), 3) for t in times[phase::4]]}


def snap(t: float, grid: list[float], window: float = 0.12) -> float:
    near = min(grid, key=lambda b: abs(b - t), default=t)
    return near if abs(near - t) <= window else t


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="mce.beats")
    ap.add_argument("music")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--duration", type=float)
    a = ap.parse_args()
    r = beats(a.music, a.offset, a.duration)
    print(json.dumps({**r, "beats": r["beats"][:16], "downbeats": r["downbeats"][:8], "n_beats": len(r["beats"])}))
