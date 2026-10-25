"""Source separation (Demucs): split a soundtrack into voice and everything else.

Uses:
  - one-stream recordings where mic and game/music are mixed: transcribe and detect laughs on the clean
    voice, game sounds on the rest (`mce analyze --separate`);
  - B-roll / trailers: drop the music (keep "rest" minus music → stems=all) or the narrator;
  - remixing: duck the game under the voice, replace copyrighted music, louder dialogue.

  uv run python -m mce.stems <media> [--stream N] [--stems voice|all] [--out DIR] [--start S --end E]
  → <out>/vocals.wav + no_vocals.wav  (stems=all: vocals, drums, bass, other)

Output is 44.1 kHz stereo WAV, same timing as the source (from --start), so it lines up 1:1 on the timeline.
Speed: ~1/10 real time on Apple Silicon (MPS) — run hour-long files in the background.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from . import ff

MODEL = "htdemucs"  # "htdemucs_ft" is ~4x slower and slightly cleaner
SR = 44100
CHUNK = 300.0  # seconds per pass (keeps memory flat on long recordings)
XFADE = 2.0    # overlap between passes, crossfaded


def _read(src: str, stream: int | None, start: float, dur: float) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", src, "-t", str(dur),
           "-map", f"0:a:{stream or 0}", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"]
    raw, _ = ff.run(cmd, binary=True)
    return np.frombuffer(raw, np.float32).reshape(-1, 2).T.copy()  # (2, n)


def _duration(src: str) -> float:
    return ff.duration(src)


def _device() -> str:
    import torch

    return "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"


def separate(src: str, out_dir: str | Path, stream: int | None = None, stems: str = "voice",
             start: float = 0.0, end: float | None = None, model: str = MODEL) -> dict[str, str]:
    """Separate one audio stream of `src`. Returns {stem name: wav path}. Cached: reruns are free."""
    import soundfile as sf
    import torch
    from demucs.api import Separator

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    names = ["vocals", "no_vocals"] if stems == "voice" else ["vocals", "drums", "bass", "other"]
    paths = {n: str(out / f"{n}.wav") for n in names}
    stamp = out / "stems.json"
    key = {"src": str(Path(src).resolve()), "mtime": Path(src).stat().st_mtime, "stream": stream,
           "stems": stems, "start": start, "end": end, "model": model}
    if stamp.exists() and json.loads(stamp.read_text(encoding="utf-8")) == key and all(Path(p).exists() for p in paths.values()):
        return paths

    sep = Separator(model=model, device=_device(), progress=False)
    stop = min(end or 1e12, _duration(src))
    writers = {n: sf.SoundFile(p, "w", SR, 2, "PCM_24") for n, p in paths.items()}
    tail: dict[str, np.ndarray] = {}  # last XFADE seconds of the previous pass, not written yet
    pos, nx = start, int(XFADE * SR)
    try:
        while pos < stop - 0.05:
            last = pos + CHUNK >= stop - 0.05
            wav = _read(src, stream, pos, min(CHUNK + XFADE, stop - pos))
            with torch.no_grad():
                _, res = sep.separate_tensor(torch.from_numpy(wav), SR)
            res = {k: v.cpu().numpy() for k, v in res.items()}
            if stems == "voice":
                res = {"vocals": res["vocals"], "no_vocals": sum(v for k, v in res.items() if k != "vocals")}
            for n in names:
                x = res[n]
                if n in tail:  # crossfade the overlap with the previous pass
                    k = min(nx, x.shape[1])
                    ramp = np.linspace(0, 1, k, dtype=np.float32)
                    x[:, :k] = tail[n][:, :k] * (1 - ramp) + x[:, :k] * ramp
                if last:
                    writers[n].write(x.T)
                else:
                    writers[n].write(x[:, :-nx].T)
                    tail[n] = x[:, -nx:]
            pos += CHUNK
    finally:
        for w in writers.values():
            w.close()
    stamp.write_text(json.dumps(key), encoding="utf-8")
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.stems")
    ap.add_argument("media")
    ap.add_argument("--stream", type=int, help="audio stream (0-based); default first")
    ap.add_argument("--stems", choices=["voice", "all"], default="voice")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out", help="default: <media>_stems/")
    a = ap.parse_args()
    out = a.out or Path(a.media).with_suffix("").as_posix() + "_stems"
    print(json.dumps(separate(a.media, out, a.stream, a.stems, a.start, a.end, a.model), indent=1))


if __name__ == "__main__":
    main()
