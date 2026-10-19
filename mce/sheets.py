"""Contact sheets: grids of timestamped gameplay thumbnails for Claude to look at."""
from pathlib import Path

import cv2
import numpy as np

from .vision import THUMB_H, THUMB_W

COLS, ROWS = 3, 3


def fmt(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60}:{t % 60:02d}"


def _thumb(thumbs: Path, t: float) -> np.ndarray:
    p = thumbs / f"t_{int(round(t)):06d}.jpg"
    img = cv2.imread(str(p)) if p.exists() else None
    if img is None:
        img = np.zeros((THUMB_H, THUMB_W, 3), np.uint8)
    label = fmt(t)
    cv2.rectangle(img, (0, 0), (12 + 15 * len(label), 30), (0, 0, 0), -1)
    cv2.putText(img, label, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def sheet(thumbs: Path, times: list[float], out: Path) -> None:
    tiles = [_thumb(thumbs, t) for t in times]
    tiles += [np.zeros_like(tiles[0])] * (COLS * ROWS - len(tiles))
    rows = [np.hstack(tiles[r * COLS:(r + 1) * COLS]) for r in range(ROWS)]
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 82])


def overview(thumbs: Path, duration: float, out_dir: Path, every: float = 20.0) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    times = list(np.arange(0, duration, every))
    paths = []
    for i in range(0, len(times), COLS * ROWS):
        chunk = times[i:i + COLS * ROWS]
        p = out_dir / f"overview_{fmt(chunk[0]).replace(':', '-')}.jpg"
        sheet(thumbs, chunk, p)
        paths.append(p)
    return paths


def moment(thumbs: Path, t: float, duration: float, out_dir: Path) -> Path:
    """Nine frames from 3 s before to 5 s after a moment."""
    out_dir.mkdir(parents=True, exist_ok=True)
    times = [min(max(0.0, t + d), duration - 1) for d in range(-3, 6)]
    p = out_dir / f"moment_{fmt(t).replace(':', '-')}.jpg"
    sheet(thumbs, times, p)
    return p
