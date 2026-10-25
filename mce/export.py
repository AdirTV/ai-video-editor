"""Render a sequence that's already in Premiere — in Adobe Media Encoder when the export_via setting allows it
(default: when installed), else inside Premiere. Same path as `push --export`, without rebuilding anything;
prefer it over calling the MCP export tool directly, which always renders inside Premiere.

  uv run python -m mce.export <out.mp4> [--sequence NAME] [--direct] [--qa]
"""
import argparse
import json
from pathlib import Path

from .premiere import Client
from .push import _ok, render


def _data(res: str) -> dict:
    d = json.loads(res)
    return d.get("data", d) if isinstance(d, dict) else {}


def seq_seconds(c: Client) -> tuple[float, float]:
    """(end, fps) of the active sequence: the end of its last clip."""
    end, fps, offset = 0.0, 30.0, 0
    while offset is not None:
        d = _data(c.call("get_full_sequence_info", {"clip_limit": 200, "clip_offset": offset}))
        if d.get("timebase"):  # ticks per frame
            fps = 254016000000 / float(d["timebase"])
        for key in ("videoTracks", "audioTracks"):
            for tr in d.get(key, []):
                for cl in tr.get("clips", []):
                    end = max(end, float(cl.get("endSeconds") or cl.get("end") or 0))
        offset = (d.get("pagination") or {}).get("nextOffset")
    return end, fps


def export(out: str, sequence: str | None = None, direct: bool = False, qa: bool = False) -> None:
    c = Client()
    try:
        def call(tool, args, label):
            res = c.call(tool, args)
            print(("✓ " if _ok(res) else "✗ ") + label + ("" if _ok(res) else f"  → {res[:200]}"))
            return res

        if sequence:
            call("set_active_sequence", {"sequence_id": sequence}, f"activate {sequence}")
        name = _data(c.call("get_active_sequence", {"clip_limit": 1})).get("name")
        if sequence and name != sequence:
            raise SystemExit(f"couldn't open sequence {sequence!r} (active: {name!r})")
        call("save_project", {}, "save project")  # Media Encoder renders the saved project
        end, fps = seq_seconds(c)
        print(f"rendering {name!r} ({end:.1f}s)")
        render(c, call, {"fps": fps, "video": [[{"start": 0, "in": 0, "out": end}]]}, out, direct=direct)
    finally:
        c.close()
    if qa:
        from .qa import check_render
        print("QA:\n" + "\n".join(check_render(out)))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("out")
    p.add_argument("--sequence")
    p.add_argument("--direct", action="store_true", help="render inside Premiere, not in Media Encoder")
    p.add_argument("--qa", action="store_true", help="run the render checks on the result")
    a = p.parse_args()
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    export(a.out, a.sequence, a.direct, a.qa)
