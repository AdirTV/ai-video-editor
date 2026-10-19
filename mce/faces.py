"""Where is the speaker's face? Samples a talking-head recording and caches face
centres, so vertical crops and punch-ins can frame the face instead of the frame centre.

  uv run python -m mce.faces <video> [--every 0.5]   -> <video>_faces.json (or next to --out)
  face_at(track, t0, t1) -> (cx, cy, w) median in source pixels over a range
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def track(src: str, every: float = 0.5, out: Path | None = None) -> list[dict]:
    out = out or Path(src).with_name(Path(src).stem + "_faces.json")
    if out.exists():
        return json.loads(out.read_text())
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = max(1, round(every * fps))
    rows, prev = [], None
    for f in range(0, n, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, f)
        ok, img = cap.read()
        if not ok:
            break
        k = 960 / img.shape[1]
        g = cv2.cvtColor(cv2.resize(img, None, fx=k, fy=k), cv2.COLOR_BGR2GRAY)
        hits = cascade.detectMultiScale(g, 1.1, 5, minSize=(40, 40))
        if len(hits):
            # the face nearest the last one (or the biggest) — ignores posters/background faces
            def score(h):
                x, y, w, hh = h
                c = np.array([x + w / 2, y + hh / 2]) / k
                return -np.linalg.norm(c - prev) if prev is not None else w
            x, y, w, hh = max(hits, key=score)
            prev = np.array([x + w / 2, y + hh / 2]) / k
            rows.append({"t": round(f / fps, 2), "cx": round(float(prev[0])), "cy": round(float(prev[1])),
                         "w": round(w / k)})
    out.write_text(json.dumps(rows))
    return rows


def face_at(rows: list[dict], t0: float, t1: float, default=(960, 540, 200)) -> tuple[float, float, float]:
    """Median face centre and width over [t0, t1] (widens the window until it finds faces)."""
    for pad in (0, 1, 3, 10, 1e9):
        hit = [r for r in rows if t0 - pad <= r["t"] <= t1 + pad]
        if hit:
            return tuple(float(np.median([r[k] for r in hit])) for k in ("cx", "cy", "w"))
    return default


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--every", type=float, default=0.5)
    ap.add_argument("--out")
    a = ap.parse_args()
    rows = track(a.video, a.every, Path(a.out) if a.out else None)
    print(len(rows), "faces;", "median", face_at(rows, 0, 1e9))


if __name__ == "__main__":
    main()
