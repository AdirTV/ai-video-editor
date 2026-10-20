"""Sound-effect library + automatic placement on a timeline spec.

Library: category folders (whoosh, pop, riser, impact, ding, click, magic, glitch,
minecraft, meme) plus whole packs (e.g. "Jota Pack/"), classified by filename
keywords first, then folder names.

  uv run python -m mce.sfx index [LIB]          scan → LIB/sfx_index.json
  uv run python -m mce.sfx search zombie hurt   find specific sounds
  uv run python -m mce.sfx plan <spec.json>     add sfx tracks to the spec (in place)

Placement rules (plan):
  transitions        → whoosh, its loudest moment on the cut
  clip "pop"         → pop when the clip pops in (and a softer one out)
  clip "sfx": kind   → that kind at the clip start (e.g. impact on "2027")
  spec "sfx": [{"t", "kind", "gain_db"?, "align": "peak"|"start"}]  explicit hits
Every hit lands on the clip's peak unless align="start". Levels are matched so
each kind sits at a fixed loudness under the voiceover.
"""
import argparse
import functools
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from .config import SFX_LIB as LIB
AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aif", ".aiff", ".ogg", ".flac"}

KEYWORDS = {  # order matters: first match wins ("keyboard click" → typing)
    "typing": ["typing", "keyboard", "typewriter", "type writer"],
    "shutter": ["shutter", "camera flurry", "camera snap", "photo snap", "polaroid"],
    "beep": ["beep", "bleep", "blip"],
    "whoosh": ["whoosh", "swoosh", "swish", "woosh", "pass by", "fly by", "flyby", "transition"],
    "pop": ["pop", "bubble", "plop", "boop"],
    "riser": ["riser", "rise", "build up", "buildup", "uplifter", "swell"],
    "impact": ["impact", "boom", "hit", "punch", "slam", "thud", "bass drop", "braam", "drop"],
    "ding": ["ding", "bell", "chime", "notification", "success", "coin", "subscribe"],
    "click": ["click", "button", "switch", "tap", "ui "],
    "magic": ["magic", "sparkle", "shimmer", "twinkle", "poof", "transform", "glitter"],
    "glitch": ["glitch", "static", "error", "distort", "digital"],
}
# Folder names (any level) → kind, used when the filename says nothing.
FOLDERS = {
    "whoosh": "whoosh", "swoosh": "whoosh", "riser": "riser", "swell": "riser", "impact": "impact",
    "cinematic": "impact", "notification": "ding", "chime": "ding", "bell": "ding", "positive": "ding",
    "button": "click", "switch": "click", "game ui": "click", "beep": "beep", "typing": "typing",
    "keyboard": "typing", "camera": "shutter", "hacking": "glitch",
    "sci-fi": "glitch", "sci_fi": "glitch", "minecraft": "minecraft", "funny": "meme",
    "ed edd eddy": "meme", "anime": "meme", "negative": "meme", "pop": "pop", "magic": "magic", "glitch": "glitch",
    "ding": "ding",
}
# Target loudness (dBFS RMS around the peak) per kind; the voiceover sits near -16.
LEVEL = {"typing": -28, "shutter": -25, "beep": -26, "whoosh": -26, "pop": -24, "riser": -27, "impact": -22, "ding": -25, "click": -26, "magic": -25,
         "glitch": -27, "minecraft": -24, "meme": -22, "other": -25}
# Longest sound worth using per kind (seconds); long beds/loops are skipped.
MAX_LEN = {"typing": 3, "shutter": 1.5, "beep": 1.0, "whoosh": 3, "pop": 1.5, "click": 1.5, "ding": 3, "impact": 5, "riser": 8, "magic": 4,
           "glitch": 3, "minecraft": 5, "meme": 6, "other": 6}


def _category(path: Path, lib: Path) -> str:
    """Filename keywords first (most specific), then folder names, else "other"."""
    name = path.stem.lower().replace("_", " ")
    parts = [p.lower() for p in (path.relative_to(lib).parts[:-1] if path.is_relative_to(lib) else ())]
    if any("minecraft" in p for p in parts):
        return "minecraft"  # game sounds ("zombie/hit1") are not generic impacts
    for kind, words in KEYWORDS.items():
        if any(w in name for w in words):
            return kind
    for part in reversed(parts):
        for key, kind in FOLDERS.items():
            if key in part:
                return kind
    return "other"


def _analyze(path: Path) -> dict:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-t", "20", "-i", str(path), "-ac", "1", "-ar", "16000",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    hop = 160  # 10 ms
    n = max(1, len(x) // hop)
    rms = np.sqrt(np.mean(x[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms)
    peak = int(np.argmax(rms))
    around = db[max(0, peak - 5): peak + 6]
    return {"duration": round(len(x) / 16000, 3), "peak": round(peak * hop / 16000, 3),
            "loudness": round(float(np.mean(around)), 1)}


# No single hit may peak above this (dBFS) after gain: loud transients (ice/glass/snowball impacts)
# matched by RMS otherwise clip the mix (Ice Caves shorts hit +3.6 dBTP).
PEAK_CEIL = -7.0
# A sound whose loudest sample is below this is broken/empty (some pack files peak at -59 dBFS): never use
# it — it would need +50 dB, which Premiere can't give (XML levels clamp at +6) and would only lift noise.
SILENT_PEAK = -40.0


@functools.lru_cache(maxsize=None)
def _sample_peak(path: str) -> float:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-t", "20", "-i", path, "-ar", "48000", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.abs(np.frombuffer(raw, np.float32))
    return float(20 * np.log10(x.max() + 1e-9)) if len(x) else -90.0


def _item(args: tuple[str, str]) -> dict | None:
    p, lib = Path(args[0]), Path(args[1])
    try:
        info = _analyze(p)
    except subprocess.CalledProcessError:
        return None
    rel = p.relative_to(lib)
    return {"path": str(p), "kind": _category(p, lib), "tags": " ".join(rel.parts).lower(), **info}


def index(lib: Path = LIB) -> dict:
    from concurrent.futures import ProcessPoolExecutor

    paths = [str(p) for p in sorted(lib.rglob("*"))
             if p.suffix.lower() in AUDIO_EXT and not p.name.startswith(".") and "_generated" not in p.parts]
    with ProcessPoolExecutor() as ex:
        items = [it for it in ex.map(_item, [(p, str(lib)) for p in paths], chunksize=32) if it]
    idx = {"lib": str(lib), "items": items}
    (lib / "sfx_index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    counts: dict[str, int] = {}
    for it in items:
        counts[it["kind"]] = counts.get(it["kind"], 0) + 1
    print(f"indexed {len(items)}:", dict(sorted(counts.items(), key=lambda kv: -kv[1])))
    return idx


STARTER = {  # kind: (filename must contain one of, duration window)
    "whoosh": (["whoosh", "swoosh", "woosh", "swish"], (0.35, 1.6)),
    "pop": (["pop"], (0.08, 0.8)),
    "ding": (["ding", "chime", "notification"], (0.3, 2.0)),
    "impact": (["impact", "boom", "braam", "bass drop"], (0.5, 3.0)),
    "riser": (["riser"], (1.5, 5.0)),
    "magic": (["magic", "sparkle", "shimmer", "twinkle"], (0.5, 3.0)),
    "glitch": (["glitch"], (0.2, 1.5)),
    "click": (["click"], (0.05, 0.5)),
    "typing": (["typing", "keyboard"], (0.5, 3.0)),
    "shutter": (["shutter", "camera flurry", "camera snap"], (0.1, 1.2)),
    "beep": (["beep", "bleep", "blip"], (0.05, 0.6)),
}
AVOID = ["mosquito", "tree", "alarm", "horror", "gun", "scream", "fart", "car ", "door", "water", "punch",
         "body", "blood", "bone", "kick", "loop", "bed", "ambience", "transformer", "vox", "vending",
         "bamboo", "sword", "money", "toaster", "vein", "words", "tree", "wood"]


def starter_kit(lib: Path = LIB, per_kind: int = 8, kinds: list[str] | None = None) -> None:
    """Copy a small, varied, sensibly-named set per kind into LIB/<kind>/ for auditioning."""
    import shutil

    idx = json.loads((lib / "sfx_index.json").read_text())
    for kind, (words, (lo, hi)) in STARTER.items():
        if kinds and kind not in kinds:
            continue
        dest = lib / kind
        dest.mkdir(exist_ok=True)
        pool = [it for it in idx["items"] if it["kind"] == kind and lo <= it["duration"] <= hi
                and -32 < it["loudness"] < -6 and Path(it["path"]).parent.name not in LEVEL
                and any(w in Path(it["path"]).stem.lower() for w in words)
                and not any(a in it["tags"] for a in AVOID)]
        pool.sort(key=lambda it: hashlib.md5(it["path"].encode()).hexdigest())
        picked, packs = [], set()
        for it in pool:  # one per sub-folder first, for variety
            pk = Path(it["path"]).parent
            if pk not in packs:
                picked.append(it)
                packs.add(pk)
            if len(picked) == per_kind:
                break
        for it in pool:
            if len(picked) >= per_kind:
                break
            if it not in picked:
                picked.append(it)
        for it in picked:
            shutil.copy2(it["path"], dest / Path(it["path"]).name)
        print(f"{kind:7s} {len(picked)}  ← from {len(pool)} candidates")
    index(lib)


def search(words: str, lib: Path = LIB, limit: int = 15) -> list[dict]:
    """Find sounds whose path contains all the given words (e.g. "zombie hurt")."""
    idx = json.loads((lib / "sfx_index.json").read_text())
    ws = words.lower().split()
    return [it for it in idx["items"] if all(w in it["tags"] for w in ws)][:limit]


def typing_track(duration: float, lib: Path = LIB, seed: int = 0, rate: float = 11.0) -> dict:
    """ASMR typing for text appearing on screen: single keystrokes from the
    library's typing folder laid one after another at a natural, uneven pace
    (~rate keys/s, varied level) for `duration` seconds. Returns an index-style item."""
    import random
    import wave

    rng = random.Random(seed)
    keys = [p for p in sorted((lib / "typing").glob("*")) if p.suffix.lower() in AUDIO_EXT]
    if not keys:
        raise FileNotFoundError(f"no keystrokes in {lib / 'typing'}")
    sr = 48000
    samples = []
    for k in keys:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(k), "-ac", "1", "-ar", str(sr), "-t", "0.4",
                              "-f", "s16le", "-"], capture_output=True, check=True).stdout
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        if len(x):
            samples.append(x / (np.abs(x).max() + 1e-9))
    out = np.zeros(int((duration + 0.5) * sr), np.float32)
    t = 0.0
    while t < duration:
        x = rng.choice(samples) * rng.uniform(0.55, 1.0)
        i = int(t * sr)
        out[i:i + len(x)] += x[: len(out) - i]
        t += rng.uniform(0.6, 1.4) / rate
    out = out / (np.abs(out).max() + 1e-9) * 0.5
    gen_dir = lib / "_generated"
    gen_dir.mkdir(exist_ok=True)
    path = gen_dir / f"typing_{duration:.2f}s_{seed}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((out * 32767).astype(np.int16).tobytes())
    return {"path": str(path), "kind": "typing", "duration": round(len(out) / sr, 3), "peak": 0.0,
            **{k: v for k, v in _analyze(path).items() if k == "loudness"}}


class _Picker:
    """Rotate through a category so consecutive hits don't repeat one sound."""

    def __init__(self, items: list[dict]):
        self.by_kind: dict[str, list[dict]] = {}
        curated = [it for it in items if Path(it["path"]).parent.name in LEVEL]
        for it in curated or items:
            if it["duration"] <= MAX_LEN.get(it["kind"], 6) and it["loudness"] > -50:
                self.by_kind.setdefault(it["kind"], []).append(it)
        if curated:  # kinds with no curated sounds fall back to the packs
            for it in items:
                if it["kind"] not in self.by_kind and it["duration"] <= MAX_LEN.get(it["kind"], 6):
                    self.by_kind.setdefault(it["kind"], []).append(it)
        # Same order every run, but spread across sub-packs instead of alphabetical runs.
        for pool in self.by_kind.values():
            pool.sort(key=lambda it: hashlib.md5(it["path"].encode()).hexdigest())
        self.n: dict[str, int] = {}

    def __call__(self, kind: str) -> dict | None:
        pool = self.by_kind.get(kind) or (self.by_kind.get("whoosh") if kind == "glitch" else None)
        if not pool:
            return None
        i = self.n.get(kind, 0)
        self.n[kind] = i + 1
        return pool[i % len(pool)]


# Which sound a transition gets (after a pro editor's rules): movement → whoosh,
# quick cuts → a mouse click / camera shutter, glitch → glitch.
TRANSITION_SFX = {
    "Whip": "whoosh", "Zoom Blur": "whoosh", "Pull Motion": "whoosh", "Push": "whoosh", "Spin Motion": "whoosh",
    "Slide": "whoosh", "Fold Motion": "whoosh", "Cross Zoom": "whoosh", "Pop Motion": "pop",
    "Flash": "shutter", "Dip to White": "shutter", "Glitch": "glitch", "Cut": "click",
}


def plan(spec: dict, lib: Path = LIB) -> tuple[dict, list[str]]:
    idx_path = lib / "sfx_index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else index(lib)
    pick = _Picker(idx["items"])
    hits: list[tuple] = []  # (t, kind, gain offset, align, forced file)

    for tr in spec.get("transitions", []):
        if tr.get("track", 0) == 0:  # one whoosh per cut even when V1+V2 both transition
            hits.append((tr["t"], tr.get("sfx") or TRANSITION_SFX.get(tr["name"], "whoosh"), 0, "peak", None))
    for track in spec.get("video", []):
        for c in track:
            if c.get("pop") in ("start", "both"):
                hits.append((c["start"], "pop", 0, "start", None))
            if c.get("pop") in ("end", "both"):
                hits.append((c["start"] + c["out"] - c["in"] - 0.15, "pop", -6, "start", None))
            if c.get("text"):      # text appearing → ASMR typing for as long as it types on
                dur = c.get("text_dur") or min((c["out"] - c["in"]) * 0.8, 1.2)
                hits.append((c["start"], "typing", 0, "start", f"__typing__:{dur:.2f}"))
            if c.get("emphasis"):  # highlighting something → sparkle
                hits.append((c["start"] + c.get("emphasis_at", 0), "magic", 0, "peak", None))
            if c.get("sfx"):
                hits.append((c["start"] + c.get("sfx_at", 0), c["sfx"], 0, c.get("sfx_align", "peak"), None))
    for h in spec.get("sfx", []):
        hits.append((h["t"], h.get("kind", "other"), h.get("gain_db", 0), h.get("align", "peak"), h.get("file")))

    files = spec.setdefault("files", {})
    tracks: list[list[dict]] = [[], []]  # A: whoosh/riser/glitch, B: pops/hits
    report, missing = [], set()
    by_path = {it["path"]: it for it in idx["items"]}
    for t, kind, off, align, forced in sorted(hits, key=lambda h: h[0]):
        if forced and forced.startswith("__typing__:"):
            it = typing_track(float(forced.split(":")[1]), lib, seed=int(t * 100))
        else:
            it = by_path.get(forced) if forced else pick(kind)
            tries = 0
            while it and not forced and _sample_peak(it["path"]) < SILENT_PEAK and tries < 8:
                it, tries = pick(kind), tries + 1   # auto pick landed on an empty file: take the next one
        if not it:
            missing.add(kind)
            continue
        if _sample_peak(it["path"]) < SILENT_PEAK:
            report.append(f"!! {t:6.2f}s  {Path(it['path']).name} is near-silent "
                          f"(peak {_sample_peak(it['path']):.0f} dBFS) — skipped, choose another sound")
            continue
        fid = "sfx_" + hashlib.md5(it["path"].encode()).hexdigest()[:8]
        files[fid] = {"path": it["path"]}
        lead = it["peak"] if align == "peak" else 0.0
        start = max(0.0, t - lead)
        src_in = lead - (t - start)  # trimmed when the peak can't fit before t=0
        gain = round(min(LEVEL[it["kind"]] - it["loudness"] + off, PEAK_CEIL - _sample_peak(it["path"])), 1)
        clip = {"file": fid, "start": round(start, 3), "in": round(src_in, 3), "out": it["duration"],
                "gain_db": gain, "stream": 1, "name": f"SFX {kind}"}
        lane = tracks[0] if kind in ("whoosh", "riser", "glitch") else tracks[1]
        if lane and lane[-1]["start"] + lane[-1]["out"] - lane[-1]["in"] > clip["start"]:
            lane = tracks[1] if lane is tracks[0] else tracks[0]  # avoid overlaps on one track
        lane.append(clip)
        report.append(f"{t:6.2f}s  {kind:7s} {Path(it['path']).name}  ({gain:+.1f} dB)")
    spec["audio"] = [a for a in spec.get("audio", []) if not (a and a[0].get("name", "").startswith("SFX"))]
    spec["audio"] += [lane for lane in tracks if lane]
    for k in sorted(missing):
        report.append(f"!! no '{k}' sounds in the library — add some to {lib / k}")
    return spec, report


def main() -> None:
    p = argparse.ArgumentParser(prog="mce.sfx")
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("index")
    i.add_argument("lib", nargs="?", default=str(LIB))
    st = sub.add_parser("starter")
    st.add_argument("--kinds", help="comma-separated kinds to fill (default: all)")
    se = sub.add_parser("search")
    se.add_argument("words", nargs="+")
    pl = sub.add_parser("plan")
    pl.add_argument("spec")
    pl.add_argument("--lib", default=str(LIB))
    a = p.parse_args()
    if a.cmd == "index":
        index(Path(a.lib))
    elif a.cmd == "starter":
        starter_kit(kinds=a.kinds.split(",") if a.kinds else None)
    elif a.cmd == "search":
        for it in search(" ".join(a.words)):
            print(f"{it['kind']:9s} {it['duration']:5.2f}s  {Path(it['path']).relative_to(LIB)}")
    else:
        spec, report = plan(json.loads(Path(a.spec).read_text()), Path(a.lib))
        Path(a.spec).write_text(json.dumps(spec, ensure_ascii=False, indent=1))
        print("\n".join(report))


if __name__ == "__main__":
    main()
