"""Frame interpolation (RIFE): smooth slow motion and higher frame rates for speed ramps.

Uses:
  - slow-mo shots: a clutch moment, a reveal, a fail — x2/x4/x8 without the stutter of duplicated frames;
  - speed ramps on 30 fps footage: make a 60 fps copy (--fps-out 60) so Premiere's slow part of the ramp
    plays real frames instead of blending; cleaner than Premiere's Optical Flow (no warping/ghosting on HUDs).

  uv run python -m mce.slowmo <video> --start S --end E [--factor 2|4|8] [-o out.mov] [--model rife-v4.6]
  → <video>_slowmo_x<factor>.mov : same fps as the source, duration × factor (a slow-mo clip)
  uv run python -m mce.slowmo <video> --start S --end E --fps-out 60 [-o out.mov]
  → <video>_<N>fps.mov : real-time duration at the higher frame rate (slow it down in Premiere)

Output is ProRes 422 HQ .mov, VIDEO ONLY (no audio), starting at --start of the source. Keep the range short:
every output frame is a PNG in a temp dir (4K ≈ 20 MB each). Only the rife-v4* models do x4/x8 and --fps-out
in one pass; older models (rife-v2.x, rife-anime, ...) do x2 only.
Speed (Apple Silicon, rife-v4.6): ~15 output frames/s at 1080p, ~7 at 3840x1080 — a 2 s 1080p30 clip x4 ≈ 20 s.
Needs rife-ncnn-vulkan in ~/.mce/tools (or MCE_RIFE=/path/to/rife-ncnn-vulkan).
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path

from . import ff

TOOLS = Path.home() / ".mce" / "tools"
RIFE_EXE = "rife-ncnn-vulkan.exe" if os.name == "nt" else "rife-ncnn-vulkan"
MODEL = "rife-v4.6"
UHD_PIXELS = 2560 * 1440  # above this, RIFE's UHD mode (-u) handles big motion better


def find_rife() -> Path | None:
    """rife-ncnn-vulkan: MCE_RIFE, then anywhere under ~/.mce/tools, then PATH."""
    env = os.environ.get("MCE_RIFE")
    if env:
        p = Path(env).expanduser()
        return p if p.is_file() else None
    hits = sorted(TOOLS.glob(f"**/{RIFE_EXE}")) if TOOLS.exists() else []
    hits = [h for h in hits if h.is_file()]
    if hits:
        return hits[-1]  # newest release folder sorts last (rife-ncnn-vulkan-YYYYMMDD-…)
    w = shutil.which(RIFE_EXE)
    return Path(w) if w else None


def target_frames(n_in: int, factor: int = 2, src_fps: float | None = None, fps_out: float | None = None) -> int:
    """Frames RIFE should write for n_in source frames: × factor, or rescaled to fps_out at the same duration."""
    if n_in < 2:
        raise ValueError("need at least 2 source frames to interpolate")
    if fps_out is not None:
        if not src_fps or fps_out <= src_fps:
            raise ValueError(f"--fps-out ({fps_out}) must be higher than the source fps ({src_fps})")
        return max(n_in + 1, round(n_in * float(fps_out) / float(src_fps)))
    if factor < 2:
        raise ValueError("factor must be 2 or more")
    return n_in * factor


def output_fps(src_fps: Fraction, fps_out: float | None = None) -> Fraction:
    """Frame rate of the encoded clip: the source rate (slow-mo) or the requested one (NTSC-snapped)."""
    return ff.snap_fps(Fraction(str(fps_out))) if fps_out is not None else src_fps


def default_output(video: str | Path, factor: int = 2, fps_out: float | None = None) -> Path:
    v = Path(video)
    tag = f"{fps_out:g}fps" if fps_out is not None else f"slowmo_x{factor}"
    return v.with_name(f"{v.stem}_{tag}.mov")


def needs_v4(factor: int, fps_out: float | None) -> bool:
    """Arbitrary frame counts (x4/x8, --fps-out) need a rife-v4* model."""
    return fps_out is not None or factor != 2


def interpolate(video: str, start: float, end: float, factor: int = 2, fps_out: float | None = None,
                out: str | Path | None = None, model: str = MODEL, uhd: bool | None = None) -> dict:
    rife = find_rife()
    if not rife:
        raise SystemExit(f"rife-ncnn-vulkan not found. Put the macOS release under {TOOLS} "
                         f"(e.g. {TOOLS}/rife-dl/rife-ncnn-vulkan-20221029-macos/) or set MCE_RIFE=/path/to/{RIFE_EXE}")
    model_dir = Path(model) if Path(model).is_dir() else rife.parent / model
    if not model_dir.is_dir():
        models = sorted(p.name for p in rife.parent.iterdir() if p.is_dir() and p.name.startswith("rife"))
        raise SystemExit(f"model {model!r} not found next to {rife.name}; have: {', '.join(models)}")
    if needs_v4(factor, fps_out) and not model_dir.name.startswith("rife-v4"):
        raise SystemExit(f"{model_dir.name} only does x2; use --model rife-v4.6 for x{factor} / --fps-out")
    if end <= start:
        raise SystemExit("--end must be after --start")

    vs = next((s for s in ff.probe_json(video)["streams"] if s.get("codec_type") == "video"), None)
    if not vs:
        raise SystemExit(f"no video stream in {video}")
    src_fps = ff.stream_fps(vs) or Fraction(30)
    w, h = ff.display_size(vs)
    uhd = w * h > UHD_PIXELS if uhd is None else uhd
    fps = output_fps(src_fps, fps_out)
    out = Path(out) if out else default_output(video, factor, fps_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="mce_slowmo_") as tmp:
        src_dir, dst_dir = Path(tmp) / "in", Path(tmp) / "out"
        src_dir.mkdir()
        dst_dir.mkdir()
        t0 = time.time()
        # constant-rate PNGs at the (snapped) source rate, so frame math = time math even on VFR phone clips
        ff.run(["ffmpeg", "-v", "error", "-ss", f"{start:.6f}", "-i", video, "-t", f"{end - start:.6f}",
                "-map", "0:v:0", "-vf", f"fps={src_fps}", "-pix_fmt", "rgb24", src_dir / "%08d.png"])
        n_in = len(list(src_dir.glob("*.png")))
        n_out = target_frames(n_in, factor, float(src_fps), fps_out)
        t1 = time.time()
        cmd = [rife, "-i", src_dir, "-o", dst_dir, "-n", n_out, "-m", model_dir, "-f", "%08d.png"]
        if uhd:
            cmd.append("-u")
        _run_rife(cmd)
        got = len(list(dst_dir.glob("*.png")))
        if got == 0:
            raise SystemExit("RIFE wrote no frames (GPU/Vulkan problem?) — run it by hand to see its log")
        t2 = time.time()
        ff.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(fps), "-pattern_type", "glob",
                "-i", str(dst_dir / "*.png"), "-c:v", "prores_ks", "-profile:v", "3", "-vendor", "apl0",
                "-pix_fmt", "yuv422p10le", "-r", str(fps), "-an", out])
        t3 = time.time()

    rife_s = t2 - t1
    res = {"out": str(out), "mode": f"fps-out {float(fps):g}" if fps_out is not None else f"slowmo x{factor}",
           "size": f"{w}x{h}", "uhd": uhd, "model": model_dir.name, "src_fps": round(float(src_fps), 3),
           "out_fps": round(float(fps), 3), "frames_in": n_in, "frames_out": got,
           "duration_out": round(got / float(fps), 3),
           "seconds": {"extract": round(t1 - t0, 1), "rife": round(rife_s, 1), "encode": round(t3 - t2, 1),
                       "total": round(t3 - t0, 1)},
           "rife_frames_per_s": round(got / rife_s, 1) if rife_s > 0 else None}
    return res


def _run_rife(cmd: list) -> None:
    import subprocess

    r = subprocess.run([str(c) for c in cmd], capture_output=True)
    if r.returncode:
        tail = "\n".join(r.stderr.decode("utf-8", "replace").strip().splitlines()[-8:])
        raise SystemExit(f"rife-ncnn-vulkan failed (exit {r.returncode}):\n{tail}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.slowmo", description=__doc__.split("\n\n")[0])
    ap.add_argument("video")
    ap.add_argument("--start", type=float, required=True, help="seconds into the source")
    ap.add_argument("--end", type=float, required=True)
    ap.add_argument("--factor", type=int, choices=[2, 4, 8], default=2, help="slow-mo: duration × factor (default 2)")
    ap.add_argument("--fps-out", type=float, help="instead of slow-mo: same duration at this frame rate (e.g. 60)")
    ap.add_argument("-o", "--out", help="default: next to the source, <stem>_slowmo_x<factor>.mov / <stem>_<N>fps.mov")
    ap.add_argument("--model", default=MODEL, help=f"RIFE model folder name (default {MODEL})")
    ap.add_argument("--uhd", action=argparse.BooleanOptionalAction, default=None,
                    help="RIFE UHD mode (default: on above 1440p)")
    a = ap.parse_args()
    try:
        res = interpolate(a.video, a.start, a.end, a.factor, a.fps_out, a.out, a.model, a.uhd)
    except (ff.FFError, ValueError) as e:
        sys.exit(str(e))
    s = res["seconds"]
    print(f"{res['mode']}: {res['frames_in']} → {res['frames_out']} frames, {res['out_fps']:g} fps, "
          f"{res['duration_out']:g} s ({res['size']}, {res['model']}{', UHD' if res['uhd'] else ''})")
    print(f"time: extract {s['extract']} s · RIFE {s['rife']} s ({res['rife_frames_per_s']} frames/s) · "
          f"encode {s['encode']} s · total {s['total']} s")
    print(res["out"])


if __name__ == "__main__":
    main()
