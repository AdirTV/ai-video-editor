"""Exact check that a full-panel graphic covers its whole frame, every frame.

Shakes, zooms, blur and slide-ins pull a layer off the frame edge, and the gap renders as a black strip. Looking
at colours can't tell that strip from a dark background, so render the graphic WITH ALPHA and no page background
(ProRes 4444): anything uncovered is then transparent, and this measures it exactly.

  npx remotion render <Panel> check.mov --image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444 [--props …]
  uv run python -m mce.gfxcheck check.mov [--fps 30] [--min 0.02]

Lists the time ranges and sides where coverage drops (alpha < 0.98 on more than --min of an edge strip).
In Remotion, overscan a background with an explicit size ({left: -80, top: -80, width: W + 160, height: H + 160});
`inset: -80` on an AbsoluteFill keeps width/height 100% and only shifts it.
"""
import argparse

import numpy as np

from .ff import run


def gaps(alpha: np.ndarray, edge: int = 3, min_share: float = 0.02) -> list[str]:
    """Sides of one alpha frame (0..255) where the outer `edge` px aren't fully opaque. Pure, for tests."""
    sides = {"left": alpha[:, :edge], "right": alpha[:, -edge:], "top": alpha[:edge], "bottom": alpha[-edge:]}
    return [s for s, a in sides.items() if (a < 250).mean() > min_share]


def check(path: str, fps: int = 30, min_share: float = 0.02) -> list[tuple[str, float, float]]:
    out, _ = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                  "-of", "csv=p=0", path])
    w0, h0 = (int(x) for x in out.strip().split(",")[:2])
    w, h = max(2, w0 // 4), max(2, h0 // 4)
    raw, _ = run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={fps},alphaextract,scale={w}:{h}:flags=area,format=gray",
                  "-f", "rawvideo", "-"], binary=True)
    frames = np.frombuffer(raw, np.uint8)
    frames = frames[: len(frames) // (w * h) * (w * h)].reshape(-1, h, w)
    hits: dict[str, list[float]] = {}
    for k, a in enumerate(frames):
        for side in gaps(a, 2, min_share):
            hits.setdefault(side, []).append(k / fps)
    res = []
    for side, ts in hits.items():
        start = ts[0]
        for x, y in zip(ts, ts[1:] + [None]):
            if y is None or y - x > 1.5 / fps:
                res.append((side, start, x + 1 / fps))
                start = y
    return sorted(res, key=lambda r: r[1])


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.gfxcheck")
    ap.add_argument("render", help="the graphic rendered with alpha (ProRes 4444 / PNG sequence → mov)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--min", type=float, default=0.02, help="share of an edge strip that may be uncovered")
    a = ap.parse_args()
    res = check(a.render, a.fps, a.min)
    for side, s, e in res:
        print(f"🔴 {side} edge uncovered {s:.2f}–{e:.2f}s")
    print("✅ covers the whole frame" if not res else f"{len(res)} gaps — overscan / scale the layer that moves")


if __name__ == "__main__":
    main()
