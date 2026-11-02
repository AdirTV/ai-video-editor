"""Cheap per-frame signals from the gameplay picture: motion, brightness, redness.

Game-specific HUD readings (health, menus) come from an add-on profile's `hud` hook
(see mce/plugins.py), computed on the same frames.
"""
import subprocess
from pathlib import Path

import cv2
import numpy as np

SAMPLE_FPS = 2
THUMB_EVERY = 1.0  # seconds between saved thumbnails
THUMB_W, THUMB_H = 480, 270

def detect_layout(src: str, width: int, height: int, duration: float) -> str:
    """For a side-by-side recording, find which half holds the facecam."""
    from .faces import detect

    hits = {"left": 0, "right": 0}
    for t in np.linspace(duration * 0.1, duration * 0.9, 8):
        frame = grab_frame(src, float(t), width, height)
        if frame is None:
            continue
        half = frame.shape[1] // 2
        for side, img in (("left", frame[:, :half]), ("right", frame[:, half:])):
            hits[side] += len(detect(cv2.cvtColor(img, cv2.COLOR_RGB2BGR)))
    return "facecam_left" if hits["left"] >= hits["right"] else "facecam_right"


def grab_frame(src: str, t: float, width: int, height: int) -> np.ndarray | None:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
    ).stdout
    if len(raw) != width * height * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(height, width, 3)


def scan(src: str, width: int, height: int, layout: str, thumbs_dir: Path, hud=None, finish=None) -> list[dict]:
    """Stream the video at SAMPLE_FPS and compute per-sample gameplay signals.

    `hud(frame) -> dict` adds game-specific readings per sample; `finish(samples)` post-processes them.

    Saves a gameplay thumbnail every THUMB_EVERY seconds as t_<seconds>.jpg.
    """
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    # Decode at half resolution (enough for HUD readings: hearts stay ~4-9 px tall).
    sw = width // 2 // 2 * 2
    sh = height // 2 // 2 * 2
    proc = subprocess.Popen(
        # Software decode: measured ~20x faster than videotoolbox for this rawvideo pipe.
        ["ffmpeg", "-v", "error", "-i", src,
         "-vf", f"fps={SAMPLE_FPS},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE,
    )
    size = sw * sh * 3
    samples, prev, i = [], None, 0
    next_thumb = 0.0
    while True:
        raw = proc.stdout.read(size)
        if len(raw) < size:
            break
        frame = np.frombuffer(raw, np.uint8).reshape(sh, sw, 3)
        game = _game_half(frame, layout)
        t = i / SAMPLE_FPS
        small = cv2.resize(game, (160, 90), interpolation=cv2.INTER_AREA).astype(np.int16)
        motion = float(np.mean(np.abs(small - prev))) if prev is not None else 0.0
        prev = small
        samples.append({"t": t, "motion": round(motion, 2), **_signals(game), **(hud(game.astype(np.int16)) if hud else {})})
        if t >= next_thumb:
            thumb = cv2.resize(game, (THUMB_W, THUMB_H), interpolation=cv2.INTER_AREA)
            cv2.imwrite(str(thumbs_dir / f"t_{int(round(t)):06d}.jpg"),
                        cv2.cvtColor(thumb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
            next_thumb += THUMB_EVERY
        i += 1
    proc.wait()
    if finish:
        finish(samples)
    return samples


def _game_half(frame: np.ndarray, layout: str) -> np.ndarray:
    half = frame.shape[1] // 2
    if layout == "facecam_left":
        return frame[:, half:]
    if layout == "facecam_right":
        return frame[:, :half]
    return frame


def _signals(game: np.ndarray) -> dict:
    f = game.astype(np.int16)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    mr, mg, mb = float(r.mean()), float(g.mean()), float(b.mean())
    return {
        "redness": round(mr / (0.5 * (mg + mb) + 1), 2),
        "brightness": round((mr + mg + mb) / 3, 1),
    }
