"""Merge audio, transcript and vision signals into one readable timeline."""
import numpy as np

from .i18n import t
from .sheets import fmt

CLIP_WORDS = ("קליפ", "קליפּ", "clip")  # spoken marker the creator says after a good moment (any language)
HYPE_WORDS = ("וואו", "וואי", "לא לא", "מה ", "אחי", "יאללה", "אוי", "וואלה", "איזה", "פאק", "שיט", "רוץ", "הצילו",
              "no way", "oh my god", "omg", "let's go", "lets go", "bro", "dude", "wow", "what the", "run", "help",
              "no no", "yes!", "insane", "crazy", "holy")

ROW = 10  # seconds per timeline row


def _runs(flags: list[bool], ts: list[float], min_len: float) -> list[tuple[float, float]]:
    out, start = [], None
    for f, t in zip(flags + [False], ts + [ts[-1] + 1 if ts else 0]):
        if f and start is None:
            start = t
        elif not f and start is not None:
            if t - start >= min_len:
                out.append((round(start, 1), round(t, 1)))
            start = None
    return out


def build(duration: float, speech, excite, game, segments, samples, sounds=()) -> dict:
    ts = [s["t"] for s in samples]
    menus = _runs([s["menu"] > 0.25 for s in samples], ts, 1.0)
    deaths = _runs([s["redness"] > 1.8 and s["brightness"] > 30 for s in samples], ts, 1.0)

    speaking = np.zeros(int(duration) + 2, bool)
    for s, e in speech:
        speaking[int(s): int(e) + 1] = True
    idle = _runs([s["motion"] < 1.0 and not speaking[int(s["t"])] for s in samples], ts, 6.0)

    health = [(s["t"], s["health"]) for s in samples if s.get("health") is not None and s["menu"] < 0.15]
    drops = []
    for i, (t, h) in enumerate(health):
        j = i
        while j > 0 and t - health[j - 1][0] <= 3:
            j -= 1
        if health[j][1] - h >= 3 and (not drops or t - drops[-1]["t"] > 5):
            drops.append({"t": t, "from": health[j][1], "to": h})
    low = _runs([h is not None and h <= 3 for _, h in health], [t for t, _ in health], 2.0)

    words = [w for seg in segments for w in seg["words"]]
    clip_marks = [w["start"] for w in words if any(c in w["word"].lower() for c in CLIP_WORDS)]
    hype = [seg["start"] for seg in segments if any(h in seg["text"] for h in HYPE_WORDS)]

    highlights = _score(duration, excite, game, drops, deaths, low, clip_marks, hype, sounds)
    return {
        "duration": duration, "speech": speech, "excitement": excite, "game_events": game, "sounds": list(sounds),
        "menus": menus, "idle": idle, "death_candidates": deaths, "health_drops": drops,
        "low_health": low, "clip_marks": clip_marks, "highlights": highlights,
    }


def _score(duration, excite, game, drops, deaths, low, clip_marks, hype, sounds=()) -> list[dict]:
    n = int(duration) + 1
    score = np.zeros(n)
    why: list[set] = [set() for _ in range(n)]

    def add(t, w, reason):
        i = min(n - 1, max(0, int(t)))
        score[i] += w
        why[i].add(reason)

    for e in excite:
        add(e["t"], 1.0 + 0.5 * e["score"], t("r_excited"))
    # Classified sound events weigh more than raw loudness: a laugh or a scream
    # is the clearest signal that something happened.
    weights = {"laugh": (3.0, t("r_laugh")), "scream": (2.5, t("r_scream")), "gasp": (1.2, t("r_gasp")),
               "explosion": (1.5, t("r_explosion"))}
    for e in sounds:
        if e["kind"] in weights:
            w, label = weights[e["kind"]]
            add(e["t"], w * (0.5 + e["score"]), label)
    for e in game:
        add(e["t"], 0.6 + e["score"] / 30, t("r_game"))
    for d in drops:
        add(d["t"], 2.0 + (d["from"] - d["to"]) / 3, t("r_health", a=d["from"], b=d["to"]))
    for s, _ in deaths:
        add(s, 4.0, t("r_death"))
    for s, _ in low:
        add(s, 1.5, t("r_low"))
    for tc in clip_marks:
        add(tc - 5, 5.0, t("r_clip"))
    for th in hype:
        add(th, 0.7, t("r_hype"))

    # Pool within an 8 s window so a burst of signals becomes one moment.
    k = 8
    pooled = np.convolve(score, np.ones(k), mode="same")
    out = []
    taken = np.zeros(n, bool)
    for i in np.argsort(-pooled):
        if pooled[i] < 1.5 or len(out) >= 40:
            break
        if taken[max(0, i - 10): i + 10].any():
            continue
        taken[i] = True
        reasons = set().union(*why[max(0, i - k): i + k])
        out.append({"t": float(i), "score": round(float(pooled[i]), 1), "why": sorted(reasons)})
    return sorted(out, key=lambda h: h["t"])


def to_markdown(tl: dict, segments: list[dict], samples: list[dict]) -> str:
    rows = [t("tl_head"), "|---|---|---|---|"]
    dur = tl["duration"]
    by_row: dict[int, list[str]] = {}
    for seg in segments:
        by_row.setdefault(int(seg["start"] // ROW), []).append(seg["text"])

    def overlaps(spans, a, b):
        return any(s < b and e > a for s, e in spans)

    def near(points, a, b):
        return any(a <= p < b for p in points)

    for r in range(int(dur // ROW) + 1):
        a, b = r * ROW, (r + 1) * ROW
        hs = [s["health"] for s in samples if a <= s["t"] < b and s.get("health") is not None and s["menu"] < 0.15]
        flags = []
        if near([e["t"] for e in tl["excitement"]], a, b):
            flags.append(t("f_voice"))
        if near([e["t"] for e in tl["game_events"]], a, b):
            flags.append(t("f_game"))
        for kind, flag in (("laugh", t("f_laugh")), ("scream", t("f_scream")), ("explosion", t("f_explosion"))):
            if near([e["t"] for e in tl.get("sounds", []) if e["kind"] == kind], a, b):
                flags.append(flag)
        if near([d["t"] for d in tl["health_drops"]], a, b):
            flags.append(t("f_drop"))
        if overlaps(tl["death_candidates"], a, b):
            flags.append(t("f_death"))
        if overlaps(tl["menus"], a, b):
            flags.append(t("f_menu"))
        if overlaps(tl["idle"], a, b):
            flags.append(t("f_idle"))
        if near(tl["clip_marks"], a, b):
            flags.append(t("f_clip"))
        text = " ".join(by_row.get(r, [])) or "—"
        hp = f"{min(hs):.0f}-{max(hs):.0f}" if hs else ""
        rows.append(f"| {fmt(a)} | {text} | {hp} | {' '.join(flags)} |")

    hl = [t("tl_hhead"), "|---|---|---|"] + [
        f"| {fmt(h['t'])} | {h['score']} | {', '.join(h['why'])} |"
        for h in sorted(tl["highlights"], key=lambda h: -h["score"])
    ]
    return (
        f"# {t('tl_title')} ({fmt(dur)})\n\n## {t('tl_candidates')}\n\n" + "\n".join(hl)
        + f"\n\n## {t('tl_full')}\n\n" + "\n".join(rows) + "\n"
    )
