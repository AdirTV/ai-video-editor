"""Automatic quality check of a rendered edit (and its spec, if given).

  uv run python -m mce.qa <render.mp4> [--spec spec.json] [--sheets DIR]

Checks: black frames, frozen picture, loudness for YouTube (-14 LUFS, true peak
<= -1 dBTP), dead air, and spec problems (V1 gaps, flash-short clips/captions,
overlapping overlays). Writes dense contact sheets so the whole render can be
looked at, not just a few frames.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

TARGET_LUFS, MAX_TP = -14.0, -1.0


def _ff(args: list[str]) -> str:
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args], capture_output=True, text=True).stderr


def _ranges(log: str, start_key: str, end_key: str) -> list[tuple[float, float]]:
    starts = [float(x) for x in re.findall(start_key + r":\s*([\d.]+)", log)]
    ends = [float(x) for x in re.findall(end_key + r":\s*([\d.]+)", log)]
    return list(zip(starts, ends + [float("nan")] * (len(starts) - len(ends))))


def check_render(path: str) -> list[str]:
    issues = []
    black = _ranges(_ff(["-i", path, "-vf", "blackdetect=d=0.08:pix_th=0.08", "-an", "-f", "null", "-"]),
                    "black_start", "black_end")
    for s, e in black:
        issues.append(f"🔴 מסך שחור {s:.2f}–{e:.2f}s")
    freeze = _ranges(_ff(["-i", path, "-vf", "freezedetect=n=0.002:d=0.6", "-an", "-f", "null", "-"]),
                     r"lavfi.freezedetect.freeze_start", r"lavfi.freezedetect.freeze_end")
    for s, e in freeze:
        issues.append(f"🟡 תמונה קפואה {s:.2f}–{e:.2f}s (בסדר אם זה מכוון)")

    loud = _ff(["-i", path, "-af", "ebur128=peak=true", "-vn", "-f", "null", "-"])
    lufs = re.findall(r"I:\s*(-?[\d.]+) LUFS", loud)
    tp = re.findall(r"Peak:\s*(-?[\d.]+) dBFS", loud)
    if lufs:
        i = float(lufs[-1])
        mark = "✅" if abs(i - TARGET_LUFS) <= 1.5 else "🟡"
        issues.append(f"{mark} עוצמה כוללת {i:.1f} LUFS (יעד יוטיוב {TARGET_LUFS:.0f})")
    if tp:
        p = float(tp[-1])
        issues.append(f"{'✅' if p <= MAX_TP else '🔴'} שיא {p:.1f} dBTP (מקסימום {MAX_TP:.0f})")

    silence = _ranges(_ff(["-i", path, "-af", "silencedetect=n=-45dB:d=0.7", "-vn", "-f", "null", "-"]),
                      "silence_start", "silence_end")
    for s, e in silence:
        issues.append(f"🟡 שקט מוחלט {s:.2f}–{e:.2f}s")
    return issues


def check_spec(spec: dict) -> list[str]:
    issues = []
    v1 = sorted(spec.get("video", [[]])[0], key=lambda c: c["start"])
    end = 0.0
    for c in v1:
        if c["start"] - end > 0.02:
            issues.append(f"🔴 חור ב-V1 בין {end:.2f} ל-{c['start']:.2f}s")
        end = max(end, c["start"] + (c["out"] - c["in"]) / (c.get("speed") or 1))
    for t, track in enumerate(spec.get("video", []), 1):
        for c in track:
            d = (c["out"] - c["in"]) / (c.get("speed") or 1)
            if d < 0.25 and "SFX" not in c.get("name", ""):
                issues.append(f"🟡 קליפ קצר מאוד ({d:.2f}s) ב-V{t}: {c.get('name')} @ {c['start']:.2f}")
    # Overlays above V3 that overlap in time compete for attention.
    over = sorted([c for tr in spec.get("video", [])[3:] for c in tr if c.get("name") != "כתוביות"],
                  key=lambda c: c["start"])
    for a, b in zip(over, over[1:]):
        if a["start"] + a["out"] - a["in"] > b["start"] + 0.05:
            issues.append(f"🟡 שתי גרפיקות חופפות: {a.get('name')} ו-{b.get('name')} @ {b['start']:.2f}")
    return issues


def sheets(path: str, out_dir: Path, every: float = 0.25) -> list[Path]:
    """Contact sheets of the whole render: 4x4 frames each, timestamped."""
    out_dir.mkdir(parents=True, exist_ok=True)
    w, h = 216, 384
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf", f"fps={1 / every},scale={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)
    paths = []
    for s in range(0, len(frames), 16):
        tiles = []
        for i, f in enumerate(frames[s:s + 16]):
            f = f.copy()
            cv2.putText(f, f"{(s + i) * every:.2f}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
            tiles.append(f)
        tiles += [np.zeros_like(frames[0])] * (16 - len(tiles))
        p = out_dir / f"review_{s * every:06.2f}.jpg"
        cv2.imwrite(str(p), np.vstack([np.hstack(tiles[r * 4:r * 4 + 4]) for r in range(4)]))
        paths.append(p)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.qa")
    ap.add_argument("render")
    ap.add_argument("--spec")
    ap.add_argument("--sheets")
    a = ap.parse_args()
    issues = check_render(a.render)
    if a.spec:
        issues += check_spec(json.loads(Path(a.spec).read_text()))
    print("\n".join(issues) or "✅ לא נמצאו בעיות")
    if a.sheets:
        for p in sheets(a.render, Path(a.sheets)):
            print(p)


if __name__ == "__main__":
    main()
