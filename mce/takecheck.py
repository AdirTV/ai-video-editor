"""Catch flawed takes from the audio, not just the transcript — any language.

ASR smooths over the things that make a take bad: a speaker who stalls mid-sentence ("I really need… you to")
comes back as one long word or a tidy pause, and cutting that pause out only hides the stall behind a jump cut.
This listens to the voice track itself and flags, inside each kept take:

  * stall: the voice goes quiet mid-sentence (no punctuation before the gap) — a hesitation, a lost line
  * drawn-out word: a word that lasts far longer than the speaker's other words ("חייייב…", "sooo…")
  * trail-off: the voice fades to a mumble inside a sentence and comes back

A flawed take should be replaced by a clean take of the same line (mce.retakes lists them), not trimmed.

  uv run python -m mce.takecheck <media> <transcript.json> 12.3:20.1 45:51.2 [--stream 0]
"""
import argparse
import statistics
from pathlib import Path

import numpy as np

from .ff import run

HOP = 0.025          # envelope step (s)
STALL = 0.22         # quiet this long inside a sentence = a stall
QUIET_DB = 24        # "quiet" = this far under the take's speech level
WEAK_DB = 14         # "mumble" = this far under, but not silent
TRAIL = 0.3          # a mumble this long, then quiet, inside a sentence = trailing off
SENTENCE_END = (".", ",", "?", "!", "…", ":", ";", "-", "—")


def envelope(src: str, stream: int, t0: float, t1: float) -> np.ndarray:
    """RMS level (dBFS) every HOP seconds of the voice track between t0 and t1."""
    raw, _ = run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", src,
                  "-map", f"0:a:{stream}", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], binary=True)
    x = np.frombuffer(raw, np.int16).astype(float) / 32768
    n = int(16000 * HOP)
    if len(x) < n:
        return np.array([-90.0])
    x = x[: len(x) // n * n].reshape(-1, n)
    return 20 * np.log10(np.sqrt((x ** 2).mean(axis=1)) + 1e-9)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            out.append((start, i))
            start = None
    return out


def flaws(words: list[dict], env: np.ndarray, t0: float, med_word: float | None = None) -> list[dict]:
    """Flaws inside one take. `words` = that take's words (start/end in source seconds), `env` its envelope
    starting at t0. Pure, so it can be tested without media."""
    if not words:
        return []
    out = []
    durs = [w["end"] - w["start"] for w in words if len(w["word"].strip(".,?!…")) > 1]
    med = med_word or (statistics.median(durs) if durs else 0.3)
    for w in words:
        d = w["end"] - w["start"]
        if d > max(0.7, 2.6 * med):
            out.append({"t": round(w["start"], 2), "kind": "drawn-out word",
                        "detail": f"'{w['word']}' lasts {d:.2f}s (others ~{med:.2f}s)"})
    speech = float(np.percentile(env, 80))
    idx = lambda t: int(round((t - t0) / HOP))  # noqa: E731
    first, last = idx(words[0]["start"]), idx(words[-1]["end"])
    quiet = env < speech - QUIET_DB
    weak = (env < speech - WEAK_DB) & ~quiet

    def mid_sentence(t: float) -> bool:
        before = [w for w in words if w["end"] <= t + 0.05]
        return bool(before) and not before[-1]["word"].strip().endswith(SENTENCE_END) and before[-1] is not words[-1]

    for a, b in _runs(quiet):
        if a <= first or b >= last or (b - a) * HOP < STALL:
            continue
        t = t0 + a * HOP
        if mid_sentence(t):
            out.append({"t": round(t, 2), "kind": "stall", "detail": f"{(b - a) * HOP:.2f}s of silence mid-sentence"})
    for a, b in _runs(weak):
        if a <= first or b >= last or (b - a) * HOP < TRAIL or b >= len(quiet) or not quiet[b]:
            continue
        t = t0 + a * HOP
        if mid_sentence(t + (b - a) * HOP):
            out.append({"t": round(t, 2), "kind": "trail-off", "detail": f"voice fades for {(b - a) * HOP:.2f}s, then stops"})
    return sorted(out, key=lambda f: f["t"])


def check(src: str, words: list[dict], takes: list, stream: int = 0) -> list[list[dict]]:
    """Flaws per take; takes are [start, end(, label)] in source seconds."""
    durs = [w["end"] - w["start"] for w in words if len(w["word"].strip(".,?!…")) > 1]
    med = statistics.median(durs) if durs else 0.3
    res = []
    for tk in takes:
        t0, t1 = float(tk[0]), float(tk[1])
        ws = [w for w in words if t0 - 0.05 <= w["start"] < t1]
        res.append(flaws(ws, envelope(src, stream, t0, t1), t0, med) if ws else [])
    return res


def load_words(path: str) -> list[dict]:
    import json
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    segs = data["segments"] if isinstance(data, dict) else data
    return sorted(({"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])}
                   for s in segs for w in s.get("words", []) if "start" in w and "end" in w), key=lambda w: w["start"])


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.takecheck")
    ap.add_argument("media")
    ap.add_argument("transcript")
    ap.add_argument("takes", nargs="+", help="start:end in source seconds")
    ap.add_argument("--stream", type=int, default=0, help="audio stream with the voice (0-based)")
    a = ap.parse_args()
    takes = [[float(x) for x in t.split(":")] for t in a.takes]
    for tk, fl in zip(takes, check(a.media, load_words(a.transcript), takes, a.stream)):
        print(f"{tk[0]:7.2f}–{tk[1]:7.2f}  " + ("✔ clean" if not fl else "✘ " + "; ".join(
            f"{f['kind']} at {f['t']:.2f}s ({f['detail']})" for f in fl)))


if __name__ == "__main__":
    main()
