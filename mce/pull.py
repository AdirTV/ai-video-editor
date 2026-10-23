"""Keep the editor's own Premiere changes between iterations.

push rebuilds a sequence from its spec, so anything changed by hand in Premiere
would be lost. Right after a push the new sequence is exported as XML and saved
as a snapshot (<spec dir>/.mce/<sequence>.json). pull exports the sequence again,
compares it with that snapshot and writes only the differences — the editor's
changes — into the spec:

  trims / moves / track changes / speed   -> start, in, out, speed of the clip
  scale / position / motion keyframes     -> scale, x, y, keys
  volume / volume keyframes               -> gain_db (as a change, so headroom
                                             boosts stay right), gain_keys
  razor cuts                               -> the clip is split in the spec too
  deleted / disabled clips                 -> removed
  clips the editor added                   -> added (new media gets a files key)
  effects added / removed                  -> clip "effects" (numeric params as props)
  video transitions added / removed / longer -> "transitions" / clip "pop"

Clips that push generates (auto_sfx sounds, music_fit / music_playlist /
duck_music music, vo_lufs voice gain) can't be kept as a change to a setting:
when the editor touches one, that whole group is written out as plain clips and
its setting is turned off ("frozen"), so the next push keeps it as it is.

Every applied change is remembered in the spec's "_pulled" list, so pulling
again doesn't undo a later change by Claude; a spec regenerated from scratch
(talkshort) gets the changes again, matched by media and source range.

  uv run python -m mce.pull <spec.json> [--seq NAME] [--dry-run]
  uv run python -m mce.pull <spec.json> --against <old spec.json>   # no snapshot (pushed before this
                                                                    # existed): compare with that spec
push runs pull first (from "replaces", else the spec's own sequence) and stops
when an edit can't be placed.
"""
import argparse
import copy
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlparse

# groups whose clips push generates or rewrites, and the spec settings behind them
GROUP_FLAGS = {"sfx": ("auto_sfx", "sfx"), "music": ("music_playlist", "music_fit", "duck_music"),
               "vo": ("vo_lufs",)}
BUILTIN_FX = {"basic", "audiolevels", "timeremap", "crop", "opacity"}
TIME, PX, SCALE, DB = 1.01, 1.0, 0.3, 0.15  # tolerances (TIME is in frames)


def snapshot_path(spec_path: str | Path, seq: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in " -_." else "_" for ch in seq)
    return Path(spec_path).parent / ".mce" / f"{safe}.json"


# ---------------------------------------------------------------- reading XML

def _rate(el) -> float:
    tb = float(el.findtext("rate/timebase") or 0)
    return tb * 1000 / 1001 if (el.findtext("rate/ntsc") or "").upper() == "TRUE" else tb


def _path(url: str) -> str:
    p = unquote(urlparse(url).path)
    while p.startswith("//"):
        p = p[1:]
    return str(Path(p).resolve())


def _db(lin: float) -> float:
    return round(20 * math.log10(max(lin, 1e-6)), 2)


def parse(xml_text: str) -> dict:
    """xmeml (ours or Premiere's export) -> clips in spec units, plus transitions."""
    seq = ET.fromstring(xml_text).find(".//sequence")
    fps = _rate(seq)
    fmt = seq.find("media/video/format/samplecharacteristics")
    W = float(fmt.findtext("width") or 1920) if fmt is not None else 1920
    H = float(fmt.findtext("height") or 1080) if fmt is not None else 1080
    files: dict[str, dict] = {}
    for f in seq.iter("file"):
        if f.find("pathurl") is not None:
            v = f.find("media/video/samplecharacteristics")
            files[f.get("id")] = {"path": _path(f.findtext("pathurl")),
                                  "w": float(v.findtext("width")) if v is not None and v.findtext("width") else W,
                                  "h": float(v.findtext("height")) if v is not None and v.findtext("height") else H}
    out = {"fps": fps, "width": W, "height": H, "video": [], "audio": [], "transitions": []}
    for kind in ("video", "audio"):
        group = seq.find(f"media/{kind}")
        for ti, tr in enumerate(group.findall("track") if group is not None else []):
            items, clips, trans = list(tr), [], []
            for i, e in enumerate(items):
                if e.tag == "transitionitem":
                    s, en = int(e.findtext("start")), int(e.findtext("end"))
                    align = e.findtext("alignment") or "center"
                    cut = s if align in ("start", "start-black") else en if align in ("end", "end-black") else math.ceil((s + en) / 2)  # odd lengths: the extra frame is before the cut
                    trans.append({"kind": kind, "track": ti, "name": e.findtext("effect/name") or e.findtext("name"),
                                  "s": s, "e": en, "cut": cut, "align": align})
            for i, e in enumerate(items):
                if e.tag != "clipitem":
                    continue
                f = files.get(e.find("file").get("id")) if e.find("file") is not None else None
                if f is None:  # nested sequence / generator: nothing we can rebuild
                    continue
                cf = _rate(e) or fps
                s, en = int(e.findtext("start")), int(e.findtext("end"))
                cin, cout = int(e.findtext("in")), int(e.findtext("out"))
                # a clip that starts/ends inside a transition has start/end -1; its in/out include the handle,
                # and Premiere writes the same handle on both sides: the part after the cut
                tmap = {id(items[j]): t for j, t in zip([j for j, x in enumerate(items) if x.tag == "transitionitem"], trans)}
                before = tmap.get(id(items[i - 1])) if i > 0 else None
                after = tmap.get(id(items[i + 1])) if i + 1 < len(items) else None
                if s < 0 and before:
                    s = round(before["cut"])
                    cin += round((before["e"] - before["cut"]) * cf / fps)
                if en < 0 and after:
                    en = round(after["cut"])
                    cout -= round((after["e"] - after["cut"]) * cf / fps)
                c = {"path": f["path"], "name": e.findtext("name") or "", "track": ti,
                     "enabled": (e.findtext("enabled") or "TRUE").upper() != "FALSE",
                     "speed": 1.0, "fx": {}}
                for flt in e.findall("filter"):
                    ef = flt.find("effect")
                    if ef is None:
                        continue
                    eid = (ef.findtext("effectid") or ef.findtext("name") or "").strip()
                    params = {(p.findtext("parameterid") or p.findtext("name") or ""): p for p in ef.findall("parameter")}
                    if eid == "timeremap" and "speed" in params:
                        c["speed"] = float(params["speed"].findtext("value")) / 100 or 1.0
                    elif eid == "basic":
                        sc, ce = params.get("scale"), params.get("center")
                        nx = lambda h: round(float(h) * f["w"] + W / 2, 1)
                        ny = lambda v: round(float(v) * f["h"] + H / 2, 1)
                        c["scale"] = float(sc.findtext("value")) if sc is not None else 100.0
                        if ce is not None and ce.find("value/horiz") is not None:
                            c["x"], c["y"] = nx(ce.findtext("value/horiz")), ny(ce.findtext("value/vert"))
                        c["_skeys"] = [(int(k.findtext("when")), float(k.findtext("value")))
                                       for k in (sc.findall("keyframe") if sc is not None else [])]
                        c["_ckeys"] = [(int(k.findtext("when")), nx(k.findtext("value/horiz")),
                                        ny(k.findtext("value/vert")))
                                       for k in (ce.findall("keyframe") if ce is not None else [])]
                    elif eid == "audiolevels" and "level" in params:
                        lv = params["level"]
                        c["gain_db"] = _db(float(lv.findtext("value")))
                        c["_gkeys"] = [(int(k.findtext("when")), _db(float(k.findtext("value"))))
                                       for k in lv.findall("keyframe")]
                    elif eid == "crop":
                        c["crop"] = [float(params[k].findtext("value") or 0) if k in params else 0.0
                                     for k in ("left", "right", "top", "bottom")]
                    elif eid not in BUILTIN_FX:
                        props = {}
                        for pid, p in params.items():
                            try:
                                props[p.findtext("name") or pid] = float(p.findtext("value"))
                            except (TypeError, ValueError):
                                pass
                        c["fx"][ef.findtext("name") or eid] = props
                if kind == "video" and "scale" not in c:  # Premiere leaves untouched Basic Motion out
                    c.update(scale=100.0, x=W / 2, y=H / 2)
                sp = c["speed"]
                c["start"] = round(s / fps, 4)
                c["dur"] = round((en - s) / fps, 4)
                c["in"] = round(cin * sp / cf, 4)
                c["out"] = round(c["in"] + c["dur"] * sp, 4)
                if kind == "audio":
                    c["stream"] = int(e.findtext("sourcetrack/trackindex") or 1)
                # keyframes: `when` counts source frames like <in>; spec keys are seconds from the clip start
                rel = lambda w: round((w - cin) / cf, 3)
                if c.get("_skeys") or c.get("_ckeys"):
                    sk, ck = dict(c.pop("_skeys")), {w: (x, y) for w, x, y in c.pop("_ckeys")}
                    c["keys"] = [{"t": rel(w), "scale": sk.get(w, c["scale"]),
                                  "x": ck.get(w, (c.get("x"), c.get("y")))[0], "y": ck.get(w, (c.get("x"), c.get("y")))[1]}
                                 for w in sorted(set(sk) | set(ck))]
                c.pop("_skeys", None), c.pop("_ckeys", None)
                if c.get("_gkeys"):
                    c["gain_keys"] = [[rel(w), d] for w, d in c["_gkeys"]]
                c.pop("_gkeys", None)
                clips.append(c)
            out[kind].append(clips)
            for t in trans:
                out["transitions"].append({**t, "t": round(t["cut"] / fps, 4), "dur": round((t["e"] - t["s"]) / fps, 4)})
    return out


# ---------------------------------------------------------------- snapshots

def make_snapshot(built: dict, parsed: dict, groups: dict[str, str], seq: str) -> dict:
    """Pair every clip Premiere exported with the spec clip that made it.

    built: the spec as it went into build() — after push's own steps, before headroom
    boosts; every clip carries an "id". groups: id -> "sfx" | "music" | "vo" for clips
    push generated or rewrote."""
    fps = parsed["fps"]
    snap = {"sequence": seq, "fps": fps, "width": parsed["width"], "height": parsed["height"],
            "files": {k: str(Path(v["path"]).resolve()) for k, v in built.get("files", {}).items()},
            "video": [], "audio": [], "transitions": parsed["transitions"], "spec_transitions":
            copy.deepcopy(built.get("transitions", [])), "flags": {k: built[k] for g in GROUP_FLAGS.values()
                                                                   for k in g if k in built}}
    for kind in ("video", "audio"):
        for ti, clips in enumerate(parsed[kind]):
            spec_clips = sorted(built.get(kind, [])[ti], key=lambda c: c["start"]) if ti < len(built.get(kind, [])) else []
            free = list(spec_clips)
            row = []
            files = built.get("files", {})
            named = lambda s: (s.get("name") or Path(files.get(s["file"], {}).get("path", "")).name)
            for c in sorted(clips, key=lambda c: c["start"]):
                # same order as build() wrote them; confirm by name and start time
                m = next((s for s in free if named(s) == c["name"] and abs(s["start"] - c["start"]) * fps <= 1.5), None)
                if m is None and len(clips) == len(spec_clips) and free and named(free[0]) == c["name"]:
                    m = free[0]
                if m is not None:
                    free.remove(m)
                row.append({**c, "id": m.get("id") if m else None, "group": groups.get(m.get("id")) if m else None,
                            "spec": copy.deepcopy(m) if m else None})
            snap[kind].append(row)
    return snap


# ---------------------------------------------------------------- comparing

def _overlap(a: dict, b: dict) -> float:
    return min(a["out"], b["out"]) - max(a["in"], b["in"])


def _match(base: list[dict], live: list[dict], fps: float) -> tuple[dict, list]:
    """live clip -> base clip (same media, overlapping source). Several live clips on one
    base clip = razor cuts. Returns ({base idx: [live idx...]}, unmatched live idx)."""
    pairs = []
    for li, l in enumerate(live):
        best = None
        for bi, b in enumerate(base):
            if b["path"] != l["path"] or b.get("stream") != l.get("stream"):
                continue
            ov = _overlap(b, l)
            if ov <= 0 and not (b["out"] - b["in"] <= 0 or abs(b["start"] - l["start"]) < 0.5):
                continue
            score = (ov > 0, b["track"] == l["track"], -abs(b["start"] - l["start"]), ov)
            if best is None or score > best[0]:
                best = (score, bi)
        if best:
            pairs.append((best[1], li))
    by_base: dict[int, list[int]] = {}
    for bi, li in pairs:
        by_base.setdefault(bi, []).append(li)
    # the piece that kept the most of the original is "the" clip; the rest are new pieces
    for bi, lis in by_base.items():
        lis.sort(key=lambda li: -_overlap(base[bi], live[li]))
    matched = {li for lis in by_base.values() for li in lis}
    return by_base, [li for li in range(len(live)) if li not in matched]


def _same_keys(a, b, tol) -> bool:
    a, b = a or [], b or []
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        xs = x.values() if isinstance(x, dict) else x
        ys = y.values() if isinstance(y, dict) else y
        if any(abs((p or 0) - (q or 0)) > tol for p, q in zip(xs, ys)):
            return False
    return True


def changes(b: dict, l: dict, fps: float) -> dict:
    """Fields the editor changed on one clip: {"time", "track", "motion", "gain", "fx+", "fx-"}."""
    ch = {}
    f = 1 / fps
    if any(abs(b[k] - l[k]) > TIME * f for k in ("start", "in", "out")) or abs(b["speed"] - l["speed"]) > 1e-3:
        ch["time"] = True
    if b["track"] != l["track"]:
        ch["track"] = True
    if "scale" in b or "scale" in l:
        if (abs(b.get("scale", 100) - l.get("scale", 100)) > SCALE or abs((b.get("x") or 0) - (l.get("x") or 0)) > PX
                or abs((b.get("y") or 0) - (l.get("y") or 0)) > PX
                or not _same_keys([{k: d[k] for k in ("t", "scale", "x", "y")} for d in b.get("keys", [])],
                                  [{k: d[k] for k in ("t", "scale", "x", "y")} for d in l.get("keys", [])], PX)):
            ch["motion"] = True
    if "gain_db" in b or "gain_db" in l:
        # with keyframes Premiere's static level is just the first key: compare the keys
        if b.get("gain_keys") or l.get("gain_keys"):
            if not _same_keys(b.get("gain_keys"), l.get("gain_keys"), DB):
                ch["gain"] = True
        elif abs(b.get("gain_db", 0) - l.get("gain_db", 0)) > DB:
            ch["gain"] = True
    if (b.get("crop") or [0] * 4) != (l.get("crop") or [0] * 4):
        ch["crop"] = True
    added = [n for n in l["fx"] if n not in b["fx"]]
    removed = [n for n in b["fx"] if n not in l["fx"]]
    retuned = [n for n in l["fx"] if n in b["fx"] and b["fx"][n] is not None and l["fx"][n] != b["fx"][n]]
    if added or retuned:
        ch["fx+"] = added + retuned
    if removed:
        ch["fx-"] = removed
    if not l["enabled"]:
        ch["disabled"] = True
    return ch


# ---------------------------------------------------------------- merging

class Merge:
    def __init__(self, spec: dict, snap: dict, live: dict):
        self.spec, self.snap, self.live = spec, snap, live
        self.fps = snap["fps"]
        self.done = set(spec.get("_pulled", []))
        self.applied: list[str] = []      # ledger keys added this pull
        self.report: list[str] = []
        self.unplaced: list[str] = []
        self.files = spec.setdefault("files", {})
        self.track_map: dict[tuple[str, int], int] = {}

    # -- helpers
    def key(self, *parts) -> str:
        return "|".join(str(p) for p in (self.snap["sequence"], *parts))

    def once(self, k: str) -> bool:
        if k in self.done:
            return False
        self.done.add(k)
        self.applied.append(k)
        return True

    def file_key(self, path: str) -> str:
        for k, p in self.snap["files"].items():
            if p == path and "+" in k and k.rsplit("+", 1)[0] in self.files:
                return k.rsplit("+", 1)[0]  # headroom copy -> the original (push makes the copy again)
        for k, v in self.files.items():
            if str(Path(v["path"]).resolve()) == path:
                return k
        for k, p in self.snap["files"].items():
            if p == path and k not in self.files:
                self.files[k] = {"path": p}
                return k
        stem = "".join(ch if ch.isalnum() else "_" for ch in Path(path).stem.lower())[:24] or "media"
        k, n = stem, 2
        while k in self.files:
            k, n = f"{stem}_{n}", n + 1
        self.files[k] = {"path": path}
        return k

    def boost(self, path: str) -> float:
        import re
        for k, p in self.snap["files"].items():
            m = re.search(r"\+(\d+)dB$", k)
            if p == path and m:
                return float(m.group(1))
        return 0.0

    def label(self, kind: str, c: dict) -> str:
        return f"{'V' if kind == 'video' else 'A'}{c['track'] + 1} \"{c.get('name') or Path(c['path']).name}\" @ {c['start']:.2f}s"

    def all_clips(self, kind: str):
        for ti, tr in enumerate(self.spec.get(kind, [])):
            for c in tr:
                yield ti, c

    def find(self, kind: str, b: dict) -> tuple[int, dict] | None:
        """The spec clip that produced snapshot clip b: by id, else by media + source range."""
        if b.get("id"):
            for ti, c in self.all_clips(kind):
                if c.get("id") == b["id"]:
                    return ti, c
        s = b.get("spec")
        if not s:
            return None
        best = None
        for ti, c in self.all_clips(kind):
            if c.get("file") != s.get("file") or c.get("stream", 1) != s.get("stream", 1):
                continue
            ov = min(c["out"], s["out"]) - max(c["in"], s["in"])
            if ov <= 0 and abs(c["start"] - s["start"]) > 0.5:
                continue
            score = (ov > 0, ti == b["track"], -abs(c["start"] - s["start"]), ov)
            if best is None or score > best[0]:
                best = (score, ti, c)
        return (best[1], best[2]) if best else None

    def track_for(self, kind: str, live_track: int) -> int:
        """Spec track index for a live track (push's own steps can add/drop audio tracks)."""
        k = (kind, live_track)
        if k in self.track_map:
            return self.track_map[k]
        votes: dict[int, int] = {}
        for b in self.snap[kind][live_track] if live_track < len(self.snap[kind]) else []:
            hit = self.find(kind, b) if not b.get("group") else None
            if hit:
                votes[hit[0]] = votes.get(hit[0], 0) + 1
        tracks = self.spec.setdefault(kind, [])
        if votes:
            idx = max(votes, key=votes.get)
        elif kind == "video" and live_track < len(tracks):
            idx = live_track
        else:
            tracks.append([])
            idx = len(tracks) - 1
        self.track_map[k] = idx
        return idx

    def put(self, kind: str, track: int, clip: dict) -> None:
        tracks = self.spec.setdefault(kind, [])
        while len(tracks) <= track:
            tracks.append([])
        tracks[track].append(clip)

    def remove(self, kind: str, clip: dict) -> None:
        for tr in self.spec.get(kind, []):
            if any(c is clip for c in tr):
                tr[:] = [c for c in tr if c is not clip]

    def new_id(self) -> str:
        ids = {c.get("id") for k in ("video", "audio") for _, c in self.all_clips(k)}
        n = len(ids) + 1
        while f"c{n}" in ids:
            n += 1
        return f"c{n}"

    # -- applying one clip's changes onto a spec clip
    def apply(self, target: dict, b: dict, l: dict, ch: dict) -> list[str]:
        what = []
        s = b.get("spec") or {}
        if ch.get("time"):
            d_in = l["in"] - target.get("in", l["in"])
            sp = l["speed"]
            # keyframes are stored from the clip start; Premiere anchors them to the source
            if abs(d_in) > 1e-6 and not ch.get("motion") and target.get("keys"):
                target["keys"] = [{**k, "t": round(k["t"] - d_in / sp, 3)} for k in target["keys"]]
            if abs(d_in) > 1e-6 and not ch.get("gain") and target.get("gain_keys"):
                target["gain_keys"] = [[round(t - d_in / sp, 3), d] for t, d in target["gain_keys"]]
            if not ch.get("gain") and l.get("gain_keys") and (target.get("fade_in") or target.get("fade_out")):
                # fades follow the clip's ends in the spec, but Premiere left the keyframes where they were
                boost = self.boost(l["path"])
                target["gain_keys"] = [[t, round(d + boost, 2)] for t, d in l["gain_keys"]]
                target.pop("fade_in", None), target.pop("fade_out", None)
                what.append("volume keyframes stay where Premiere has them")
            target.update(start=l["start"], **{"in": l["in"]}, out=l["out"])
            if abs(sp - 1) > 1e-3:
                target["speed"] = sp
            else:
                target.pop("speed", None)
            what.append(f"timing {b['start']:.2f}–{b['start'] + b['dur']:.2f} → {l['start']:.2f}–{l['start'] + l['dur']:.2f}"
                        + (f" (source {l['in']:.2f}–{l['out']:.2f})" if abs(l["in"] - b["in"]) > 1e-3 else "")
                        + (f", speed {sp:g}" if abs(sp - b["speed"]) > 1e-3 else ""))
        if ch.get("motion"):
            for k in ("scale", "x", "y"):
                if l.get(k) is not None:
                    target[k] = round(l[k], 2)
            if l.get("keys"):
                target["keys"] = l["keys"]
            else:
                target.pop("keys", None)
            what.append(f"scale {l.get('scale', 100):g} at ({l.get('x')}, {l.get('y')})"
                        + (f", {len(l['keys'])} keyframes" if l.get("keys") else ""))
        if ch.get("crop"):
            target["crop"] = l["crop"]
            what.append(f"crop {l['crop']}")
        if ch.get("gain"):
            # Premiere's numbers are relative to a headroom pre-boosted copy ("<file>+6dB"); the spec's aren't
            boost = self.boost(l["path"])
            if l.get("gain_keys"):
                target["gain_keys"] = [[t, round(d + boost, 2)] for t, d in l["gain_keys"]]
                target["gain_db"] = round(max(d for _, d in l["gain_keys"]) + boost, 2)
                for k in ("fade_in", "fade_out"):
                    target.pop(k, None)
                what.append(f"volume keyframes ({len(l['gain_keys'])})")
            else:
                delta = l.get("gain_db", 0) - (b.get("gain_db", 0) if not b.get("gain_keys") else
                                               max(d for _, d in b["gain_keys"]))
                target["gain_db"] = round(target.get("gain_db", 0) + delta, 2)
                for k in ("gain_keys", "fade_in", "fade_out"):
                    target.pop(k, None)
                what.append(f"volume {delta:+.1f} dB")
        if ch.get("fx+"):
            fx = target.setdefault("effects", [])
            for n in ch["fx+"]:
                props = {k: v for k, v in l["fx"][n].items()}
                fx[:] = [e for e in fx if e["name"] != n] + [{"name": n, "props": props} if props else {"name": n}]
            what.append("effect " + ", ".join(ch["fx+"]))
        if ch.get("fx-"):
            if target.get("effects"):
                target["effects"] = [e for e in target["effects"] if e["name"] not in ch["fx-"]]
            what.append("removed effect " + ", ".join(ch["fx-"]))
        return what

    def clip_from_live(self, kind: str, l: dict, like: dict | None = None) -> dict:
        c = copy.deepcopy(like) if like else {}
        c.update({"file": self.file_key(l["path"]), "start": l["start"], "in": l["in"], "out": l["out"]})
        if like is None:
            c["name"] = l.get("name") or Path(l["path"]).stem
            if kind == "audio":
                c["stream"] = l.get("stream", 1)
                c["gain_db"] = l.get("gain_db", 0)
                if l.get("gain_keys"):
                    c["gain_keys"] = l["gain_keys"]
            else:
                for k in ("scale", "x", "y", "keys", "crop"):
                    if l.get(k) is not None:
                        c[k] = l[k]
            if l["fx"]:
                c["effects"] = [{"name": n, "props": p} if p else {"name": n} for n, p in l["fx"].items()]
        if abs(l["speed"] - 1) > 1e-3:
            c["speed"] = l["speed"]
        c["id"] = self.new_id()
        return c

    # -- the whole merge
    def run(self) -> None:
        live, snap = self.live, self.snap
        frozen: set[str] = set()
        plan = []  # (kind, b, [live clips])
        added = []
        for kind in ("video", "audio"):
            base = [b for tr in snap[kind] for b in tr]
            lv = [c for tr in live[kind] for c in tr]
            by_base, extra = _match(base, lv, self.fps)
            for bi, b in enumerate(base):
                ls = [lv[i] for i in by_base.get(bi, [])]
                plan.append((kind, b, ls))
                if b.get("group") == "vo":  # vo_lufs only sets the volume: trims and moves are fine
                    touched = any(changes(b, l, self.fps).get("gain") for l in ls)
                else:
                    touched = not ls or len(ls) > 1 or any(changes(b, l, self.fps) for l in ls)
                if touched and b.get("group"):
                    frozen.add(b["group"])
            added += [(kind, lv[i]) for i in extra]

        for g in sorted(frozen):
            if self.once(self.key("freeze", g)):
                flags = [f for f in GROUP_FLAGS[g] if self.spec.pop(f, None) is not None]
                n = sum(len(ls) for k, b, ls in plan if b.get("group") == g)
                self.report.append(f"froze {g}: you edited a clip push generates, so {', '.join(flags) or 'its setting'} "
                                   f"is off and its {n} clips are now plain clips, as they are in Premiere")
        for kind, b, ls in plan:
            bkey = b.get("id") or f"{kind}{b['track']}:{round(b['start'] * self.fps)}:{Path(b['path']).name}"
            if b.get("group") in frozen:
                self.materialize(kind, b, ls, bkey)
                continue
            if b.get("group") and b["group"] != "vo" and not ls:
                continue
            hit = self.find(kind, b)
            if not ls or all(not l["enabled"] for l in ls):
                if self.once(self.key(bkey, "del")):
                    if hit:
                        self.remove(kind, hit[1])
                        self.report.append(f"removed {self.label(kind, b)}"
                                           + (" (disabled)" if ls else ""))
                continue
            first, rest = ls[0], ls[1:]
            ch = changes(b, first, self.fps)
            if ch:
                k = self.key(bkey, "set", json.dumps({x: first.get(x) for x in
                                                      ("start", "in", "out", "speed", "track", "scale", "x", "y",
                                                       "keys", "gain_db", "gain_keys", "crop", "fx")}, sort_keys=True))
                if self.once(k):
                    if not hit:
                        self.unplaced.append(f"{self.label(kind, b)}: you changed it, but the spec no longer has it")
                    else:
                        ti, target = hit
                        what = self.apply(target, b, first, ch)
                        if ch.get("track"):
                            nt = self.track_for(kind, first["track"])
                            if nt != ti:
                                self.remove(kind, target)
                                self.put(kind, nt, target)
                                what.append(f"moved to {'V' if kind == 'video' else 'A'}{first['track'] + 1}")
                        if what:
                            self.report.append(f"{self.label(kind, b)}: " + "; ".join(what))
            for l in rest:
                if not l["enabled"]:
                    continue
                if self.once(self.key(bkey, "split", round(l["start"] * self.fps), round(l["in"] * self.fps))):
                    if not hit:
                        self.unplaced.append(f"{self.label(kind, b)}: you cut it, but the spec no longer has it")
                        continue
                    piece = self.clip_from_live(kind, l, like=hit[1])
                    self.apply(piece, b, l, {**changes(b, l, self.fps), "time": True})
                    self.put(kind, self.track_for(kind, l["track"]) if l["track"] != b["track"] else hit[0], piece)
                    self.report.append(f"{self.label(kind, b)}: cut — new piece {l['start']:.2f}–{l['start'] + l['dur']:.2f}")
        for kind, l in added:
            if not l["enabled"]:
                continue
            if self.once(self.key("add", kind, l["track"], round(l["start"] * self.fps), Path(l["path"]).name,
                                  round(l["in"] * self.fps))):
                self.put(kind, self.track_for(kind, l["track"]), self.clip_from_live(kind, l))
                self.report.append(f"added {self.label(kind, l)} (source {l['in']:.2f}–{l['out']:.2f})")
        self.transitions()
        self.spec["_pulled"] = sorted(self.done)

    def materialize(self, kind: str, b: dict, ls: list[dict], bkey: str) -> None:
        """A clip of a frozen group: write what's in Premiere as a plain spec clip."""
        if not self.once(self.key(bkey, "frozen")):
            return
        hit = self.find(kind, b) if b.get("id") and not str(b["id"]).startswith("auto-") else None
        if hit:
            self.remove(kind, hit[1])
        for l in ls:
            if not l["enabled"]:
                continue
            c = copy.deepcopy(b["spec"]) if b.get("spec") else self.clip_from_live(kind, l)
            c.pop("id", None)
            c["file"] = c.get("file") if c.get("file") in self.files else self.file_key(l["path"])
            if c["file"] not in self.files and c["file"] in self.snap["files"]:
                self.files[c["file"]] = {"path": self.snap["files"][c["file"]]}
            self.apply(c, b, l, {**changes(b, l, self.fps), "time": True})
            c["id"] = self.new_id()
            self.put(kind, self.track_for(kind, l["track"]), c)

    def transitions(self) -> None:
        fps = self.fps
        near = lambda a, b: a["kind"] == b["kind"] and a["track"] == b["track"] and abs(a["t"] - b["t"]) * fps <= 2
        base, live = self.snap["transitions"], self.live["transitions"]
        spec_tr = self.spec.setdefault("transitions", [])
        for t in base:
            m = next((x for x in live if near(t, x)), None)
            if m is None:
                if self.once(self.key("tr-", t["kind"], t["track"], round(t["t"] * fps))):
                    if self.drop_transition(t):
                        self.report.append(f"removed transition {t['name']} @ {t['t']:.2f}s")
            elif abs(m["dur"] - t["dur"]) * fps > 1 and t["kind"] == "video":
                if self.once(self.key("tr~", t["track"], round(t["t"] * fps), round(m["dur"] * fps))):
                    st = next((x for x in spec_tr if x.get("track", 0) == t["track"] and abs(x["t"] - t["t"]) * fps <= 2), None)
                    if st:
                        st["dur"] = m["dur"]
                        self.report.append(f"transition {t['name']} @ {t['t']:.2f}s → {m['dur']:.2f}s long")
                    else:
                        self.unplaced.append(f"transition {t['name']} @ {t['t']:.2f}s: you changed its length "
                                             f"to {m['dur']:.2f}s, but the spec makes it as a clip pop")
        for m in live:
            if any(near(t, m) for t in base):
                continue
            if self.once(self.key("tr+", m["kind"], m["track"], round(m["t"] * fps), m["name"])):
                if m["kind"] == "video":
                    spec_tr.append({"name": m["name"], "track": m["track"], "t": m["t"], "dur": m["dur"]})
                    self.report.append(f"added transition {m['name']} @ {m['t']:.2f}s (V{m['track'] + 1})")
                else:
                    self.unplaced.append(f"audio transition {m['name']} @ {m['t']:.2f}s (A{m['track'] + 1}): "
                                         "the spec can't hold audio transitions — use fade_in/fade_out")
        if not spec_tr:
            self.spec.pop("transitions", None)

    def drop_transition(self, t: dict) -> bool:
        fps = self.fps
        tr = self.spec.get("transitions", [])
        for x in tr:
            if t["kind"] == "video" and x.get("track", 0) == t["track"] and abs(x["t"] - t["t"]) * fps <= 2:
                tr.remove(x)
                return True
        for _, c in self.all_clips(t["kind"]):  # a Pop Motion that push put on a clip edge
            if not c.get("pop"):
                continue
            end = c["start"] + (c["out"] - c["in"]) / (c.get("speed") or 1)
            side = "start" if abs(c["start"] - t["t"]) * fps <= 16 else "end" if abs(end - t["t"]) * fps <= 16 else None
            if side:
                left = {"both": "end" if side == "start" else "start"}.get(c["pop"])
                if left:
                    c["pop"] = left
                else:
                    c.pop("pop")
                return True
        return False


# ---------------------------------------------------------------- entry points

def export_live(client, seq: str, dest: Path) -> str:
    client.call("set_active_sequence", {"sequence_id": seq})
    active = json.loads(client.call("get_active_sequence", {"clip_limit": 1}))
    active = active.get("data", active).get("name")
    if active != seq:
        raise SystemExit(f"couldn't open sequence {seq!r} (active: {active!r})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.unlink(missing_ok=True)
    import time
    t0 = time.time()
    client.call("export_as_fcp_xml", {"output_path": str(dest)})
    for _ in range(100):  # Premiere can still be writing when the call returns
        if dest.exists():
            text = dest.read_text(encoding="utf-8", errors="replace")
            if text.rstrip().endswith("</xmeml>"):
                # effects XML can't hold get a "not translated" report next to the file; we read those from
                # Premiere directly, so the reports are just clutter
                for rep in dest.parent.glob("FCP Translation Results*.txt"):
                    if rep.stat().st_mtime >= t0 - 2:
                        rep.unlink(missing_ok=True)
                return text
        time.sleep(0.1)
    raise SystemExit(f"Premiere didn't export {seq!r} as XML")


BASE_COMPONENTS = {"Opacity", "Motion", "Volume", "Channel Volume", "Panner", "Time Remapping", "Vector Motion"}


def read_live(client, seq: str, dest: Path) -> dict:
    """The sequence as it is in Premiere. Effects come from Premiere itself: its XML export
    silently leaves out anything it can't translate (Lumetri, Film Impact, most plug-ins)."""
    live = parse(export_live(client, seq, dest))
    fps = live["fps"]
    at = {(k, c["track"], round(c["start"] * fps)): c for k in ("video", "audio") for tr in live[k] for c in tr}
    offset = 0
    while offset is not None:
        d = json.loads(client.call("get_full_sequence_info", {"sequence_id": seq, "clip_limit": 200,
                                                              "clip_offset": offset}))
        d = d.get("data", d)
        for kind, key in (("video", "videoTracks"), ("audio", "audioTracks")):
            for tr in d.get(key, []):
                for cl in tr.get("clips", []):
                    c = at.get((kind, tr.get("index", 0), round(cl["startSeconds"] * fps)))
                    if c is None or cl.get("effectsTruncated"):
                        continue
                    fx = {}
                    for name in cl.get("effects", []):
                        if name in BASE_COMPONENTS:
                            continue
                        fx[name] = c["fx"].get(name) or _effect_props(client, cl["nodeId"], name)
                    c["fx"] = fx
        offset = (d.get("pagination") or {}).get("nextOffset")
    return live


def _effect_props(client, node: str, name: str) -> dict:
    try:
        d = json.loads(client.call("get_effect_properties", {"node_id": node, "effect_name": name}))
    except json.JSONDecodeError:
        return {}
    d = d.get("data", d)
    return {p["displayName"]: p["value"] for p in d.get("properties", [])
            if p.get("displayName") and not p["displayName"].startswith("_") and p["displayName"] != "Error occurred"
            and isinstance(p.get("value"), (int, float)) and not isinstance(p.get("value"), bool)}


def snapshot_from_spec(spec_path: str) -> dict:
    """No snapshot (pushed before snapshots existed): rebuild what push would have built."""
    from .push import assign_ids, prepare
    from .timeline_xml import build
    spec = json.loads(Path(spec_path).read_text())
    assign_ids(spec)
    built, groups = prepare(spec, quiet=True)
    pre = copy.deepcopy(built)
    snap = make_snapshot(pre, parse(build(built)), groups, spec["name"])
    # what push adds after importing isn't in our XML: effects (settings unknown -> None), transitions, pops
    for kind in ("video", "audio"):
        for tr in snap[kind]:
            for c in tr:
                sc = c.get("spec") or {}
                c["fx"] = {e["name"]: None for e in sc.get("effects", [])}
                if kind == "audio" and pre.get("limit_db") is not None:
                    c["fx"]["Hard Limiter"] = None
                if sc.get("pop"):
                    end = sc["start"] + (sc["out"] - sc["in"]) / (sc.get("speed") or 1)
                    for side, t in (("start", sc["start"]), ("end", end)):
                        if sc["pop"] in (side, "both"):
                            snap["transitions"].append({"kind": "video", "track": c["track"], "name": "Pop Motion",
                                                        "t": t, "dur": 0.25})
    for t in pre.get("transitions", []):
        snap["transitions"].append({"kind": "video", "track": t.get("track", 0), "name": t["name"], "t": t["t"],
                                    "dur": t.get("dur", 0.25)})
    return snap


def pull(spec_path: str, seq: str | None = None, against: str | None = None, dry: bool = False,
         client=None, quiet: bool = False) -> tuple[list[str], list[str]] | None:
    """Merge the editor's changes in `seq` into the spec. Returns (report, unplaced),
    or None when there's nothing to compare against."""
    spec = json.loads(Path(spec_path).read_text())
    own = client is None
    if own:
        from .premiere import Client
        client = Client()
    try:
        if seq is None:
            seqs = json.loads(client.call("list_sequences", {}))
            names = {q.get("name") for q in (seqs.get("data", seqs) if isinstance(seqs, dict) else seqs)}
            seq = next((s for s in (spec.get("name"), spec.get("replaces")) if s in names), None)
            if seq is None:
                return None
        snap_file = snapshot_path(spec_path, seq)
        if against:
            snap = snapshot_from_spec(against)
        elif snap_file.exists():
            snap = json.loads(snap_file.read_text())
        else:
            old = next((p for p in sorted(Path(spec_path).parent.glob("*.json"))
                        if _spec_named(p, seq)), None)
            if old is None:
                if not quiet:
                    print(f"⚠️ no snapshot of {seq!r} and no spec named that next to {Path(spec_path).name} — "
                          "can't tell your Premiere changes apart; nothing pulled")
                return None
            print(f"⚠️ no snapshot of {seq!r} (pushed before pull existed) — comparing with {old.name}; "
                  "check the list below")
            snap = snapshot_from_spec(str(old))
        live = read_live(client, seq, snap_file.with_suffix(".live.xml"))
    finally:
        if own:
            client.close()
    m = Merge(spec, snap, live)
    m.run()
    if m.applied and not dry:
        backup = Path(spec_path).with_suffix(".prepull.json")
        backup.write_text(Path(spec_path).read_text())
        Path(spec_path).write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    if not quiet or m.report or m.unplaced:
        head = f"Your changes in {seq!r}" + (" (dry run)" if dry else "") + ":"
        print("\n  ".join([head] + (m.report or ["none"])))
        if m.unplaced:
            print("\n  ".join(["⚠️ couldn't place:"] + m.unplaced))
    return m.report, m.unplaced


def _spec_named(p: Path, name: str) -> bool:
    try:
        d = json.loads(p.read_text())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(d, dict) and d.get("name") == name and "video" in d


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--seq", help="sequence to read (default: the spec's own, else its \"replaces\")")
    ap.add_argument("--against", help="compare with this spec instead of the push snapshot")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    r = pull(a.spec, a.seq, a.against, a.dry_run)
    if r is None:
        print("nothing to pull")
