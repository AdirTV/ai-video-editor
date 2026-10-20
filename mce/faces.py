"""Where is the speaker's face? Samples a talking-head recording and caches face
centres, so vertical crops and punch-ins can frame the face instead of the frame centre.

  uv run python -m mce.faces <video> [--every 0.5]   -> <video>_faces.json (or next to --out)
  face_at(track, t0, t1) -> (cx, cy, w) median in source pixels over a range
  dense(src, t0, t1)     -> smoothed per-0.1 s face path for one shot (face-lock keyframes)
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


def dense(src: str, t0: float, t1: float, every: float = 0.1, cache: Path | None = None,
          anchor: tuple[float, float, float] | None = None) -> list[dict]:
    """Face centre/width every `every` s over [t0, t1], outliers dropped and smoothed (for face-lock).
    anchor = the speaker's face around then (face_at): detections farther than ~1.5 face widths from it are
    background faces/posters, never the speaker. Cached per range in `cache` (a json dict)."""
    key = f"v2-{t0:.3f}-{t1:.3f}-{every}" + (f"-a{anchor[0]:.0f},{anchor[1]:.0f}" if anchor else "")
    store = json.loads(cache.read_text()) if cache and cache.exists() else {}
    if key in store:
        return store[key]
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(src)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    raw, prev = [], None
    t = t0
    cap.set(cv2.CAP_PROP_POS_MSEC, t0 * 1000)
    step = max(1, round(every * fps))
    f0 = round(t0 * fps)
    f = f0
    while f / fps <= t1 + 1e-6:
        ok, img = cap.read()
        if not ok:
            break
        if (f - f0) % step == 0:
            k = 960 / img.shape[1]
            g = cv2.cvtColor(cv2.resize(img, None, fx=k, fy=k), cv2.COLOR_BGR2GRAY)
            hits = cascade.detectMultiScale(g, 1.1, 8, minSize=(40, 40))  # stricter: occluded faces drop out
            if anchor is not None:
                hits = [h for h in hits if np.hypot((h[0] + h[2] / 2) / k - anchor[0],
                                                    (h[1] + h[3] / 2) / k - anchor[1]) < 1.5 * anchor[2]
                        and 0.5 < (h[2] / k) / anchor[2] < 2.0]
            if len(hits):
                def score(h):
                    x, y, w, hh = h
                    c = np.array([x + w / 2, y + hh / 2]) / k
                    return -np.linalg.norm(c - prev) if prev is not None else w
                x, y, w, hh = max(hits, key=score)
                prev = np.array([x + w / 2, y + hh / 2]) / k
                raw.append((f / fps, float(prev[0]), float(prev[1]), w / k))
        f += 1
    out = []
    if raw:
        a = np.array(raw)
        # drop jumps (another face, false hit): > 0.6 face widths from the running median
        med = np.array([np.median(a[max(0, i - 3):i + 4, 1:3], axis=0) for i in range(len(a))])
        wm = np.median(a[:, 3])
        keep = (np.linalg.norm(a[:, 1:3] - med, axis=1) < 0.6 * wm) & (np.abs(a[:, 3] / wm - 1) < 0.2)
        # (a box much smaller/bigger than usual = hand over the face or a partial hit)
        a = a[keep] if keep.sum() >= 2 else a
        # smooth: centred moving average over ~0.5 s
        n = max(1, round(0.25 / every))
        sm = lambda col: np.array([a[max(0, i - n):i + n + 1, col].mean() for i in range(len(a))])
        out = [{"t": round(float(tt), 3), "cx": round(float(x), 1), "cy": round(float(y), 1), "w": round(float(w), 1)}
               for tt, x, y, w in zip(a[:, 0], sm(1), sm(2), sm(3))]
    if cache:
        store[key] = out
        cache.write_text(json.dumps(store))
    return out


def motion(path: list[dict]) -> float:
    """How much the face moves within a shot, in face widths (max distance from its median position,
    plus relative size change)."""
    if len(path) < 2:
        return 0.0
    a = np.array([[p["cx"], p["cy"], p["w"]] for p in path])
    w = np.median(a[:, 2])
    drift = np.max(np.linalg.norm(a[:, :2] - np.median(a[:, :2], axis=0), axis=1)) / w
    return float(drift + (a[:, 2].max() - a[:, 2].min()) / w)


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
