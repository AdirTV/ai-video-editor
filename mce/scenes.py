"""Shot boundaries (PySceneDetect): where the picture cuts to a different shot.

Uses: picking B-roll in/out that never crosses a cut (trailers, news footage), splitting a montage or a
long stream VOD into shots, finding jump cuts in someone else's edit, and — in continuous gameplay —
hard visual changes (death screen, portal/dimension change, teleport, loading screen, menu opening).

Detectors:
  adaptive (default) compares each frame with its rolling neighbourhood, so constant camera motion
           (mouse-look in a game, handheld) doesn't count as a cut — only a jump far above the local motion does.
  content  plain frame-to-frame difference (threshold ~27); catches more, including fast whip pans.
  fade     fades to/from black (threshold = brightness 0-255, ~12).

  uv run python -m mce.scenes <video> [--start S --end E] [--detector adaptive|content|fade]
                              [--threshold X] [--min-len 0.5] [--json out.json]
"""
import argparse
import json
from pathlib import Path

from .sheets import fmt

DEFAULTS = {"adaptive": 3.0, "content": 27.0, "fade": 12.0}


def shots(video: str, start: float | None = None, end: float | None = None, detector: str = "adaptive",
          threshold: float | None = None, min_len: float = 0.5) -> list[dict]:
    """[{i, start, end, dur}] in source seconds covering [start, end]. Cached next to nothing — it's fast
    (~10-30x real time, frames are downscaled)."""
    from scenedetect import AdaptiveDetector, ContentDetector, ThresholdDetector, detect, open_video

    fps = open_video(video).frame_rate
    n = max(1, round(min_len * fps))
    thr = DEFAULTS[detector] if threshold is None else threshold
    det = {"adaptive": lambda: AdaptiveDetector(adaptive_threshold=thr, min_scene_len=n),
           "content": lambda: ContentDetector(threshold=thr, min_scene_len=n),
           "fade": lambda: ThresholdDetector(threshold=thr, min_scene_len=n)}[detector]()
    scenes = detect(video, det, start_time=start, end_time=end, start_in_scene=True)
    return [{"i": i + 1, "start": round(a.seconds, 3), "end": round(b.seconds, 3),
             "dur": round(b.seconds - a.seconds, 3)} for i, (a, b) in enumerate(scenes)]


def cuts(video: str, **kw) -> list[float]:
    """Just the cut times (seconds)."""
    return [s["start"] for s in shots(video, **kw)[1:]]


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.scenes")
    ap.add_argument("video")
    ap.add_argument("--start", type=float)
    ap.add_argument("--end", type=float)
    ap.add_argument("--detector", choices=list(DEFAULTS), default="adaptive")
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--min-len", type=float, default=0.5, help="shortest shot, seconds")
    ap.add_argument("--json", help="also write the shot list here")
    a = ap.parse_args()
    rows = shots(a.video, a.start, a.end, a.detector, a.threshold, a.min_len)
    for r in rows:
        print(f"{r['i']:4d}  {fmt(r['start'])} – {fmt(r['end'])}  ({r['dur']:.2f}s)  [{r['start']:.3f}–{r['end']:.3f}]")
    print(f"{len(rows)} shots")
    if a.json:
        Path(a.json).write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
