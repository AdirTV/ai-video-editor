"""Re-transcribe a recording one speech region at a time — word timings you can cut on.

Whole-file ASR on retake-heavy talking-head recordings goes wrong in exactly the places that matter: it merges a
broken-off take with the full one after it, drops lines it heard twice, and drifts its word timings by a second
or more. Cut between real pauses (measured on the voice track) and transcribed piece by piece, every word lands
inside the region where it was said.

  uv run python -m mce.retranscribe <media> [--stream 0] [--language he] [--out analysis/transcript_regions.json]

Writes the mce transcript format (segments with words), so mce.retakes / mce.takecheck / talkshort read it as is.
Prints any region whose speech has no words — something was said that the ASR missed.
"""
import argparse
import json
import re
import tempfile
from pathlib import Path

from .ff import run

QUIET_DB = -40       # silencedetect noise floor
MIN_PAUSE = 0.35     # pause that separates regions
PAD = 0.15           # context around each region for the ASR


def regions(media: str, stream: int = 0, end: float | None = None) -> list[tuple[float, float]]:
    _, log = run(["ffmpeg", "-hide_banner", "-i", media, "-map", f"0:a:{stream}",
                  "-af", f"silencedetect=n={QUIET_DB}dB:d={MIN_PAUSE}", "-f", "null", "-"])
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    if end is None:
        m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", log)
        end = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else (en[-1] if en else 0.0)
    out, t = [], 0.0
    for a, b in zip(st, en + [end] * (len(st) - len(en))):
        if a - t > 0.15:
            out.append((round(t, 2), round(a, 2)))
        t = b
    if end - t > 0.15:
        out.append((round(t, 2), round(end, 2)))
    return out


def retranscribe(media: str, stream: int = 0, language: str | None = None) -> tuple[list[dict], list]:
    from .transcribe import transcribe
    segs, empty = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for a, b in regions(media, stream):
            o = max(0.0, a - PAD)
            wav = Path(tmp) / f"r{o:.2f}.wav"
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{o:.3f}", "-t", f"{b - o + PAD:.3f}", "-i", media,
                 "-map", f"0:a:{stream}", "-ac", "1", "-ar", "16000", wav])
            words = [{"word": w["word"], "start": round(w["start"] + o, 3), "end": round(w["end"] + o, 3),
                      "score": w.get("score", 1.0)}
                     for s in transcribe(str(wav), language=language) for w in s.get("words", []) if "start" in w]
            if not words:
                if b - a >= 0.4:
                    empty.append((a, b))
                continue
            segs.append({"start": words[0]["start"], "end": words[-1]["end"],
                         "text": " ".join(w["word"] for w in words), "words": words})
    return segs, empty


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.retranscribe")
    ap.add_argument("media")
    ap.add_argument("--stream", type=int, default=0, help="voice audio stream (0-based)")
    ap.add_argument("--language", default=None, help="he, en… (default: detect)")
    ap.add_argument("--out", help="default: transcript_regions.json next to the media")
    a = ap.parse_args()
    segs, empty = retranscribe(a.media, a.stream, a.language)
    out = Path(a.out) if a.out else Path(a.media).with_name(Path(a.media).stem + "_transcript_regions.json")
    out.write_text(json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in segs:
        print(f"[{s['start']:7.2f}–{s['end']:7.2f}] {s['text']}")
    for a_, b_ in empty:
        print(f"!! speech at {a_:.2f}–{b_:.2f}s but no words — listen to it")
    print("→", out)


if __name__ == "__main__":
    main()
