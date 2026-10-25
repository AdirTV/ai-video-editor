"""Decide where J-cuts and L-cuts belong in a gameplay edit plan.

  uv run python -m mce.jl <edit_plan.json> <timeline.json>   (edits the plan in place)

J-cut (sound first): the next segment's audio starts under the current picture.
L-cut (sound lingers): the current segment's audio runs over the next picture.

Rules, from the analysis timeline (source seconds):
  L  a laugh / scream / explosion is still ringing at the cut → let it finish
     (up to 0.8 s), but only if the next segment isn't talking in that window.
  J  the next segment opens on a word or a big game sound right at its in-point
     → start its audio 0.15–0.3 s early so the breath/attack isn't clipped,
     but only if the outgoing segment is silent in that window.
  Hard cut otherwise — in fast comedy edits the hard cut *is* the joke.
"""
import json
import sys
from pathlib import Path

MAX_L, MAX_J = 0.8, 0.3


def _speech_in(speech: list, a: float, b: float) -> bool:
    return any(s < b and e > a for s, e in speech)


def auto(plan: dict, tl: dict) -> list[str]:
    speech = tl.get("speech", [])
    sounds = tl.get("sounds", []) + [{"kind": "game", "t": e["t"], "start": e["t"] - 0.1, "end": e["t"] + 0.5}
                                     for e in tl.get("game_events", [])]
    segs, report = plan["segments"], []
    for k in range(len(segs) - 1):
        a, b = segs[k], segs[k + 1]
        if float(a.get("speed", 1) or 1) != 1 or float(b.get("speed", 1) or 1) != 1:
            continue
        if a.get("l") or b.get("j"):
            continue  # an explicit decision wins
        # L: a reaction/impact that the cut would chop off.
        ring = [e for e in sounds if e["kind"] in ("laugh", "scream", "explosion", "game")
                and e["start"] < a["out"] < e["end"] + 0.05]
        if ring:
            tail = min(MAX_L, max(e["end"] for e in ring) - a["out"] + 0.1)
            if tail >= 0.12 and not _speech_in(speech, b["in"], b["in"] + tail):
                a["l"] = round(tail, 2)
                report.append(f"L {tail:.2f}s after seg {k + 1} ({ring[0]['kind']} rings over the cut)")
                continue
        # J: the next segment starts right on a word / bang.
        starts_talking = any(abs(s - b["in"]) < 0.15 or (s < b["in"] < s + 0.15) for s, _ in speech)
        bang = any(b["in"] - 0.1 <= e["t"] <= b["in"] + 0.25 for e in sounds if e["kind"] in ("explosion", "game"))
        if starts_talking or bang:
            lead = 0.3 if bang else 0.2
            if not _speech_in(speech, a["out"] - lead, a["out"]):
                b["j"] = lead
                report.append(f"J {lead:.2f}s into seg {k + 2} ({'game sound' if bang else 'speech'} starts at the cut)")
    return report


if __name__ == "__main__":
    plan_path, tl_path = sys.argv[1], sys.argv[2]
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    rep = auto(plan, json.loads(Path(tl_path).read_text(encoding="utf-8")))
    Path(plan_path).write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(rep) or "hard cuts everywhere (nothing called for J/L)")
