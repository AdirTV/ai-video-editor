"""Render exports in Adobe Media Encoder instead of inside Premiere.

A render in its own process can't take Premiere (and unsaved work) down when it leaks or crashes, and
Premiere stays free meanwhile. The catch: Premiere only hands the job over — nothing reports when it's
done — so wait() watches AME's encoding log and the file itself (a complete MP4 of the right length that
has stopped growing) before anyone runs QA on it.

  from mce import ame
  ame.use()       # export_via setting: "ame" / "premiere" / "auto" (= when Media Encoder is installed)
  ame.preset()    # the H.264 "Match Source - High bitrate" preset, same as Premiere's own export
"""
import os
import sys
import time
from pathlib import Path

from . import ff
from .config import EXPORT_VIA

WIN = sys.platform == "win32"
H264 = "4E49434B_48323634"  # AME's H.264 exporter folder (writes .mp4)
PRESET = "00 - Match Source - High bitrate.epr"


def installs() -> list[Path]:
    """Media Encoder installs, newest name last (… (Beta) sorts after the release)."""
    if WIN:
        return sorted(Path(os.environ.get("ProgramFiles", r"C:\Program Files"), "Adobe").glob("Adobe Media Encoder*"))
    return sorted(Path("/Applications").glob("Adobe Media Encoder*"))


def use() -> bool:
    if EXPORT_VIA == "premiere":
        return False
    return bool(installs() and preset())


def preset() -> str | None:
    """Media Encoder's copy of the preset; Premiere ships the same file."""
    roots = installs() + (sorted(Path(os.environ.get("ProgramFiles", r"C:\Program Files"), "Adobe")
                                 .glob("Adobe Premiere Pro*")) if WIN else sorted(Path("/Applications")
                                                                                  .glob("Adobe Premiere Pro*")))
    for root in roots:
        for p in root.glob(f"**/MediaIO/systempresets/{H264}/{PRESET}"):
            return str(p)
    return None


def logs() -> list[Path]:
    """AMEEncodingLog.txt of every Media Encoder version (one per "<app>/<version>" folder)."""
    docs = Path.home() / "Documents" / "Adobe"
    return list(docs.glob("Adobe Media Encoder*/*/AMEEncodingLog.txt"))


def log_sizes() -> dict[Path, int]:
    """Take before handing the job over: wait() only reads what AME writes after it."""
    return {p: p.stat().st_size for p in logs()}


def _log_verdict(out: Path, since: dict[Path, int]) -> str | None:
    """"ok" / an error line, from the log entry AME writes when it finishes our file; None = not yet."""
    for p in logs():
        try:
            with open(p, "rb") as f:
                bom = f.read(2)
                # AME writes the log as UTF-16 (with a BOM); keep reads on whole characters
                enc = {b"\xff\xfe": "utf-16-le", b"\xfe\xff": "utf-16-be"}.get(bom, "utf-8")
                start = since.get(p, 0)
                f.seek(max(start - start % 2, 2) if enc != "utf-8" else start)
                text = f.read().decode(enc, "replace")
        except OSError:
            continue
        i = text.find(out.name)
        if i < 0:
            continue
        tail = text[i:]
        if "Successfully" in tail:
            return "ok"
        for line in tail.splitlines():
            if any(w in line for w in ("Failed", "failed", "Error", "Stopped", "Cancelled")):
                return line.strip()
    return None


def _complete(out: Path, expected: float, tol: float) -> bool:
    """A readable MP4 as long as the sequence (the index is written last, so a partial one won't probe)."""
    try:
        return abs(ff.duration(out) - expected) <= tol
    except ff.FFError:
        return False


def wait(out: Path, expected: float, since: dict[Path, int], fps: float = 30,
         start_timeout: float = 600, stall_timeout: float = 300, poll: float = 5) -> None:
    """Block until AME has finished `out`. Raises RuntimeError when it fails, stalls or never starts writing."""
    t0, last, grew = time.time(), -1, time.time()
    tol = max(0.5, 3 / fps)
    while True:
        verdict = _log_verdict(out, since)
        if verdict and verdict != "ok":
            raise RuntimeError(f"Media Encoder: {verdict}")
        if out.exists():
            size = out.stat().st_size
            if size != last:
                last, grew = size, time.time()
            # the log says done, or (no log entry) the file is whole and hasn't grown for a while
            if (verdict == "ok" or time.time() - grew >= 2 * poll) and _complete(out, expected, tol):
                return
            if verdict == "ok" and time.time() - grew >= 6 * poll:
                try:
                    got = ff.duration(out)
                except ff.FFError:
                    got = 0.0
                raise RuntimeError(f"Media Encoder finished {out.name} but it's {got:.2f}s, not {expected:.2f}s")
            if time.time() - grew > stall_timeout:
                raise RuntimeError(f"Media Encoder stopped writing {out.name} ({stall_timeout / 60:.0f} min "
                                   "without growing) before it was complete")
        elif time.time() - t0 > start_timeout:
            raise RuntimeError(f"Media Encoder didn't start writing {out.name} within {start_timeout / 60:.0f} min "
                               "(is its queue paused, or is another job running?)")
        time.sleep(poll)
