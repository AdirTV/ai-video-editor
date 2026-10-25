"""B-roll: find footage for what's being said, pull just the part you need, check it's the right shot.

  uv run python -m mce.broll search "minecraft pointed dripstone" [--n 8]
      → YouTube results: id, channel, length, views, title (official channels first: pick from those)
  uv run python -m mce.broll scan <url|id> [--n 24]
      → a low-res copy of the whole video + a frame sheet across its length: find WHERE the shot is
  uv run python -m mce.broll get <url|id> --from 1:23 --to 1:31 [--name dripstone] [--dir footage/broll] [--fps 60]
      → <dir>/<name>.mp4: H.264, constant frame rate, 1080p max — ready for Premiere (VFR/AV1/VP9 downloads
        drift or won't import). Only that section is downloaded.
  uv run python -m mce.broll sheet <file> [--n 12] [--from S --to E]
      → <file>.sheet.jpg: a grid of frames with timestamps — look at it before using the clip
        (is that really the dripstone? where does the shot change?). Exact cut points: mce.scenes.

Order of preference for sources: the user's own footage → the official channel of the thing being shown
(game studio, brand, event) → reputable creators → anything else. Keep clips short (a few seconds per
cutaway), and for client / sponsored videos use footage the user has rights to.
"""
import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path


def _ytdlp() -> str:
    exe = shutil.which("yt-dlp")
    if not exe:
        raise SystemExit("yt-dlp is missing: brew install yt-dlp (Mac) / winget install yt-dlp.yt-dlp (Windows)")
    return exe


def secs(t: str | float | None) -> float | None:
    """'1:23' / '01:02:03.5' / '83' → seconds."""
    if t is None or isinstance(t, (int, float)):
        return t
    parts = [float(p) for p in str(t).split(":")]
    return sum(p * 60 ** i for i, p in enumerate(reversed(parts)))


def search(query: str, n: int = 8) -> list[dict]:
    out = subprocess.run([_ytdlp(), f"ytsearch{n}:{query}", "--flat-playlist", "-J", "--no-warnings"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stdout
    rows = []
    for e in json.loads(out).get("entries", []):
        rows.append({"id": e.get("id"), "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                     "title": e.get("title", ""), "channel": e.get("channel") or e.get("uploader") or "",
                     "duration": e.get("duration") or 0, "views": e.get("view_count") or 0})
    return rows


def get(url: str, start: float | None, end: float | None, name: str | None = None,
        out_dir: str | Path = "footage/broll", fps: int = 60) -> str:
    out_dir = Path(out_dir)
    raw_dir = out_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if re.fullmatch(r"[\w-]{11}", url):
        url = f"https://www.youtube.com/watch?v={url}"
    vid = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    stem = name or (vid.group(1) if vid else "clip")
    if start is not None:
        stem += f"_{start:g}-{end:g}" if end is not None else f"_{start:g}"
    cmd = [_ytdlp(), url, "--no-warnings", "--no-playlist", "-o", str(raw_dir / f"{stem}.%(ext)s"),
           # H.264 + AAC when offered (imports cleanly), up to 1080p; otherwise the best there is (re-encoded below)
           "-f", "bv*[vcodec^=avc1][height<=1080]+ba[acodec^=mp4a]/bv*[height<=1080]+ba/b", "--merge-output-format", "mp4"]
    if start is not None:
        cmd += ["--download-sections", f"*{start}-{end if end is not None else 'inf'}", "--force-keyframes-at-cuts"]
    subprocess.run(cmd, check=True)
    raw = next(p for p in raw_dir.glob(f"{stem}.*") if p.suffix in (".mp4", ".mkv", ".webm"))
    out = out_dir / f"{stem}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-vf", f"scale='min(1920,iw)':-2,fps={fps}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", str(out)], check=True)
    return str(out)


def scan(url: str, n: int = 24, out_dir: str | Path = "footage/broll") -> str:
    """Whole video at low res (fast) → frame sheet, to find the moment before downloading it properly."""
    raw_dir = Path(out_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    if re.fullmatch(r"[\w-]{11}", url):
        url = f"https://www.youtube.com/watch?v={url}"
    vid = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url)
    stem = f"{vid.group(1) if vid else 'clip'}_scan"
    subprocess.run([_ytdlp(), url, "--no-warnings", "--no-playlist", "-f", "wv*[height>=240][ext=mp4]/wv*[height>=240]/worst",
                    "-o", str(raw_dir / f"{stem}.%(ext)s")], check=True)
    low = next(p for p in raw_dir.glob(f"{stem}.*") if p.suffix in (".mp4", ".mkv", ".webm"))
    return sheet(str(low), n, cols=6)


def sheet(path: str, n: int = 12, start: float | None = None, end: float | None = None, cols: int = 4) -> str:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(path)
    dur = cap.get(cv2.CAP_PROP_FRAME_COUNT) / (cap.get(cv2.CAP_PROP_FPS) or 30)
    a, b = start or 0.0, min(end or dur, dur)
    tiles = []
    for i in range(n):
        t = a + (b - a) * (i + 0.5) / n
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        frame = cv2.resize(frame, (480, round(480 * h / w)))
        label = f"{int(t // 60)}:{t % 60:05.2f}"
        cv2.rectangle(frame, (0, 0), (150, 34), (0, 0, 0), -1)
        cv2.putText(frame, label, (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
        tiles.append(frame)
    if not tiles:
        raise SystemExit(f"couldn't read frames from {path}")
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    grid = np.vstack([np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)])
    out = str(Path(path).with_suffix(".sheet.jpg"))
    cv2.imwrite(out, grid, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return out


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.broll")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--n", type=int, default=8)
    g = sub.add_parser("get")
    g.add_argument("url")
    g.add_argument("--from", dest="start")
    g.add_argument("--to", dest="end")
    g.add_argument("--name")
    g.add_argument("--dir", default="footage/broll")
    g.add_argument("--fps", type=int, default=60)
    g.add_argument("--no-sheet", action="store_true")
    c = sub.add_parser("scan")
    c.add_argument("url")
    c.add_argument("--n", type=int, default=24)
    c.add_argument("--dir", default="footage/broll")
    h = sub.add_parser("sheet")
    h.add_argument("file")
    h.add_argument("--n", type=int, default=12)
    h.add_argument("--from", dest="start")
    h.add_argument("--to", dest="end")
    a = ap.parse_args()
    if a.cmd == "search":
        for r in search(a.query, a.n):
            d = int(r["duration"])
            print(f"{r['id']}  {d // 60:3d}:{d % 60:02d}  {r['views']:>11,}  {r['channel'][:24]:24s}  {r['title'][:70]}")
    elif a.cmd == "get":
        out = get(a.url, secs(a.start), secs(a.end), a.name, a.dir, a.fps)
        print("→", out)
        if not a.no_sheet:
            print("sheet:", sheet(out))
    elif a.cmd == "scan":
        print("sheet:", scan(a.url, a.n, a.dir))
    else:
        print(sheet(a.file, a.n, secs(a.start), secs(a.end)))


if __name__ == "__main__":
    main()
