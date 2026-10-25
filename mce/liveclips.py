"""Clip candidates from a live-stream VOD: merge the analysis highlights (laughs, screams, excitement, spoken
"clip") with chat reactions (`mce.livechat`) and cut each into a self-contained clip — setup → peak → reaction.

Boundaries snap to sentence edges from the transcript: start at the sentence that leads into the peak (≥ `setup`
seconds before it), end after the reaction settles (≥ `after` seconds past it), clamped to [min_len, max_len].
A moment both the streamer and chat reacted to ranks above either alone.

  uv run python -m mce.liveclips <analysis-dir> [--live <live-dir>] [--top 15] [--setup 12] [--after 8]
                                 [--min-len 15] [--max-len 60]

Writes `<analysis-dir>/clips.md` (ranked, with transcript and chat per clip) and `clips.json`.
"""
import argparse
import json
import re
from pathlib import Path

from .sheets import fmt

CHAT_MATCH = 20  # s: a chat spike this close (after lag correction) backs a highlight


def _sentence_start(segments, t):
    """Start of the sentence that contains t, or the last one before it."""
    best = None
    for s in segments:
        if s["start"] <= t:
            best = s["start"]
        else:
            break
    return best if best is not None else t


def _sentence_end(segments, t, limit, gap=2.5):
    """End of the sentence at t, then keep going while the next one follows within `gap` s — a reaction
    ("Kaboom! Yeah, exactly! It was supposed to…") shouldn't be cut mid-flow. Stops at the first pause."""
    i = next((i for i, s in enumerate(segments) if s["end"] >= t), None)
    if i is None:
        return t
    end = segments[i]["end"]
    while i + 1 < len(segments) and segments[i + 1]["start"] - end <= gap and segments[i + 1]["end"] <= limit:
        i += 1
        end = segments[i]["end"]
    return end


def _words(text):
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) > 2}


def chat_reads(chat: list[dict], segments: list[dict], within: float = 90.0) -> list[dict]:
    """Moments the streamer reads a chat message out loud and answers it — a natural clip ("the GOAT, yes").
    A message counts when most of its words (≥2) turn up in what's said within `within` s after it."""
    out = []
    for c in chat:
        cw = _words(c["text"])
        if len(cw) < 2:
            continue
        for s in segments:
            if s["start"] < c["t"] or s["start"] > c["t"] + within:
                continue
            hit = cw & _words(s["text"])
            if len(hit) >= 2 and len(hit) / len(cw) >= 0.6:
                out.append({"t": s["start"], "msg": c["text"], "said": s["text"]})
                break
    return out


def candidates(tl: dict, chat_spikes: list[dict], reads: list[dict] = (), n_msgs: int = 0) -> list[dict]:
    """One row per moment: highlight score + chat backing; chat-only spikes join with their own score.
    Reading chat aloud backs a highlight; it stands alone only when the streamer rarely does it (a small
    channel's streamer reads every message, so there it's routine, not a moment)."""
    rows = [{"t": h["t"], "score": h["score"], "why": list(h["why"]), "chat": None} for h in tl["highlights"]]
    rare = n_msgs and len(reads) / n_msgs < 0.3
    for r in reads:
        near = [x for x in rows if abs(x["t"] - r["t"]) <= CHAT_MATCH]
        if near:
            x = max(near, key=lambda x: x["score"])
            x["score"] += 1.5
            x["why"].append(f"reads chat: “{r['msg'][:40]}”")
        elif rare:
            rows.append({"t": r["t"], "score": 3.0, "why": [f"reads chat: “{r['msg'][:40]}”"], "chat": None})
    for c in chat_spikes:
        near = [r for r in rows if abs(r["t"] - c["moment"]) <= CHAT_MATCH]
        if near:
            r = max(near, key=lambda r: r["score"])
            if r["chat"] is None or c["score"] > r["chat"]["score"]:
                r["chat"] = c
        else:
            rows.append({"t": c["moment"], "score": 0.0, "why": [], "chat": c})
    for r in rows:
        chat = r["chat"]["score"] if r["chat"] else 0.0
        both = 1.5 if r["chat"] and r["score"] > 0 else 1.0  # streamer + chat agree
        r["rank"] = round((r["score"] + 1.2 * chat) * both, 2)
        if r["chat"]:
            r["why"].append(f"chat {r['chat']['kind']} ({r['chat']['msgs']} msgs)")
    return sorted(rows, key=lambda r: -r["rank"])


def bounds(segments, duration, t, setup=12.0, after=8.0, min_len=15.0, max_len=60.0) -> tuple[float, float]:
    a = _sentence_start(segments, t - setup)
    b = _sentence_end(segments, t + after, limit=a + max_len)
    if b - a < min_len:
        b = min(duration, a + min_len)
    if b - a > max_len:  # keep the peak, trim setup first
        a = max(a, t - (max_len - after))
        b = a + max_len
    a, b = max(0.0, a - 0.3), min(duration, b + 0.4)  # breath before, tail after
    return round(a, 2), round(b, 2)


def build(analysis: Path, live: Path | None, top=15, **kw) -> list[dict]:
    tl = json.loads((analysis / "timeline.json").read_text(encoding="utf-8"))
    segments = json.loads((analysis / "transcript.json").read_text(encoding="utf-8"))
    spikes, chat = [], []
    if live and (live / "chat.json").exists():
        from . import livechat
        info = json.loads((live / "vod.json").read_text(encoding="utf-8"))
        chat = json.loads((live / "chat.json").read_text(encoding="utf-8"))
        spikes = livechat.spikes(chat, info["length"], top=40)
    clips = []
    for r in candidates(tl, spikes, chat_reads(chat, segments), len(chat)):
        if len(clips) >= top:
            break
        a, b = bounds(segments, tl["duration"], r["t"], **kw)
        if any(a < c["end"] and b > c["start"] for c in clips):
            continue  # overlaps a better clip
        clips.append({"n": len(clips) + 1, "start": a, "end": b, "dur": round(b - a, 1), "peak": r["t"],
                      "rank": r["rank"], "why": r["why"],
                      "text": " ".join(s["text"].strip() for s in segments if s["end"] > a and s["start"] < b),
                      "chat": [c["text"] for c in chat if a <= c["t"] <= b + 15][:8]})
    return clips


def to_markdown(clips: list[dict], src: str) -> str:
    out = [f"# Clip candidates — {Path(src).name}", ""]
    for c in clips:
        out += [f"## {c['n']}. {fmt(c['start'])}–{fmt(c['end'])} ({c['dur']:.0f}s) · peak {fmt(c['peak'])} · "
                f"rank {c['rank']}", f"*{', '.join(c['why']) or '—'}*", "", f"> {c['text'] or '(no speech)'}"]
        if c["chat"]:
            out += ["", "Chat: " + " · ".join(f"`{m}`" for m in c["chat"])]
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.liveclips")
    ap.add_argument("analysis")
    ap.add_argument("--live", help="dir from `mce.livechat fetch` (default: <video folder>/live)")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--setup", type=float, default=12.0, help="seconds of lead-in before the peak")
    ap.add_argument("--after", type=float, default=8.0, help="seconds of reaction after the peak")
    ap.add_argument("--min-len", type=float, default=15.0)
    ap.add_argument("--max-len", type=float, default=60.0)
    a = ap.parse_args()
    analysis = Path(a.analysis)
    live = Path(a.live) if a.live else analysis.parent / "live"
    clips = build(analysis, live, a.top, setup=a.setup, after=a.after, min_len=a.min_len, max_len=a.max_len)
    src = json.loads((analysis / "timeline.json").read_text(encoding="utf-8"))["source"]
    (analysis / "clips.json").write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
    (analysis / "clips.md").write_text(to_markdown(clips, src), encoding="utf-8")
    for c in clips:
        print(f"{c['n']:2d}. {fmt(c['start'])}–{fmt(c['end'])} ({c['dur']:.0f}s) rank {c['rank']:5.1f}  "
              f"{', '.join(c['why'])}")
    print(f"→ {analysis / 'clips.md'}")


if __name__ == "__main__":
    main()
