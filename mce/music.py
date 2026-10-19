"""Music structure: where the song really starts, its sections and energy, and
where to start it in an edit so its best moment lands where the video needs it.

  uv run python -m mce.music analyze <song> [--plot out.png]
  uv run python -m mce.music fit <song> --duration 15.2 [--hit 2.417]

analyze → first sound (skips leading silence), tempo, bars, sections labelled by
          energy (intro / build / drop / main / break / outro), and drops.
fit     → the source offset to start the song at. Always on a bar line (never
          mid-phrase). With --hit, a drop lands on that timeline second (e.g. the
          hook's payoff cut); otherwise the most energetic stretch without a
          break covers the whole video.
"""
import argparse
import json

import numpy as np

from .i18n import t

SR = 22050
HOP = 512


def _bars(beat_times: np.ndarray, strength: np.ndarray) -> np.ndarray:
    """Bar lines: every 4th beat, phase chosen where onset strength is highest."""
    if len(beat_times) < 8:
        return beat_times
    phase = max(range(4), key=lambda p: strength[p::4].mean())
    return beat_times[phase::4]


def analyze(path: str) -> dict:
    import librosa

    y, sr = librosa.load(path, sr=SR, mono=True)
    dur = len(y) / sr
    rms = librosa.feature.rms(y=y, hop_length=HOP)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP)
    db = librosa.amplitude_to_db(rms, ref=np.max)

    # Where the music actually starts: first frame within 30 dB of the loud part.
    loud = np.percentile(db, 90)
    first = float(t[np.argmax(db > loud - 30)])
    last = float(t[len(db) - 1 - np.argmax(db[::-1] > loud - 30)])  # the song's real ending

    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=HOP)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=sr, hop_length=HOP)
    beats = beats[beats >= first - 0.05]
    bars = _bars(beats, onset[np.minimum(librosa.time_to_frames(beats, sr=sr, hop_length=HOP), len(onset) - 1)])
    if len(bars) < 2:
        bars = np.array([first, dur])

    # Per-bar features: loudness (dB), timbre (MFCC), brightness.
    mfcc = librosa.feature.mfcc(y=y, sr=sr, hop_length=HOP, n_mfcc=13)
    cent = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=HOP)[0]
    edges = list(bars) + [dur]
    loud_b, timbre_b, bright_b = [], [], []
    for a, b in zip(edges, edges[1:]):
        m = (t >= a) & (t < b)
        if not m.any():
            m[np.argmin(np.abs(t - a))] = True
        loud_b.append(db[m].mean())
        timbre_b.append(mfcc[:, m[: mfcc.shape[1]]].mean(axis=1))
        bright_b.append(cent[m[: len(cent)]].mean())
    loud_b, timbre_b, bright_b = np.array(loud_b), np.array(timbre_b), np.array(bright_b)
    nb = len(loud_b)

    # Energy relative to this song, smoothed over a 4-bar phrase.
    def rel(x):
        lo, hi = np.percentile(x, 10), np.percentile(x, 95)
        return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)
    raw = 0.75 * rel(loud_b) + 0.25 * rel(bright_b)
    k = min(4, nb)
    energy = np.convolve(np.pad(raw, (k // 2, k - 1 - k // 2), mode="edge"), np.ones(k) / k, mode="valid")

    # Novelty: how different the next 4 bars are from the previous 4 (timbre + energy).
    z = (timbre_b - timbre_b.mean(axis=0)) / (timbre_b.std(axis=0) + 1e-9)
    nov = np.zeros(nb)
    for i in range(2, nb - 1):
        a0, b1 = max(0, i - 4), min(nb, i + 4)
        nov[i] = np.linalg.norm(z[a0:i].mean(axis=0) - z[i:b1].mean(axis=0)) / np.sqrt(z.shape[1]) \
            + 1.5 * abs(raw[i:b1].mean() - raw[a0:i].mean())
    thr = max(np.percentile(nov, 75), 0.35)
    peaks = [i for i in range(1, nb - 1) if nov[i] >= thr and nov[i] == nov[max(0, i - 3):i + 4].max()]
    cuts = [0]
    for i in sorted(peaks, key=lambda i: -nov[i]):
        if all(abs(i - c) >= 4 for c in cuts) and nb - i >= 2:
            cuts.append(i)
    cuts = sorted(cuts) + [nb]

    # Split "strong" from "quiet" halfway between the song's quiet and loud levels.
    lo_lvl, hi_lvl = np.percentile(energy, 20), np.percentile(energy, 80)
    q_hi = (lo_lvl + hi_lvl) / 2
    q_lo = lo_lvl + 0.25 * (hi_lvl - lo_lvl)
    sections = []
    for n_, (a, b) in enumerate(zip(cuts, cuts[1:])):
        e = float(energy[a:b].mean())
        prev = sections[-1]["energy"] if sections else None
        if prev is not None and e - prev > 0.18 and e >= q_hi:
            label = "drop"  # the song comes back in hard after something quieter
        elif e >= q_hi:
            label = "main"
        elif e <= q_lo:
            label = "intro" if n_ == 0 else ("outro" if b == nb else "break")
        else:
            nxt = float(energy[b:cuts[n_ + 2]].mean()) if n_ + 2 < len(cuts) else e
            label = "build" if nxt - e > 0.15 else ("intro" if n_ == 0 else "main")
        sections.append({"label": label, "start": round(float(edges[a]), 3), "end": round(float(edges[b]), 3),
                         "energy": round(e, 2)})
    # "Where the song really gets going": first bar reaching the song's strong level.
    strong = [x for x in sections if x["label"] in ("main", "drop")]
    main_start = strong[0]["start"] if strong else float(edges[int(np.argmax(energy >= q_hi))])
    drops = [s["start"] for s in sections if s["label"] == "drop"]
    return {"duration": round(dur, 2), "first_sound": round(first, 3), "last_sound": round(last, 3),
            "bar_len": round(240 / tempo, 3) if tempo else 2.0, "main_start": round(main_start, 3),
            "tempo": round(tempo, 1),
            "beats": [round(float(b), 3) for b in beats], "bars": [round(float(b), 3) for b in bars],
            "bar_energy": [round(float(e), 2) for e in energy], "sections": sections, "drops": drops}


def fit(info: dict, duration: float, hit: float | None = None, end: str = "fade") -> dict:
    """Choose where in the song to start so the edit gets the right part of it.

    end="natural": the song's own ending lands on the video's last frame (the start
    is then the first bar after where it has to begin; the music comes in that much
    later). A `hit` takes priority over a natural ending.
    """
    if end == "natural" and hit is None:
        ideal = info["last_sound"] - duration
        later = [b for b in info["bars"] if b >= max(ideal, info["first_sound"] - 0.05)]
        s = later[0] if later else max(ideal, 0.0)
        return {"offset": round(s, 3), "timeline_start": round(s - ideal, 3), "end": "natural",
                "reason": t("m_natural", end=info["last_sound"], s=s)}
    bars, energy, dur = info["bars"], info["bar_energy"], info["duration"]
    starts = [b for b in bars if b + duration <= dur - 0.5] or [info["first_sound"]]

    def mean_energy(s: float) -> float:
        idx = [i for i, b in enumerate(bars) if s <= b < s + duration]
        return float(np.mean([energy[i] for i in idx])) if idx else 0.0

    def min_energy(s: float) -> float:
        idx = [i for i, b in enumerate(bars) if s <= b < s + duration]
        return float(min(energy[i] for i in idx)) if idx else 0.0

    if hit is not None and info["drops"]:
        best = None
        for d in info["drops"]:
            # First bar at or after (drop - hit): the drop then comes no later than
            # `hit`, and the song starts `delay` seconds into the video so the drop
            # lands exactly on it (delay < one bar, never negative).
            cands = [b for b in bars if max(info["first_sound"] - 0.05, d - hit - 1e-6) <= b <= d
                     and b + duration <= dur]
            if not cands:
                continue
            s = min(cands)
            delay = hit - (d - s)
            score = mean_energy(s) - (0.3 if delay > 1.0 else 0)
            if best is None or score > best[0]:
                best = (score, s, d, delay)
        if best:
            _, s, d, delay = best
            return {"offset": round(s, 3), "timeline_start": round(delay, 3), "drop_at": round(hit, 3),
                    "reason": t("m_drop", d=d, hit=hit, s=s, late=t("m_late", delay=delay) if delay > 0.01 else "")}
    # No drop target: the most energetic bar-aligned window with no real break.
    s = max(starts, key=lambda b: mean_energy(b) + 0.5 * min_energy(b))
    return {"offset": round(s, 3), "timeline_start": 0.0, "reason": t("m_energy", e=mean_energy(s), first=info["first_sound"])}


def plot(info: dict, out: str) -> None:
    import cv2

    W, H = 1400, 360
    img = np.full((H, W, 3), 255, np.uint8)
    sx = lambda tt: int(tt / info["duration"] * (W - 20)) + 10
    colors = {"intro": (200, 200, 200), "build": (120, 200, 255), "drop": (60, 60, 230), "main": (90, 170, 90),
              "break": (230, 200, 150), "outro": (180, 180, 180)}
    for s in info["sections"]:
        cv2.rectangle(img, (sx(s["start"]), 40), (sx(s["end"]), 300), colors[s["label"]], -1)
        cv2.putText(img, s["label"], (sx(s["start"]) + 4, 60), 0, 0.5, (0, 0, 0), 1)
    pts = [(sx(b), int(300 - e * 250)) for b, e in zip(info["bars"], info["bar_energy"])]
    for a, b in zip(pts, pts[1:]):
        cv2.line(img, a, b, (0, 0, 0), 2)
    cv2.line(img, (sx(info["first_sound"]), 30), (sx(info["first_sound"]), 310), (0, 0, 255), 2)
    for k in range(0, int(info["duration"]) + 1, 10):
        cv2.putText(img, f"{k}s", (sx(k), 340), 0, 0.45, (0, 0, 0), 1)
    cv2.line(img, (sx(info["main_start"]), 30), (sx(info["main_start"]), 310), (255, 0, 0), 2)
    cv2.putText(img, f"tempo {info['tempo']}  first sound {info['first_sound']}s (red)  "
                     f"gets going {info['main_start']}s (blue)", (10, 22), 0, 0.6, (0, 0, 0), 1)
    cv2.imwrite(out, img)


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.music")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("analyze")
    a1.add_argument("song")
    a1.add_argument("--plot")
    a2 = sub.add_parser("fit")
    a2.add_argument("song")
    a2.add_argument("--duration", type=float, required=True)
    a2.add_argument("--hit", type=float)
    a = ap.parse_args()
    info = analyze(a.song)
    if a.cmd == "analyze":
        print(json.dumps({k: v for k, v in info.items() if k not in ("beats", "bars", "bar_energy")},
                         ensure_ascii=False, indent=1))
        if a.plot:
            plot(info, a.plot)
    else:
        print(json.dumps(fit(info, a.duration, a.hit), ensure_ascii=False))


if __name__ == "__main__":
    main()


def _fade_keys(length: float, base: float, fade_in: float, fade_out: float) -> list[list[float]]:
    """Constant-power-ish fades: -3 dB at the midpoint of each fade."""
    k = [[0, base - 40]] if fade_in > 0 else [[0, base]]
    if fade_in > 0:
        k += [[round(fade_in / 2, 3), base - 3], [round(fade_in, 3), base]]
    if fade_out > 0:
        k += [[round(length - fade_out, 3), base], [round(length - fade_out / 2, 3), base - 3],
              [round(length, 3), base - 40]]
    else:
        k += [[round(length, 3), base]]
    return k


def _merge_keys(fades: list[list[float]], duck: list[list[float]] | None) -> list[list[float]]:
    if not duck:
        return fades
    a, b = fades[0][0], fades[-1][0]
    head = [x for x in fades if x[0] <= fades[2][0]] if len(fades) > 4 else fades[:1]
    tail = [x for x in fades if x[0] >= fades[-3][0]] if len(fades) > 4 else fades[-1:]
    body = [x for x in duck if head[-1][0] < x[0] < tail[0][0]]
    return head + body + tail


def apply_fit(spec: dict, music_file: str = "music", hit: float | None = None, end: str = "fade",
              fade_in: float = 0.12) -> str:
    """Re-cut the spec's music clip from the chosen offset. end: "fade" (fade over
    one bar into the video's end) or "natural" (the song's own ending lands there)."""
    clips = [c for tr in spec.get("audio", []) for c in tr if c["file"] == music_file]
    if not clips:
        return "no music clip"
    c = clips[0]
    vid_end = c["start"] + c["out"] - c["in"]
    info = analyze(spec["files"][music_file]["path"])
    r = fit(info, vid_end - c["start"], hit, end)
    c["start"] = round(c["start"] + r["timeline_start"], 3)
    c["in"] = r["offset"]
    c["out"] = round(r["offset"] + vid_end - c["start"], 3)
    length = vid_end - c["start"]
    fade_out = 0.05 if r.get("end") == "natural" else min(max(info["bar_len"], 0.8), 2.5)
    c["gain_keys"] = _merge_keys(_fade_keys(length, c.get("gain_db", 0), fade_in, fade_out), c.get("gain_keys"))
    return r["reason"]


def apply_playlist(spec: dict, songs: list[dict], xfade: float | None = None, base_db: float = -20,
                   end: str = "fade") -> list[str]:
    """Several songs back to back, each switch a crossfade on alternating tracks.

    songs: [{"file": key, "until": timeline_seconds, "hit": optional}, ..., {"file": key}]
    Song B enters on its own track `xfade` seconds before the switch point and fades
    up while A fades out; B is cut so its strong entrance (a drop, else where it gets
    going) arrives as the crossfade completes.
    """
    vid_end = max(c["start"] + (c["out"] - c["in"]) / (c.get("speed") or 1)
                  for tr in spec.get("video", []) for c in tr)
    keys = {s["file"] for s in songs}
    spec["audio"] = [[c for c in tr if c["file"] not in keys] for tr in spec.get("audio", [])]
    spec["audio"] = [tr for tr in spec["audio"] if tr]
    lanes: list[list[dict]] = [[], []]
    report, prev = [], None  # prev = (switch point, crossfade length) of the outgoing song
    for i, song in enumerate(songs):
        info = analyze(spec["files"][song["file"]]["path"])
        last = i == len(songs) - 1
        xf_out = xfade or min(max(2 * info["bar_len"], 1.0), 4.0)  # crossfade into the next song
        a = 0.0 if prev is None else max(0.0, prev[0] - prev[1] / 2)
        fin = 0.12 if prev is None else prev[1]
        b_out = vid_end if last else min(song["until"] + xf_out / 2, vid_end)
        win = b_out - a
        if prev is None:
            r = fit(info, win, song.get("hit"), end if last else "fade")
        else:
            # The song's strong entrance arrives right as its fade-in completes.
            target = song.get("hit", fin)
            r = fit(info, win, target) if info["drops"] else {
                "offset": round(max(info["first_sound"], info["main_start"] - target), 3), "timeline_start": 0.0,
                "reason": t("m_enters", t=info["main_start"])}
        start = a + r["timeline_start"]
        length = b_out - start
        if prev is not None:  # finish fading up exactly when the outgoing song is gone
            fin = max(0.12, round(prev[0] + prev[1] / 2 - start, 3))
        fout = xf_out if not last else (0.05 if r.get("end") == "natural" else min(max(info["bar_len"], 0.8), 2.5))
        clip = {"file": song["file"], "start": round(start, 3), "in": r["offset"],
                "out": round(r["offset"] + length, 3), "gain_db": base_db, "stream": 1,
                "name": f"Music {i + 1}", "gain_keys": _fade_keys(length, base_db, fin, fout)}
        lanes[i % 2].append(clip)
        report.append(t("m_song", n=i + 1, file=song["file"], a=start, b=b_out, off=r["offset"])
                      + (t("m_xfade", x=fin) if prev else "") + f" — {r['reason']}")
        prev = None if last else (song["until"], xf_out)
    spec["audio"] += [lane for lane in lanes if lane]
    return report
