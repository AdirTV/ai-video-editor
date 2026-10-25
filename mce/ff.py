"""Shared ffmpeg/ffprobe helpers: one place that checks for failures, probes media and builds
Premiere-compatible file URLs on Mac and Windows."""
import json
import os
import re
import subprocess
from fractions import Fraction
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import quote, unquote, urlparse

# Rates Premiere knows; a phone's variable frame rate (avg 29.87…) snaps to the nearest one
STANDARD_FPS = (23.976, 24, 25, 29.97, 30, 47.952, 48, 50, 59.94, 60, 90, 100, 119.88, 120, 240)


class FFError(RuntimeError):
    """ffmpeg/ffprobe is missing or failed; the message is meant for a person."""


def run(args: list, *, binary: bool = False, check: bool = True, timeout: float | None = None):
    """Run ffmpeg/ffprobe. Returns (stdout, stderr) — bytes stdout when binary, else text.
    A missing binary or (with check) a non-zero exit raises FFError with the end of ffmpeg's log."""
    try:
        r = subprocess.run([str(a) for a in args], capture_output=True, timeout=timeout)
    except FileNotFoundError:
        raise FFError(f"{args[0]} isn't installed or isn't on PATH — run: uv run python setup/doctor.py") from None
    err = r.stderr.decode("utf-8", "replace")
    if check and r.returncode:
        tail = "\n".join(err.strip().splitlines()[-6:])
        raise FFError(f"{args[0]} failed (exit {r.returncode}) on {_input(args)}:\n{tail}")
    return (r.stdout if binary else r.stdout.decode("utf-8", "replace")), err


def _input(args: list) -> str:
    return next((str(args[i + 1]) for i, a in enumerate(args[:-1]) if a == "-i"), str(args[-1]))


def probe_json(path) -> dict:
    out, _ = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    return json.loads(out)


def duration(path) -> float:
    out, _ = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path])
    try:
        return float(out.strip())
    except ValueError:
        raise FFError(f"ffprobe couldn't read the duration of {path}") from None


def rotation(stream: dict) -> int:
    """Clockwise degrees (0/90/180/270) a player turns this video to show it upright. Phones store
    portrait video as landscape frames plus this flag; Premiere ignores it in FCP XML."""
    deg = next((sd.get("rotation") for sd in stream.get("side_data_list", []) if "rotation" in sd), None)
    if deg is None:
        deg = -float(stream.get("tags", {}).get("rotate", 0))  # older files: tag counts clockwise
    return round(-float(deg)) % 360  # ffprobe's display-matrix angle is counter-clockwise


def display_size(stream: dict) -> tuple[int, int]:
    """Width and height as the video is shown (portrait for an upright phone clip)."""
    w, h = int(stream["width"]), int(stream["height"])
    return (h, w) if rotation(stream) in (90, 270) else (w, h)


def stream_fps(stream: dict) -> Fraction | None:
    """Frame rate of a video stream, snapped to a standard rate. None when ffprobe reports none (0/0)."""
    for key in ("avg_frame_rate", "r_frame_rate"):
        try:
            r = Fraction(stream.get(key) or "0/0")
        except (ValueError, ZeroDivisionError):
            continue
        if r > 0:
            return snap_fps(r)
    return None


def snap_fps(r) -> Fraction:
    """Snap to the nearest standard rate within 1.5% (VFR phone footage); NTSC rates come back exact (30000/1001)."""
    best = min(STANDARD_FPS, key=lambda s: abs(float(r) - s))
    if abs(float(r) - best) / best > 0.015:
        return Fraction(r).limit_denominator(1001)
    if round(best) != best:  # 23.976 / 29.97 / 59.94 / 119.88
        return Fraction(round(best) * 1000, 1001)
    return Fraction(int(best))


def pathurl(path, windows: bool | None = None) -> str:
    """xmeml <pathurl> the way Premiere writes it: file:///Users/… on Mac, file://localhost/C%3a/… on Windows."""
    windows = os.name == "nt" if windows is None else windows
    if windows:
        return "file://localhost/" + quote(PureWindowsPath(path).as_posix())
    return "file://" + quote(PurePosixPath(path).as_posix())


def url_to_path(url: str, windows: bool | None = None) -> str:
    """Inverse of pathurl, for URLs written by Premiere or by us (also file:/// and file://localhost/)."""
    windows = os.name == "nt" if windows is None else windows
    p = unquote(urlparse(url).path)
    while p.startswith("//"):
        p = p[1:]
    if windows or re.match(r"^/[A-Za-z]:[/\\]", p):
        return str(PureWindowsPath(p.lstrip("/")))
    return str(Path(p).resolve())
