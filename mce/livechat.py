"""Live-stream chat as a highlight signal: download a Twitch VOD's chat replay and the clips viewers already
made from it, then find the moments chat reacted to.

Chat is the one signal a solo recording doesn't have — viewers laughing (KEKW, LUL, "lol", חחח), hyping (Pog,
"W", "CLIP IT"), or groaning (F, "nooo") right after something happened. Chat lags the picture: stream delay
plus typing time, ~4-12 s, so a spike at t points at something around t - lag.

Viewer clips (`clips.json`) are free ground truth: each one is a moment someone cared enough to clip.

  uv run python -m mce.livechat fetch <twitch vod url or id> <out-dir>     # chat.json + clips.json
  uv run python -m mce.livechat spikes <out-dir> [--window 10] [--lag 6] [--top 20]

Small channels (a handful of chatters) give a thin signal — a single viewer's "lol" still counts, but rank it
with the audio/transcript moments from `mce.cli analyze` rather than on its own.
"""
import argparse
import json
import re
import statistics
import time
import urllib.request
from pathlib import Path

from .sheets import fmt

GQL = "https://gql.twitch.tv/gql"
CLIENT_ID = "kimne78kx3ncx6brgo4mv6wki5h1ko"  # Twitch's public web-player client id
COMMENTS_HASH = "b70a3591ff0f4e0313d126c6a1502d79a1c02baebb288227c582044aa76adf6a"

# Reaction lexicon — lower-cased tokens / emote names. Hebrew laughter is any run of ח.
REACTIONS = {
    "laugh": {"lol", "lmao", "lmfao", "rofl", "kekw", "kek", "lul", "lulw", "omegalul", "icant", "haha", "hahaha",
              "xd", "xdd", "😂", "🤣", "💀", "dead", "dying", "pepelaugh", "kappa"},
    "hype": {"pog", "poggers", "pogchamp", "pogu", "w", "ww", "www", "wow", "omg", "letsgo", "lets", "clip", "clipit",
             "hype", "gg", "🔥", "insane", "crazy", "sheesh", "ez", "nice", "וואו", "יאללה", "אש"},
    "fail": {"f", "l", "ll", "rip", "oof", "nooo", "noo", "no", "bruh", "monkas", "notlikethis", "sadge", "😭", "😬"},
}
HEB_LAUGH = re.compile(r"^ח{3,}$")
LATIN_LAUGH = re.compile(r"^(ha){2,}h?$|^(he){3,}$|^x+d+$")


def vod_id(s: str) -> str:
    m = re.search(r"(\d{6,})", s)
    if not m:
        raise SystemExit(f"not a Twitch VOD url/id: {s}")
    return m.group(1)


def _post(body):
    req = urllib.request.Request(GQL, json.dumps(body).encode(),
                                 {"Client-ID": CLIENT_ID, "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(req, timeout=30))
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def fetch_chat(vid: str) -> list[dict]:
    """[{t, user, text, emotes}] for the whole VOD, t = seconds into the VOD."""
    out, seen, variables = [], set(), {"videoID": vid, "contentOffsetSeconds": 0}
    while True:
        d = _post([{"operationName": "VideoCommentsByOffsetOrCursor", "variables": variables,
                    "extensions": {"persistedQuery": {"version": 1, "sha256Hash": COMMENTS_HASH}}}])
        comments = ((d[0].get("data") or {}).get("video") or {}).get("comments")
        if not comments:
            break
        for e in comments["edges"]:
            n = e["node"]
            if n["id"] in seen:
                continue
            seen.add(n["id"])
            frags = (n.get("message") or {}).get("fragments") or []
            out.append({"t": n["contentOffsetSeconds"], "user": (n.get("commenter") or {}).get("login"),
                        "text": "".join(f["text"] for f in frags),
                        "emotes": [f["text"] for f in frags if f.get("emote")]})
        if not comments["pageInfo"]["hasNextPage"] or not comments["edges"]:
            break
        variables = {"videoID": vid, "cursor": comments["edges"][-1]["cursor"]}
    return sorted(out, key=lambda c: c["t"])


def fetch_vod_info(vid: str) -> dict:
    """VOD title/length + channel clips that point into this VOD (most viewed first)."""
    q = """query($id:ID!){ video(id:$id){ id title lengthSeconds createdAt owner{ login
      clips(first:100, criteria:{period:ALL_TIME, sort:VIEWS_DESC}){ edges{ node{
        slug title viewCount durationSeconds videoOffsetSeconds video{id} curator{login} }}}}}}"""
    v = _post({"query": q, "variables": {"id": vid}})["data"]["video"]
    clips = [e["node"] for e in v["owner"]["clips"]["edges"] if (e["node"].get("video") or {}).get("id") == vid]
    return {"id": v["id"], "title": v["title"], "length": v["lengthSeconds"], "created": v["createdAt"],
            "channel": v["owner"]["login"],
            "clips": [{"slug": c["slug"], "title": c["title"], "views": c["viewCount"],
                       "start": c["videoOffsetSeconds"], "dur": c["durationSeconds"],
                       "by": (c.get("curator") or {}).get("login")} for c in clips]}


def classify(msg: dict) -> set[str]:
    """Which reaction kinds a message carries."""
    kinds = set()
    for tok in re.findall(r"[\w']+|[^\w\s]", msg["text"].lower()) + [e.lower() for e in msg["emotes"]]:
        if HEB_LAUGH.match(tok) or LATIN_LAUGH.match(tok):
            kinds.add("laugh")
        for k, words in REACTIONS.items():
            if tok in words:
                kinds.add(k)
    letters = [ch for ch in msg["text"] if ch.isalpha() and ch.isascii()]
    if len(letters) >= 4 and sum(ch.isupper() for ch in letters) / len(letters) > 0.8:
        kinds.add("hype")  # SHOUTING
    if "!!" in msg["text"] or "??" in msg["text"]:
        kinds.add("hype")
    return kinds


def windows(chat: list[dict], length: float, window: float = 10.0) -> list[dict]:
    """Per-window counts: msgs, unique chatters, reactions by kind."""
    n = int(length // window) + 1
    rows = [{"t": i * window, "msgs": 0, "users": set(), "laugh": 0, "hype": 0, "fail": 0, "sample": []}
            for i in range(n)]
    for c in chat:
        r = rows[min(n - 1, int(c["t"] // window))]
        r["msgs"] += 1
        r["users"].add(c["user"])
        for k in classify(c):
            r[k] += 1
        if len(r["sample"]) < 4:
            r["sample"].append(c["text"][:60])
    for r in rows:
        r["users"] = len(r["users"])
    return rows


def spikes(chat: list[dict], length: float, window: float = 10.0, lag: float = 6.0, baseline_s: float = 300.0,
           top: int = 20) -> list[dict]:
    """Moments chat reacted to, ranked. Score = activity above the rolling baseline (so a busy stream needs a
    bigger burst than a quiet one) + reactions. `moment` is shifted back by `lag` to where the event likely was."""
    rows = windows(chat, length, window)
    half = max(1, int(baseline_s / window / 2))
    for i, r in enumerate(rows):
        around = [x["msgs"] for x in rows[max(0, i - half):i + half + 1]]
        base = statistics.median(around)
        r["score"] = round(max(0.0, r["msgs"] - base) + 0.5 * (r["users"] - 1 if r["users"] > 1 else 0)
                           + 1.5 * r["laugh"] + 1.2 * r["hype"] + 0.8 * r["fail"], 2)
    picks = []
    for r in sorted(rows, key=lambda x: -x["score"]):
        if r["score"] <= 0 or len(picks) >= top:
            break
        if any(abs(r["t"] - p["t"]) < 30 for p in picks):
            continue  # one pick per burst
        kind = max(("laugh", "hype", "fail"), key=lambda k: r[k]) if r["laugh"] + r["hype"] + r["fail"] else "talk"
        picks.append({**r, "kind": kind, "moment": max(0.0, r["t"] - lag)})
    return picks


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.livechat")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download chat replay + viewer clips")
    f.add_argument("vod")
    f.add_argument("out")
    s = sub.add_parser("spikes", help="rank chat reactions")
    s.add_argument("out")
    s.add_argument("--window", type=float, default=10.0)
    s.add_argument("--lag", type=float, default=6.0, help="seconds chat trails the picture")
    s.add_argument("--top", type=int, default=20)
    a = ap.parse_args()
    out = Path(a.out)
    if a.cmd == "fetch":
        out.mkdir(parents=True, exist_ok=True)
        vid = vod_id(a.vod)
        info = fetch_vod_info(vid)
        (out / "vod.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        chat = fetch_chat(vid)
        (out / "chat.json").write_text(json.dumps(chat, ensure_ascii=False), encoding="utf-8")
        print(f"{info['channel']} — {info['title']} ({fmt(info['length'])}): {len(chat)} chat messages from "
              f"{len({c['user'] for c in chat})} chatters, {len(info['clips'])} viewer clips → {out}")
        return
    info = json.loads((out / "vod.json").read_text(encoding="utf-8"))
    chat = json.loads((out / "chat.json").read_text(encoding="utf-8"))
    picks = spikes(chat, info["length"], a.window, a.lag, top=a.top)
    (out / "chat_spikes.json").write_text(json.dumps(picks, ensure_ascii=False, indent=1), encoding="utf-8")
    for p in picks:
        print(f"{fmt(p['moment'])}  score {p['score']:5.1f}  {p['kind']:5s}  {p['msgs']} msgs/{p['users']} users  "
              f"| {' / '.join(p['sample'])}")
    for c in info["clips"]:
        print(f"CLIP {fmt(c['start'])} +{c['dur']:.0f}s  {c['views']} views  {c['title']}")


if __name__ == "__main__":
    main()
