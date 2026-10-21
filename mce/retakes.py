"""Find retakes in a recording and pick the best take of each line — Hebrew, English, any language.

When a creator flubs a line they say it again ("There are 30 days until GTA 6… / GTA 6 comes out in 30 days
and I'm gonna share one fact every day"). This finds:
  * repeated lines: attempts at the same line (fuzzy word match, so reworded/reordered takes still group),
    with the best one chosen — complete, fluent, confident, and later takes preferred (people re-record
    until it's right);
  * false starts inside one breath ("so this is part one so this is part one of…", "לכבוד, לכבוד עם התפוח"):
    the abandoned beginning is cut;
  * off-script talk between attempts ("okay", "no", "one sec", "רגע", "עוד פעם").

  uv run python -m mce.retakes analysis/transcript.json [--json analysis/retakes.json] [--window 60]

Prints each group (✔ kept, ✘ dropped, with the reason) and writes `takes`: the source ranges to keep, in
order, ready for a talkshort config or a paper edit. It's a proposal — read it, and override any pick
(the user's call on delivery always wins). Works on mce transcripts (segments → words with start/end/score).
"""
import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

GAP = 0.55          # silence that ends an utterance (s)
NIQQUD = re.compile(r"[֑-ׇ]")
FINALS = str.maketrans("ךםןףץ", "כמנפצ")
HE_PREFIX = "והשבלכמ"
NUMBERS = {
    # en
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
    "eight": "8", "nine": "9", "ten": "10", "twenty": "20", "thirty": "30", "forty": "40", "fifty": "50",
    "hundred": "100",
    # he (after final-letter folding)
    "אחד": "1", "אחת": "1", "שתיימ": "2", "שניימ": "2", "שתי": "2", "שני": "2", "שלוש": "3", "שלושה": "3",
    "ארבע": "4", "ארבעה": "4", "חמש": "5", "חמישה": "5", "שש": "6", "שישה": "6", "שבע": "7", "שבעה": "7",
    "שמונה": "8", "תשע": "9", "תשעה": "9", "עשר": "10", "עשרה": "10", "עשרימ": "20", "שלושימ": "30",
    "מאה": "100",
}
ALIASES = {"gonna": "going", "wanna": "want", "gotta": "got", "'cause": "because", "cuz": "because"}
# (not "אמ": that's also "אם" = "if" once final letters are folded)
FILLERS = {"um", "uh", "umm", "uhh", "erm", "hmm", "mm", "ah", "אה", "אממ", "אממממ", "הממ", "כאילו"}
# said between attempts, not to the audience
META = {"okay", "ok", "no", "wait", "sec", "second", "again", "sorry", "hold", "on", "cut", "take", "redo",
        "restart", "yeah", "hmm", "let", "let's", "lets", "go", "one", "do", "that", "it", "start", "over",
        "אוקיי", "אוקי", "לא", "רגע", "שנייה", "שניה", "עוד", "פעמ", "סליחה", "טוב", "יאללה", "שוב",
        "מההתחלה", "מחדש", "נעשה", "אני", "אז"}
# everyday words: two lines sharing only these aren't the same line ("אני לא יודע…", "יש פה…")
STOP = {"a", "an", "the", "to", "of", "in", "on", "and", "or", "but", "so", "if", "i", "i'm", "you", "your", "my",
        "me", "we", "it", "it's", "is", "are", "was", "be", "this", "that", "there", "here", "just", "like", "okay",
        "ok", "will", "would", "can", "going", "go", "get", "have", "has", "do", "with", "for", "from", "at", "as",
        "what", "all", "now", "then", "really", "very", "know", "don't", "not", "no", "yes", "guys",
        "אני", "אתה", "את", "הוא", "היא", "אנחנו", "אתמ", "זה", "זאת", "זו", "יש", "אינ", "פה", "כאנ", "של", "על",
        "עמ", "אל", "לא", "כנ", "גמ", "רק", "כמו", "אז", "טוב", "עכשיו", "רגע", "מה", "מי", "איכ", "כי", "כל",
        "עוד", "הנה", "פשוט", "ממש", "כאילו", "חברימ", "כזה", "יותר", "אבל", "או", "אמ", "היה", "יודע", "רואה",
        "אוקיי", "ש", "ו", "ה"}
# a take that stops on one of these was cut off mid-sentence
# (only words that can't end a sentence: "…steps ahead of you" is complete)
DANGLING = {"a", "an", "the", "to", "of", "and", "or", "but", "if", "your", "my", "with", "from", "for", "gonna",
            "going", "של", "את", "על", "עמ", "אל", "כי", "אמ", "או", "גמ", "כמו", "בגלל", "אבל", "ו", "ש", "ה"}


def norm(w: str) -> list[str]:
    """One spoken word → comparable tokens ('GTA6' → ['gta', '6'], 'שלושים' → ['30'])."""
    w = NIQQUD.sub("", w.lower()).translate(FINALS)
    w = re.sub(r"[\"׳״“”‘’.,!?;:()\[\]…–—-]", " ", w)
    w = re.sub(r"(?<=[^\W\d_])(?=\d)|(?<=\d)(?=[^\W\d_])", " ", w)  # letters|digits boundary
    return [NUMBERS.get(t, ALIASES.get(t, t)) for t in w.split()]


def same(a: str, b: str) -> bool:
    """Fuzzy token match: ASR spelling drift, Hebrew one-letter prefixes (ו/ה/ש/ב/ל/כ/מ)."""
    if a == b:
        return True
    for x, y in ((a, b), (b, a)):
        if len(y) >= 3 and x[0] in HE_PREFIX and x[1:] == y:
            return True
    return min(len(a), len(b)) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.8


def lcs(a: list[str], b: list[str]) -> int:
    """Longest common subsequence with fuzzy tokens (word order mostly kept between takes)."""
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if same(x, y) else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def load(path: str) -> list[dict]:
    data = json.loads(Path(path).read_text())
    segs = data["segments"] if isinstance(data, dict) else data
    words = []
    for s in segs:
        # multi-clip transcripts (vlogs): segments are on the joined timeline, words in their clip's time
        off = float(s["start"]) - float(s["src_start"]) if "src_start" in s else 0.0
        for w in s.get("words", []):
            if "start" in w and "end" in w and w.get("word", "").strip():
                words.append({"word": w["word"].strip(), "start": float(w["start"]) + off, "end": float(w["end"]) + off,
                              "score": float(w.get("score", 1.0)), "toks": norm(w["word"]),
                              "clip": s.get("clip"), "off": off})
    return sorted(words, key=lambda w: w["start"])


def utterances(words: list[dict]) -> list[list[dict]]:
    out: list[list[dict]] = []
    for w in words:
        if out and w["start"] - out[-1][-1]["end"] < GAP and not re.search(r"[.!?]$", out[-1][-1]["word"]) \
                and w.get("clip") == out[-1][-1].get("clip"):
            out[-1].append(w)
        else:
            out.append([w])
    return out


def toks(ws: list[dict]) -> list[str]:
    return [t for w in ws for t in w["toks"] if t not in FILLERS]


def split_restarts(u: list[dict]) -> list[tuple[list[dict], str | None]]:
    """Cut false starts inside one utterance: 2+ words said again right away, repeating most of what came
    before ("so this is part one so this is part one of…"); parallel phrasing ("נמצאת באזור בשם X ואני נמצא
    באזור בשם Y") doesn't count. One word said twice ("לכבוד, לכבוד", but also "ממש ממש") is only flagged
    "repeated word?" — emphasis or stutter is a judgement call. Returns pieces with a reason when flagged."""
    t = [w["toks"] for w in u]
    for i in range(len(u)):
        for j in range(i + 1, min(len(u), i + 14)):
            if not (t[i] and t[j] and same(t[i][0], t[j][0])):
                continue
            k = 0
            while j + k < len(u) and i + k < j and t[i + k] and t[j + k] and same(t[i + k][0], t[j + k][0]):
                k += 1
            if k >= 2 and k >= 0.6 * (j - i):
                head = [(u[:i], None)] if i else []
                return head + [(u[i:j], "false start")] + split_restarts(u[j:])
            if j == i + 1 and len(t[i][0]) >= 2 and not t[i][0].isdigit():
                head = [(u[:i], None)] if i else []
                return head + [(u[i:j], "repeated word?")] + split_restarts(u[j:])
    return [(u, None)]


def attempt(ws: list[dict], dropped: str | None = None) -> dict:
    tk = toks(ws)
    last = ws[-1]
    trailing = last["word"].endswith(("...", "…", "-", "—")) or (tk and tk[-1] in DANGLING)
    pauses = sum(1 for a, b in zip(ws, ws[1:]) if b["start"] - a["end"] > 0.45)
    clip = {"clip": ws[0]["clip"], "src": [round(ws[0]["start"] - ws[0]["off"], 2), round(last["end"] - ws[0]["off"], 2)]} \
        if ws[0].get("clip") else {}
    return {**clip, "start": round(ws[0]["start"], 2), "end": round(last["end"], 2), "text": " ".join(w["word"] for w in ws),
            "toks": tk, "conf": round(sum(w["score"] for w in ws) / len(ws), 3), "complete": not trailing,
            "fillers": sum(1 for w in ws for t in w["toks"] if t in FILLERS), "pauses": pauses,
            "meta": bool(tk) and len(tk) <= 4 and all(t in META for t in tk), "drop": dropped, "_ws": ws}


def covered(x: dict, by: dict) -> float:
    """Share of x's content words that `by` also says (1.0 = by says everything x says)."""
    c = [t for t in x["toks"] if t not in STOP] or x["toks"]
    return sum(1 for t in c if any(same(t, u) for u in by["toks"])) / max(len(c), 1)


def split_at_next(atts: list[dict], window: float) -> list[dict]:
    """A take that runs on into the start of the next line ("שהם כמו פוינטד דריפסטון הרגיל, אבל אם התאורה…"
    and then "אבל אם התאורה…" again) is split where that line begins, so each half is judged on its own."""
    out = []
    for i, a in enumerate(atts):
        ws, cut = a["_ws"], None
        for b in atts[i + 1:]:
            if b["start"] - a["end"] > window:
                break
            head = b["toks"][:3]
            if len(head) < 3 or b["drop"] or b["meta"]:
                continue
            flat = [(k, t) for k, w in enumerate(ws) for t in w["toks"] if t not in FILLERS]
            for n in range(1, len(flat) - 2):
                if all(same(flat[n + m][1], head[m]) for m in range(3)) and flat[n][0] > 0:
                    cut = flat[n][0]
                    break
            if cut:
                break
        if cut:
            first = attempt(ws[:cut], a["drop"])
            first["complete"] = True  # it stops where the next line starts, not mid-thought
            out += [first, attempt(ws[cut:], a["drop"])]
            for x in out[-2:]:
                x["check"] = a.get("check", False)
        else:
            out.append(a)
    return out


def related(a: dict, b: dict) -> bool:
    """b is another attempt at a's line."""
    if len(a["toks"]) < 3 or len(b["toks"]) < 2:
        return False
    content = lcs([t for t in a["toks"] if t not in STOP], [t for t in b["toks"] if t not in STOP])
    if content < 2:
        return False
    common = lcs(a["toks"], b["toks"])
    if b["start"] - a["end"] > 30:  # far apart: only a clear repeat counts (vlogs revisit topics)
        return content >= 3 and common / len(a["toks"]) >= 0.75
    opening = all(same(x, y) for x, y in zip(a["toks"][:3], b["toks"][:3])) and len(b["toks"]) >= 3
    bag = sum(1 for x in a["toks"] if any(same(x, y) for y in b["toks"])) / len(a["toks"])
    return common >= 3 and (common / len(a["toks"]) >= 0.6 or bag >= 0.7) or (opening and common >= 3)


def score(x: dict, longest: int, rank: float) -> float:
    return (2.0 * x["complete"] + 1.0 * len(x["toks"]) / max(longest, 1) + 0.5 * x["conf"]
            - 0.25 * x["fillers"] - 0.2 * x["pauses"] + 0.6 * rank)


def find(words: list[dict], window: float = 60.0) -> tuple[list[dict], list[list[int]]]:
    atts: list[dict] = []
    for u in utterances(words):
        for piece, reason in split_restarts(u):
            if piece:
                x = attempt(piece, None if reason == "repeated word?" else reason)
                x["check"] = reason == "repeated word?"
                atts.append(x)
    atts = split_at_next(atts, window)
    group = list(range(len(atts)))  # union-find
    root = lambda i: i if group[i] == i else root(group[i])  # noqa: E731
    for j, b in enumerate(atts):
        if b["drop"] or b["meta"]:
            continue
        for i in range(j - 1, -1, -1):
            a = atts[i]
            if b["start"] - a["end"] > window:
                break
            if not a["drop"] and not a["meta"] and related(a, b):
                group[root(j)] = root(i)  # nearest earlier attempt only: chaining on shared phrases over-merges
                break
    groups: dict[int, list[int]] = {}
    for i in range(len(atts)):
        groups.setdefault(root(i), []).append(i)
    multi = [g for g in groups.values() if len(g) > 1]
    for g in multi:
        longest = max(len(atts[i]["toks"]) for i in g)
        rank = {i: g.index(i) / (len(g) - 1) for i in g}
        left = list(g)
        while left:  # best take, then drop only what it really says again; the rest is another line
            best = max(left, key=lambda i: score(atts[i], longest, rank[i]))
            atts[best]["best"] = True
            same_line = [i for i in left if i == best or covered(atts[i], atts[best]) >= 0.6]
            for i in same_line:
                if i != best:
                    a = atts[i]
                    a["best"] = False
                    a["drop"] = "retake" if a["complete"] else "unfinished take"
            left = [i for i in left if i not in same_line]
        # off-script talk sandwiched between attempts of the same line
        for i in range(g[0], g[-1]):
            if atts[i]["meta"] and not atts[i]["drop"]:
                atts[i]["drop"] = "between takes"
    # a partial take whose words all come back in a later take of the same moment ("…and I'm gonna share one
    # fact" → "GTA 6 comes out in 30 days, so I'm starting a series where I share one GTA 6 fact every day")
    for i, x in enumerate(atts):
        if x["drop"] or x["meta"] or len(x["toks"]) < 5:
            continue
        for y in atts[i + 1:]:
            if y["start"] - x["end"] > 2 * window:
                break
            if y["drop"] or len(y["toks"]) <= len(x["toks"]):
                continue
            bag = sum(1 for t in x["toks"] if any(same(t, u) for u in y["toks"])) / len(x["toks"])
            if bag >= 0.7 and lcs(x["toks"], y["toks"]) / len(x["toks"]) >= 0.7:
                x["drop"] = f"said again in full at {y['start']:.1f}s"
                break
    return atts, multi


def keep_ranges(atts: list[dict], join: float = 1.2) -> list:
    """Source ranges to keep, in order: [start, end] — or {"clip", "in", "out"} (clip time) for multi-clip."""
    out: list[dict] = []
    for a in atts:
        if a["drop"]:
            continue
        p = out[-1] if out else None
        if p and a.get("clip") == p["clip"] and a["start"] - p["end"] < join and not any(
                x["drop"] and p["end"] <= x["start"] < a["start"] for x in atts):
            p["end"], p["src_end"] = a["end"], (a.get("src") or [0, 0])[1]
        else:
            out.append({"clip": a.get("clip"), "start": a["start"], "end": a["end"],
                        "src_start": (a.get("src") or [0])[0], "src_end": (a.get("src") or [0, 0])[1]})
    return [{"clip": r["clip"], "in": round(r["src_start"], 2), "out": round(r["src_end"], 2)} if r["clip"]
            else [round(r["start"], 2), round(r["end"], 2)] for r in out]


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.retakes")
    ap.add_argument("transcript")
    ap.add_argument("--json", help="write groups + keep ranges here (default: retakes.json next to the transcript)")
    ap.add_argument("--window", type=float, default=60.0, help="max seconds between two attempts of one line")
    a = ap.parse_args()
    atts, groups = find(load(a.transcript), a.window)
    fmt = lambda s: f"{int(s // 60)}:{s % 60:05.2f}"  # noqa: E731
    where = lambda x: f"{fmt(x['start'])}–{fmt(x['end'])}" + (f" [{x['clip']} {x['src'][0]:.2f}–{x['src'][1]:.2f}]" if x.get("clip") else "")  # noqa: E731
    for n, g in enumerate(groups, 1):
        print(f"\n— line {n}: {len(g)} takes")
        for i in g:
            x = atts[i]
            mark = "✘" if x["drop"] else "✔"
            print(f"  {mark} {where(x)}  {x['text'][:90]}" + (f"   ({x['drop']})" if x["drop"] else ""))
    lone = [x for x in atts if x["drop"] and not any(atts.index(x) in g for g in groups)]
    if lone:
        print("\n— false starts / off-script / said again later")
        for x in lone:
            print(f"  ✘ {where(x)}  {x['text'][:90]}   ({x['drop']})")
    checks = [x for x in atts if x.get("check") and not x["drop"]]
    if checks:
        print("\n— repeated word: stutter (cut) or emphasis (keep)? kept for now")
        for x in checks:
            print(f"  ? {where(x)}  {x['text'][:60]}")
    takes = keep_ranges(atts)
    dropped = sum(x["end"] - x["start"] for x in atts if x["drop"])
    print(f"\n{len(groups)} repeated lines, {sum(1 for x in atts if x['drop'])} pieces dropped ({dropped:.1f}s of speech); "
          f"{len(takes)} keep ranges")
    out = Path(a.json) if a.json else Path(a.transcript).with_name("retakes.json")
    out.write_text(json.dumps({
        "takes": takes,
        "groups": [[{k: atts[i][k] for k in ("clip", "src", "start", "end", "text", "drop", "complete", "conf") if k in atts[i]}
                    for i in g] for g in groups],
        "dropped": [{k: x[k] for k in ("clip", "src", "start", "end", "text", "drop") if k in x} for x in atts if x["drop"]],
        "check": [{k: x[k] for k in ("clip", "src", "start", "end", "text") if k in x} for x in checks],
    }, ensure_ascii=False, indent=1))
    print("→", out)


if __name__ == "__main__":
    main()
