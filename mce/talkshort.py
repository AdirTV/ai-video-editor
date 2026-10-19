"""Talking-head recording -> vertical short spec (for mce.push / timeline_xml).

You (Claude) choose the takes; this does the editor's handwork:
  * tightens each take on word timings + measured silences: pauses > max_gap and filler words are cut out
  * frames the face (mce.faces) and alternates punch-in levels at every cut, so jump cuts read as
    deliberate "camera changes" (the podcast/stream-clip style), with a slow push on long pieces
  * audio of neighbouring pieces on alternating tracks with short crossfades (jump cuts aren't heard)
  * word-group captions (Remotion "Captions") timed to the new timeline
  * layout "full" (face fills 9:16) or "split" (B-roll on the top 40%, face below, captions on the
    seam); split falls back to full wherever no B-roll covers the moment

Config (JSON):
{
  "source": "/abs/talk.mp4", "transcript": "analysis/transcript.json", "faces": "analysis/faces.json",
  "name": "gta short v1", "out": "short_v1.json",
  "takes": [[12.3, 20.1], [45.0, 51.2, "optional label"]],     # source seconds, in story order
  "layout": "full" | "split",
  "broll": [{"path": "/abs/b.mp4", "in": 3, "out": 6, "at": "06a", "zoom": 1, "fx": 0.5, "audio_db": null}],
                 # at = shot id from the printed shot list ("06a", "06a+0.9"), timeline seconds, or
                 # "word": "phrase" (first time it's said); fills its shot, slowed (>=0.7x) if too short
  "max_gap": 0.3, "fillers": ["um", "uh"], "punch": [100, 120, 140],   # % on top of the base framing
  "captions": {"look": "karaoke" | "stream", "font": "carlito", "size": 84, "max_words": 6,
               "fix": {"gta": "GTA"}, "big": ["pyramids"], "hl": {"GTA": "#FFD84D"}, "mov": "graphics/caps v1.mov"},
                 # karaoke (clip-channel look): white 2-line phrases, upcoming words dimmed, on the seam
                 # over split shots and lower-middle over full-frame ones; stream: 1-line light blue groups
  "split_ratio": 0.4,                        # split layout: top panel = 40% of the height
  # broll "full": true = full-frame cutaway over the face (hide a flub, mic drop, looking away)
  "music": {"path": "/abs/m.mp3", "in": 4.5, "gain_db": -22},
  "vo_lufs": -11.5, "vo_master": true      # mic stream pre-mastered to <source>_vo<N>.wav (default on)
}
  uv run python -m mce.talkshort <config.json>     -> writes the spec + caps_props.json, prints a cut list
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

from .faces import face_at, track
from .timeline_xml import _probe

W, H, FPS = 1080, 1920, 60
DANGLING = {"a", "an", "the", "to", "of", "in", "on", "and", "or", "but", "so", "if", "i", "i'm", "you",
            "your", "my", "with", "from", "for", "can", "will", "be", "is", "that", "this", "where", "when"}
FILLERS = {"um", "uh", "umm", "uhh", "erm", "hmm", "mm", "ah"}


def _norm(w: str) -> str:
    return re.sub(r"[^\w']", "", w.lower())


def load_words(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text())
    segs = data["segments"] if isinstance(data, dict) else data
    out = []
    for s in segs:
        for w in s.get("words", []):
            if "start" in w and "end" in w:
                out.append({"word": w["word"].strip(), "start": float(w["start"]), "end": float(w["end"])})
    return sorted(out, key=lambda w: w["start"])


def pieces(take: tuple[float, float], words: list[dict], max_gap: float, fillers: set[str],
           lead: float = 0.08, tail: float = 0.14) -> list[dict]:
    """Split one take into continuous speech pieces (gaps and fillers removed)."""
    t0, t1 = take
    ws = [w for w in words if t0 - 0.05 <= w["start"] < t1]
    keep = [w for w in ws if _norm(w["word"]) not in fillers]
    groups: list[list[dict]] = []
    for w in keep:
        if groups and w["start"] - groups[-1][-1]["end"] <= max_gap and not any(
                x["start"] > groups[-1][-1]["start"] and x["start"] < w["start"] for x in ws if x not in keep):
            groups[-1].append(w)
        else:
            groups.append([w])
    out = []
    allw = words
    for g in groups:
        i0 = allw.index(g[0])
        i1 = allw.index(g[-1])
        prev_end = allw[i0 - 1]["end"] if i0 else 0
        next_start = allw[i1 + 1]["start"] if i1 + 1 < len(allw) else g[-1]["end"] + 1
        a = max(g[0]["start"] - lead, (prev_end + g[0]["start"]) / 2, t0 - 0.3)
        b = min(g[-1]["end"] + tail, (g[-1]["end"] + next_start) / 2)
        b = min(b, t1 + tail)
        out.append({"in": round(a, 3), "out": round(b, 3), "words": g})
    return out


def silences(src: str, stream: int = 0, db: float = -38, min_len: float = 0.3) -> list[tuple[float, float]]:
    """Real pauses in the voice track (ASR word timings sometimes stretch a word across a pause)."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-map", f"0:a:{stream}", "-af",
                          f"silencedetect=n={db}dB:d={min_len}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", log)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    return list(zip(st, en))


def split_on_silence(ps: list[dict], sil: list[tuple[float, float]], pad: float = 0.06) -> list[dict]:
    """Cut pauses the word timings missed out of each piece (words go to the side holding their middle)."""
    out = []
    for p in ps:
        cur = dict(p)
        for s0, s1 in sil:
            if cur["in"] + 0.15 < s0 and s1 < cur["out"] - 0.15:
                mid = (s0 + s1) / 2
                left = [w for w in cur["words"] if (w["start"] + w["end"]) / 2 < mid]
                right = [w for w in cur["words"] if (w["start"] + w["end"]) / 2 >= mid]
                if not left or not right:
                    continue
                out.append({**cur, "out": round(s0 + pad, 3), "words": left})
                cur = {**cur, "in": round(s1 - pad, 3), "words": right}
        out.append(cur)
    return out


VOICE_CHAIN = (  # clean-up + presence for a talking-head mic, before loudness
    "highpass=f=80,afftdn=nr=10:nf=-62:tn=1,"
    "equalizer=f=300:t=q:w=1:g=-3,equalizer=f=3500:t=q:w=1.2:g=3.5,highshelf=f=9000:g=2,"
    "deesser=i=0.4,acompressor=threshold=-22dB:ratio=2.5:attack=8:release=150:makeup=2")


def master_voice(src: str, stream: int = 0, chain: str = VOICE_CHAIN) -> str:
    """Voice WAV: clean-up chain, then two-pass *linear* loudnorm (-14 LUFS, -2 dBTP) and a true limiter.
    (Single-pass loudnorm pumps the room noise up in pauses; alimiter's default auto-level pushes every
    peak to 0 dBFS — both made the first version sound squashed.)"""
    import hashlib
    tag = hashlib.md5(chain.encode()).hexdigest()[:6]
    out = Path(src).with_name(Path(src).stem + f"_vo{stream}_{tag}.wav")
    if out.exists():
        return str(out)
    base = ["ffmpeg", "-hide_banner", "-y", "-i", src, "-map", f"0:a:{stream}"]
    log = subprocess.run(base + ["-af", chain + ",loudnorm=I=-14:TP=-2:LRA=7:print_format=json", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    m = json.loads(log[log.rindex("{"):log.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-2:LRA=7:linear=true:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}")
    subprocess.run(base + ["-v", "error", "-af", f"{chain},{ln},aresample=48000,"
                           "alimiter=limit=0.79:level=disabled:attack=5:release=50",
                           "-ar", "48000", "-ac", "2", str(out)], check=True)
    return str(out)


def _cover(k: float, x: float, y: float, box: tuple[float, float, float, float]) -> tuple[float, float]:
    """Clamp a 1920x1080 clip at scale k so it still covers box (x0, y0, x1, y1)."""
    hw, hh = 960 * k, 540 * k
    x = min(max(x, box[2] - hw), box[0] + hw)
    y = min(max(y, box[3] - hh), box[1] + hh)
    return x, y


def frame_face(face: tuple[float, float, float], pct: float, target: tuple[float, float],
               box: tuple[float, float, float, float]) -> dict:
    k = pct / 100
    x = target[0] - (face[0] - 960) * k
    y = target[1] - (face[1] - 540) * k
    x, y = _cover(k, x, y, box)
    return {"scale": round(pct, 2), "x": round(x), "y": round(y)}


def captions(cuts: list[dict], cfg: dict) -> list[dict]:
    fix = {k.lower(): v for k, v in cfg.get("fix", {}).items()}
    hl = cfg.get("hl", {})
    mw = cfg.get("max_words", 3)
    maxc = cfg.get("max_chars", 16)
    caps, group = [], []

    def flush():
        if group:
            caps.append({"start": round(group[0][1], 2), "end": round(group[-1][2] + 0.2, 2),
                         "text": " ".join(g[0] for g in group)})
            group.clear()
    for c in cuts:
        for w in c["words"]:
            raw = w["word"]
            txt = fix.get(_norm(raw), raw)
            ts = w["start"] - c["in"] + c["start"]
            te = min(w["end"], c["out"]) - c["in"] + c["start"]
            if group and (len(group) >= mw or len(" ".join(g[0] for g in group) + txt) > maxc
                          or ts - group[-1][2] > 0.25):
                flush()
            if (not group and raw[-1:] in ".,!?" and caps and len(txt) <= 9
                    and ts - caps[-1]["end"] < 0.3 and caps[-1]["start"] >= c["start"]):
                # a short sentence-final word joins the group before it ("steps ahead of you.")
                caps[-1]["text"] += " " + txt
                caps[-1]["end"] = round(te + 0.2, 2)
                continue
            group.append((txt, ts, te))
            if raw[-1:] in ".,!?":
                flush()
        flush()  # never carry a group across a cut
    for a, b in zip(caps, caps[1:]):
        if b["start"] - a["end"] < 0.35:
            a["end"] = b["start"]
        a["end"] = min(a["end"], b["start"])
    for c in caps:
        h = {w: hl[_norm(w).upper()] if _norm(w).upper() in hl else hl.get(_norm(w))
             for w in c["text"].split()}
        h = {k: v for k, v in h.items() if v}
        if h:
            c["hl"] = h
    return caps


def phrases(cuts: list[dict], cfg: dict, breaks: list[float] = ()) -> list[dict]:
    """Karaoke captions: a phrase (up to ~2 lines) is shown whole, each word lights up as it is said.
    Each cap: text, start/end, words [{"t": seconds from cap start}], big = words drawn larger.
    breaks: timeline seconds where the layout changes (seam <-> lower middle) — a phrase never spans one."""
    fix = {k.lower(): v for k, v in cfg.get("fix", {}).items()}
    big = {_norm(w) for w in cfg.get("big", [])}
    mw, maxc = cfg.get("max_words", 6), cfg.get("max_chars", 26)
    caps, group = [], []

    def flush():
        if group:
            t0 = group[0][1]
            caps.append({"start": round(t0, 2), "end": round(group[-1][2] + 0.25, 2),
                         "text": " ".join(g[0] for g in group),
                         "words": [round(g[1] - t0, 2) for g in group]})
            bw = [g[0] for g in group if _norm(g[0]) in big]
            if bw:
                caps[-1]["big"] = bw
            group.clear()
    for c in cuts:
        for w in c["words"]:
            raw = w["word"]
            txt = fix.get(_norm(raw), raw).rstrip(".,")  # the style drops end punctuation
            ts = w["start"] - c["in"] + c["start"]
            te = min(w["end"], c["out"]) - c["in"] + c["start"]
            if group and any(group[0][1] < b <= ts + 0.01 for b in breaks):
                flush()
            if group and (len(group) >= mw or len(" ".join(g[0] for g in group) + txt) > maxc
                          or ts - group[-1][2] > 0.3):
                carry = []
                while len(group) > 2 and _norm(group[-1][0]) in DANGLING:  # never end a phrase on "a"/"the"…
                    carry.insert(0, group.pop())
                flush()
                group.extend(carry)
            group.append((txt, ts, te))
            if raw[-1:] in ".!?," and (len(group) >= 2 or len(txt) >= 4):
                flush()
        flush()
    for a, b in zip(caps, caps[1:]):
        if b["start"] - a["end"] < 0.4:
            a["end"] = b["start"]
        a["end"] = min(a["end"], b["start"])
    return caps


def build(cfg: dict, base: Path) -> tuple[dict, dict, list[str]]:
    rel = lambda p: str(p if Path(p).is_absolute() else base / p)
    src = cfg["source"]
    words = load_words(rel(cfg["transcript"]))
    faces = track(src, out=Path(rel(cfg.get("faces", Path(src).stem + "_faces.json"))))
    fillers = set(cfg.get("fillers", FILLERS))
    split = cfg.get("layout", "full") == "split"
    seam = round(H * cfg.get("split_ratio", 0.4))  # split: picture above the seam, face below (40/60)
    punch = cfg.get("punch", [100, 120, 140])

    # 1. cut list
    cuts, t = [], 0.0
    gap = cfg.get("max_gap", 0.3)
    sil = silences(src, cfg.get("stream", 1) - 1, cfg.get("silence_db", -38), gap)
    for take in cfg["takes"]:
        for p in split_on_silence(pieces((take[0], take[1]), words, gap, fillers), sil):
            p["start"] = round(t, 3)
            p["label"] = take[2] if len(take) > 2 else ""
            t += p["out"] - p["in"]
            cuts.append(p)
    end = round(t, 3)

    # 2. shots: long pieces split on word starts (prefer after punctuation) — picture only, audio runs on
    shot_len = cfg.get("shot_len", 1.8)  # framing changes about this often, even mid-sentence
    shots = []
    for i, c in enumerate(cuts):
        bounds, last, ws = [c["in"]], c["in"], c["words"]
        for k, w in enumerate(ws[1:], 1):
            after_punct = ws[k - 1]["word"][-1:] in ",.!?"
            if w["start"] - last >= (shot_len * 0.7 if after_punct else shot_len) and c["out"] - w["start"] >= 0.8:
                bounds.append(w["start"] - 0.04)
                last = bounds[-1]
        bounds.append(c["out"])
        for sub, (s0, s1) in enumerate(zip(bounds, bounds[1:])):
            shots.append({"id": f"{i + 1:02d}{'abcdefghijklmnop'[sub]}", "cut": i, "in": round(s0, 3),
                          "out": round(s1, 3), "start": round(c["start"] + s0 - c["in"], 3),
                          "label": c["label"] or " ".join(w["word"] for w in ws[:4])})
    by_id = {sh["id"]: sh for sh in shots}

    # 3. b-roll placement. "at": timeline seconds | shot id ("06a") | "06a+0.9"; or "word": "phrase".
    # Without "dur" it fills to the end of its shot (or the next b-roll); a source shorter than that is
    # slowed down to fit (never below "min_speed", default 0.7).
    tl_words = [(w, c["start"] + w["start"] - c["in"]) for c in cuts for w in c["words"]]
    brolls = []
    for b in cfg.get("broll", []):
        at, shot = b.get("at"), None
        if isinstance(at, str):
            sid, _, off = at.partition("+")
            shot = by_id[sid]
            at = shot["start"] + float(off or 0)
        elif at is None and b.get("word"):
            seq = b["word"].lower().split()
            for i in range(len(tl_words)):
                if [_norm(w["word"]) for w, _ in tl_words[i:i + len(seq)]] == [_norm(x) for x in seq]:
                    at = tl_words[i][1]
                    break
        if at is None:
            print("b-roll not placed:", b)
            continue
        brolls.append({**b, "at": round(at, 3), "_shot": shot})
    brolls.sort(key=lambda b: b["at"])
    for j, b in enumerate(brolls):
        nxt = brolls[j + 1]["at"] if j + 1 < len(brolls) else end
        sh = b.pop("_shot")
        room = min(nxt, sh["start"] + sh["out"] - sh["in"] if sh else end) - b["at"]
        dur = b.get("dur", room if sh else min(room, b.get("out", 1e9) - b["in"]))
        src_len = b.get("out", b["in"] + dur) - b["in"]
        speed = max(b.get("min_speed", 0.7), min(1.0, src_len / dur))
        b["dur"], b["speed"] = round(min(dur, src_len / speed), 3), round(speed, 3)

    def covered(t0, t1):
        """b-roll (one clip or several back to back) covers the whole range"""
        t = t0
        for bb in brolls:
            if bb.get("full"):
                continue
            if bb["at"] <= t + 0.05 and bb["at"] + bb["dur"] > t:
                t = bb["at"] + bb["dur"]
        return t >= t1 - 0.05

    # 4. face clips (V1) with alternating punch-ins; audio per cut with crossfades
    files = {"src": {"path": src}}
    afile, astream = "src", cfg.get("stream", 1)
    if cfg.get("vo_master", True):
        # voice pre-mastered once (compressor + loudnorm -14 + limiter -2 dBTP) -> no clipping when gained,
        # and no multi-stream recordings for Premiere to mis-map
        files["vo"] = {"path": master_voice(src, astream - 1, cfg.get("voice_chain", VOICE_CHAIN))}
        afile, astream = "vo", 1
    v_face, v_broll, a_tracks = [], [], [[], []]
    # full: face high enough that captions on the seam (y≈900) sit under the chin on punch-ins
    full_box, full_target = (0, 0, W, H), (540, cfg.get("full_target_y", 620))
    low_box, low_target = (0, seam, W, H), (540, round(seam + (H - seam) * 0.42))
    # full_base > 177.8 (fill) leaves room to lift the face above captions that sit on the seam
    full_base, low_base = cfg.get("full_base", H / 1080 * 100), cfg.get("low_base", 140.0)  # bottom panel: face fills it
    prev = -1
    xf = cfg.get("xfade", 0.04)
    for n, sh in enumerate(shots):
        c = cuts[sh["cut"]]
        d = sh["out"] - sh["in"]
        # wide, mid, wide, tight, mid, tight… never the same framing twice in a row
        lvl = [0, 1, 0, 2, 1, 2][n % 6] % len(punch) if d > 0.5 else 0
        if lvl == prev:
            lvl = (lvl + 1) % len(punch)
        prev = lvl
        low = split and covered(sh["start"], sh["start"] + d)
        face = face_at(faces, c["in"], c["out"])
        box, target, b0 = (low_box, low_target, low_base) if low else (full_box, full_target, full_base)
        pos = frame_face(face, b0 * punch[lvl] / 100, target, box)
        clip = {"file": "src", "start": sh["start"], "in": sh["in"], "out": sh["out"], **pos,
                "name": f"{sh['id']} {sh['label']}"}
        if low:  # bottom panel: static, cropped at the seam so it never spills into the top panel
            over = seam - (pos["y"] - 540 * pos["scale"] / 100)
            if over > 0:
                clip["crop"] = [0, 0, round(over / (pos["scale"] / 100) / 1080 * 100, 2), 0]
        elif d > 1.2:  # gentle push so no shot sits dead still
            z = frame_face(face, pos["scale"] * 1.04, target, box)
            clip["keys"] = [{"t": 0, **pos}, {"t": round(d, 3), **z}]
        v_face.append(clip)
    for i, c in enumerate(cuts):
        a = {"file": afile, "start": max(0, c["start"] - xf), "in": max(0, c["in"] - xf), "out": c["out"] + xf,
             "stream": astream, "name": f"{i + 1:02d} {c['label']}"}
        a["fade_in"] = a["fade_out"] = xf * 2
        a_tracks[i % 2].append(a)
    paths: dict[str, str] = {}
    for b in brolls:
        fid = paths.setdefault(b["path"], f"b{len(paths)}")
        files[fid] = {"path": b["path"]}
        pr = _probe(b["path"])
        top = split and not b.get("full")              # "full": full-frame cutaway (hides the face, e.g. a flub)
        ph = seam if top else H                        # panel height
        k = max(W / pr["width"], ph / pr["height"]) * 100 * b.get("zoom", 1)  # zoom >1 hides letterboxing
        x = 540 + (0.5 - b.get("fx", 0.5)) * (pr["width"] * k / 100 - W)    # fx: horizontal focus 0..1
        y = ph / 2
        src_len = b["dur"] * b["speed"]
        clip = {"file": fid, "start": b["at"], "in": b["in"], "out": round(b["in"] + src_len, 3),
                "scale": round(k, 2), "x": round(x), "y": y, "name": b.get("name", Path(b["path"]).stem)}
        if top:  # top panel: static, cropped at the seam (letterbox bars would cover the face panel)
            over = y + pr["height"] / 2 * k / 100 - seam
            if over > 0:
                clip["crop"] = [0, 0, 0, round(over / (k / 100) / pr["height"] * 100, 2)]
        else:
            clip["keys"] = [{"t": 0, "scale": round(k, 2), "x": round(x), "y": y},
                            {"t": round(src_len, 3), "scale": round(k * 1.06, 2), "x": round(x), "y": y}]
        if b["speed"] != 1:
            clip["speed"] = b["speed"]
        v_broll.append(clip)
        if b.get("audio_db") is not None and pr["audio"]:
            a_tracks.append([{"file": fid, "start": b["at"], "in": b["in"], "out": clip["out"],
                              "gain_db": b["audio_db"], "name": clip["name"]}])

    # 5. captions
    cc = cfg.get("captions", {})
    look = cc.get("look", "stream")
    if look == "karaoke":
        size = cc.get("size", 84)
        full_y = cc.get("full_y", 1300)
        cut_full = [(b["at"], b["at"] + b["dur"]) for b in brolls if b.get("full")]

        def on_split(t):
            return split and covered(t, t + 0.1) and not any(a <= t < z for a, z in cut_full)
        marks = sorted({sh["start"] for sh in shots} | {x for ab in cut_full for x in ab})
        breaks = [m for m in marks if m > 0 and on_split(m + 0.02) != on_split(m - 0.15)]
        caps = phrases(cuts, cc, breaks)
        for cp in caps:  # on the seam over split shots, lower-middle over full-frame ones
            cp["y"] = seam if on_split(cp["start"] + 0.06) else full_y
        props = {"caps": caps, "size": size, "seconds": round(end, 2), "font": cc.get("font", "carlito"),
                 "look": look}
    else:
        caps = captions(cuts, cc)
        size = cc.get("size", 92 if split else 104)
        # one fixed position for the whole short (moving captions read as a glitch): on the seam
        props = {"caps": caps, "top": cc.get("top", round(seam - size * 0.3) if split else 1180),
                 "size": size, "seconds": round(end, 2), "font": cc.get("font", "carlito"), "look": look}
    video = [v_face, v_broll]
    mov = cc.get("mov")
    if mov and Path(rel(mov)).exists():
        files["caps"] = {"path": rel(mov)}
        video.append([{"file": "caps", "start": 0, "in": 0, "out": end, "name": "captions"}])
    audio = a_tracks
    if cfg.get("music"):
        m = cfg["music"]
        files["music"] = {"path": m["path"]}
        audio.append([{"file": "music", "start": 0, "in": m.get("in", 0), "out": m.get("in", 0) + end,
                       "gain_db": m.get("gain_db", -22), "name": "music"}])
    spec = {"name": cfg.get("name", "talk short"), "width": W, "height": H, "fps": FPS, "files": files,
            "video": video, "audio": audio, "markers": cfg.get("markers", [])}
    for k in ("replaces", "vo_lufs", "limit_db", "auto_sfx", "sfx", "duck_music", "music_fit", "transitions"):
        if k in cfg:
            spec[k] = cfg[k]
    if "vo_lufs" in cfg:
        spec["vo_file"] = afile
    report = [f"{c['start']:6.2f}  src {c['in']:7.2f}–{c['out']:7.2f}  {' '.join(w['word'] for w in c['words'])}"
              for c in cuts]
    report += [f"   shot {sh['id']} {sh['start']:6.2f}–{sh['start'] + sh['out'] - sh['in']:6.2f}  {sh['label']}"
               for sh in shots]
    report.append(f"total {end:.2f}s, {len(cuts)} cuts, {len(v_face)} shots, {len(brolls)} b-roll")
    return spec, props, report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    a = ap.parse_args()
    cfgp = Path(a.config).resolve()
    cfg = json.loads(cfgp.read_text())
    spec, props, report = build(cfg, cfgp.parent)
    out = cfgp.with_name(cfg.get("out", cfgp.stem + "_spec.json"))
    out.write_text(json.dumps(spec, ensure_ascii=False, indent=1))
    (cfgp.parent / "caps_props.json").write_text(json.dumps(props, ensure_ascii=False, indent=1))
    print("\n".join(report))
    print("spec:", out, "\ncaptions props:", cfgp.parent / "caps_props.json")


if __name__ == "__main__":
    main()
