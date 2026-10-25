"""Read the editor's review markers from Premiere and resolve each one to what
is on the timeline at that moment, so a note like "too early" or "swap this
shot" can be acted on without describing where it is.

  uv run python -m mce.notes <spec.json>

Markers that the spec itself created (Claude's own to-do markers) are skipped;
everything else is treated as a note from the editor.
"""
import json
import sys
from pathlib import Path

from .premiere import Client
from .i18n import t


def _at(spec: dict, t: float, kind: str) -> list[str]:
    out = []
    for i, track in enumerate(spec.get(kind, []), 1):
        for c in track:
            dur = (c["out"] - c["in"]) / (c.get("speed") or 1)
            if c["start"] - 0.05 <= t < c["start"] + dur + 0.05:
                rel = t - c["start"]
                out.append(f"{'V' if kind == 'video' else 'A'}{i} \"{c.get('name', c['file'])}\" "
                           f"({c['start']:.2f}–{c['start'] + dur:.2f}, {rel:.2f}s in, src {c['in'] + rel:.2f})")
    return out


def read_notes(spec_path: str) -> list[dict]:
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    c = Client()
    try:
        c.call("set_active_sequence", {"sequence_id": spec["name"]})
        raw = json.loads(c.call("list_markers", {}))
    finally:
        c.close()
    markers = raw.get("data", raw) if isinstance(raw, dict) else raw
    markers = markers.get("markers", markers) if isinstance(markers, dict) else markers
    own = {(round(m["t"], 1), m.get("note", "")) for m in spec.get("markers", [])}
    notes = []
    for m in markers:
        t = float(m.get("startSeconds", m.get("start", 0)))
        text = " ".join(x for x in (m.get("name", ""), m.get("comments", m.get("comment", ""))) if x).strip()
        if (round(t, 1), m.get("comments", "")) in own:
            continue
        near = [f"{tr['name']} @ {tr['t']}" for tr in spec.get("transitions", []) if abs(tr["t"] - t) < 0.3]
        notes.append({"t": round(t, 2), "note": text or t("empty_note"), "color": m.get("colorIndex", m.get("color")),
                      "video": _at(spec, t, "video"), "audio": _at(spec, t, "audio"), "transitions": near})
    return sorted(notes, key=lambda n: n["t"])


def main() -> None:
    notes = read_notes(sys.argv[1])
    if not notes:
        print(t("no_notes"))
    for n in notes:
        print(f"\n[{n['t']:.2f}s] {n['note']}")
        for line in n["video"] + n["transitions"] + n["audio"]:
            print("   ", line)


if __name__ == "__main__":
    main()
