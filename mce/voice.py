"""Voice clean-up: find out what's wrong with a recording's voice, then fix only that.

Most recordings need nothing beyond the normal master (talkshort's VOICE_CHAIN). Use this when the user
asks for cleaner audio, or when `analyze` shows a real problem. Over-cleaning makes a voice watery and
robotic — worse than a little room tone — so treat the cause, at the lightest level that works.

  uv run python -m mce.voice analyze <media> [--stream N] [--transcript analysis/transcript.json]
      → noise floor, signal-to-noise, steady vs changing background, hum, clipping, bandwidth, and a
        recommended `clean` command
  uv run python -m mce.voice compare <media> [--stream N]   → 20 s at every level (original/light/medium/strong) to listen
  uv run python -m mce.voice clean <media> [--stream N] --level light|medium|strong [--hum 50|60] [--declip]
                                     [--start S --dur D]   (a short excerpt, to A/B before doing the whole file)
      → <media>_vo<N>_<tag>.wav: cleaned, mastered to -14 LUFS / -2 dBTP, lip-sync delay trimmed

Levels (what each one is for):
  light   steady hiss / fan / AC under a decent recording: high-pass + gentle spectral denoise tuned
          to the measured noise floor + de-ess
  medium  noisier room: stronger denoise + downward expander, so the room drops away in the pauses
  strong  changing background — music, game audio, street, crowd, TV: Demucs pulls the voice out first
          (slow, ~1/10 real time), then light. The only option when the noise isn't steady. The background
          stem is kept too: when the sound around the voice is part of the video (the store, the cooking,
          the game), lay it on its own track 12-18 dB under the clean voice rather than deleting it.
--hum    mains hum (50 Hz Israel/Europe, 60 Hz US) and its harmonics notched out. analyze detects it.
--declip  repairs mild clipping (adeclip). Heavy clipping can't be repaired — re-record if possible.

Not fixable here: heavy room echo/reverb (no good offline de-reverb in ffmpeg). Options to give the user:
Premiere's own Essential Sound → Dialogue → "Enhance Speech" (Premiere 2024+, one click per clip, very
good), or Adobe Podcast Enhance (web). Both are the user's to click — mention them, don't pretend.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

from . import ff
from .talkshort import VOICE_CHAIN, master_voice

SR = 48000
HOP = 0.02  # analysis frame (s)


def _read(src: str, stream: int, start: float = 0.0, dur: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", str(start), "-i", src] + (["-t", str(dur)] if dur else []) + \
          ["-map", f"0:a:{stream}", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    return np.frombuffer(ff.run(cmd, binary=True)[0], np.float32)


def _speech_mask(n_frames: int, transcript: str | None, offset: float = 0.0) -> np.ndarray | None:
    if not transcript:
        return None
    data = json.loads(Path(transcript).read_text(encoding="utf-8"))
    segs = data["segments"] if isinstance(data, dict) else data
    mask = np.zeros(n_frames, bool)
    for s in segs:
        for w in s.get("words", []):
            if "start" in w:
                a, b = int((w["start"] - offset) / HOP), int((w["end"] - offset) / HOP) + 1
                mask[max(0, a):max(0, b)] = True
    return mask


def analyze(src: str, stream: int = 0, transcript: str | None = None, start: float = 0.0,
            dur: float | None = 600.0) -> dict:
    """Measure the voice recording (first `dur` s by default — enough to judge, fast)."""
    x = _read(src, stream, start, dur)
    if not len(x):
        raise SystemExit(f"no audio in stream {stream} of {src}")
    hop = int(SR * HOP)
    frames = x[: len(x) // hop * hop].reshape(-1, hop)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(1)) + 1e-9)
    mask = _speech_mask(len(db), transcript, start)
    if mask is not None and mask.any() and (~mask).any():
        speech, quiet = db[mask], db[~mask & (db > -90)]  # pauses between words = the background
    else:  # no transcript: loudest 30% of frames = speech, quietest 15% = background
        speech, quiet = db[db >= np.percentile(db, 70)], db[(db <= np.percentile(db, 15)) & (db > -90)]
    noise = float(np.median(quiet)) if len(quiet) else -90.0
    voice = float(np.median(speech))
    # steady (hiss/fan) vs changing (music/game/street): spread of the background level over time
    spread = float(np.percentile(quiet, 90) - np.percentile(quiet, 10)) if len(quiet) > 20 else 0.0

    # spectrum of the background → mains hum; spectrum of speech → bandwidth
    def spectrum(sel: np.ndarray) -> np.ndarray:
        idx = np.flatnonzero(sel)[:4000]
        if not len(idx):
            return np.zeros(4097)
        win = np.hanning(8192)
        segs = [x[i * hop: i * hop + 8192] for i in idx[::4] if i * hop + 8192 <= len(x)]
        return np.mean([np.abs(np.fft.rfft(s * win)) for s in segs], 0) if segs else np.zeros(4097)
    freqs = np.fft.rfftfreq(8192, 1 / SR)

    def texture(sel: np.ndarray) -> float:
        n, f2 = 2048, np.fft.rfftfreq(2048, 1 / SR)
        edges = np.geomspace(150, 8000, 25)
        bands = []
        for i in np.flatnonzero(sel)[::2][:3000]:
            seg = x[i * hop: i * hop + n]
            if len(seg) == n:
                p = np.abs(np.fft.rfft(seg * np.hanning(n))) ** 2
                bands.append([10 * np.log10(p[(f2 >= a) & (f2 < b)].mean() + 1e-12) for a, b in zip(edges, edges[1:])])
        if len(bands) < 20:
            return 0.0
        b = np.array(bands)
        return float(np.median((b - b.mean(1, keepdims=True)).std(0)))
    qsel = (db <= np.percentile(db, 25)) if mask is None else (~mask & (db > -90))
    qspec = 20 * np.log10(spectrum(qsel) + 1e-9)
    hum = None
    for base in (50, 60):
        score = []
        for h in (1, 2, 3):
            f = base * h
            k = int(np.argmin(np.abs(freqs - f)))  # bins are ~5.9 Hz wide
            peak = qspec[k - 1:k + 2].max()
            around = np.median(qspec[((freqs > f - 15) & (freqs < f - 5)) | ((freqs > f + 5) & (freqs < f + 15))])
            score.append(peak - around)
        if np.mean(score) > 10:
            hum = base
    # bandwidth: highest frequency where speech is still within 55 dB of its peak (a codec / phone line
    # cuts off sharply; natural speech just tapers)
    sdb = 20 * np.log10(spectrum(db >= np.percentile(db, 70)) + 1e-9)
    sdb = np.convolve(sdb, np.ones(9) / 9, "same")
    above = np.flatnonzero(sdb > sdb.max() - 55)
    bandwidth = float(freqs[above[-1]]) if len(above) else 0.0
    clipped = float((np.abs(x) > 0.985).mean() * 100)

    snr = voice - noise
    tex = texture(qsel)
    changing = spread > 8 or tex > 4.0
    problems, level = [], None
    if snr < 15:
        problems.append("changing background (music / game / people / street) close to the voice level"
                        if changing else "loud steady background noise")
        level = "strong" if changing else "medium"
    elif snr < 30 or noise > -50:
        problems.append(("changing (people / street / music?)" if changing else "steady (fan / hiss / AC)")
                        + f" background ({noise:.0f} dBFS in the pauses)")
        level = ("strong" if snr < 20 else "medium") if changing else ("medium" if snr < 22 else "light")
    if hum:
        problems.append(f"{hum} Hz mains hum")
    if clipped > 0.05:
        problems.append(f"clipping ({clipped:.2f}% of samples at full scale)" +
                        (" — too much to repair well, re-record if possible" if clipped > 1 else ""))
    if bandwidth and bandwidth < 7000:
        problems.append(f"narrow bandwidth (nothing above ~{bandwidth / 1000:.1f} kHz: phone / heavily compressed) — can't be restored")
    return {"voice_db": round(voice, 1), "noise_db": round(noise, 1), "snr_db": round(snr, 1),
            "background_spread_db": round(spread, 1), "background_texture_db": round(tex, 2), "hum_hz": hum, "clipped_pct": round(clipped, 3),
            "bandwidth_hz": round(bandwidth), "problems": problems, "level": level,
            "declip": clipped > 0.05}


def chain(level: str, noise_db: float = -62.0, hum: int | None = None, declip: bool = False) -> str:
    nf = max(-80, min(-25, round(noise_db)))  # afftdn wants the noise floor it's removing
    pre = []
    if declip:
        pre.append("adeclip")
    if hum:  # notch the mains frequency and its first harmonics
        pre += [f"bandreject=f={hum * h}:width_type=q:w=25" for h in (1, 2, 3, 4)]
    if level == "light":
        core = f"highpass=f=80,afftdn=nr=12:nf={nf}:tn=1"
    elif level == "medium":
        core = (f"highpass=f=90,afftdn=nr=20:nf={nf}:tn=1,"
                # downward expander: below the voice, the room is pulled down 10 dB instead of gated off
                "agate=threshold=0.02:ratio=2:range=0.3:attack=5:release=180")
    else:  # strong: the voice stem is already separated; just tidy it
        core = f"highpass=f=80,afftdn=nr=8:nf={nf}:tn=1"
    tone = VOICE_CHAIN.split(",", 2)[2]  # the talkshort EQ / de-ess / compression, after the clean-up
    return ",".join(pre + [core, tone])


def clean(src: str, stream: int = 0, level: str = "light", hum: int | None = None, declip: bool = False,
          start: float | None = None, dur: float | None = None, noise_db: float | None = None) -> str:
    work = src
    if start is not None or dur is not None:  # excerpt for a quick A/B
        cut = Path(src).with_name(f"{Path(src).stem}_excerpt_{start or 0:g}_{dur or 0:g}.wav")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start or 0), "-i", src] + (["-t", str(dur)] if dur else []) +
                       ["-map", f"0:a:{stream}", "-ar", str(SR), str(cut)], check=True)
        work, stream = str(cut), 0
    if noise_db is None:
        noise_db = analyze(work, stream)["noise_db"]
    if level == "strong":
        from .stems import separate
        stems = separate(work, Path(work).with_name(Path(work).stem + "_stems"), stream)
        work, stream = stems["vocals"], 0
        # the rest (room, crowd, the activity itself) is kept: often it IS the content — the peeling, the
        # store, the game. Put it on its own track ~12-18 dB down instead of losing it.
        print("background stem (everything but the voice):", stems["no_vocals"])
        noise_db = analyze(work, 0)["noise_db"]
    return master_voice(work, stream, chain(level, noise_db, hum, declip))


def busiest(src: str, stream: int, dur: float = 20.0) -> float:
    """Start of the `dur` window with the most speech-level audio in the first 10 minutes."""
    x = _read(src, stream, 0, 600)
    hop = int(SR * HOP)
    db = 20 * np.log10(np.sqrt((x[: len(x) // hop * hop].reshape(-1, hop) ** 2).mean(1)) + 1e-9)
    loud = (db > np.percentile(db, 60)).astype(float)
    w = int(dur / HOP)
    if len(loud) <= w:
        return 0.0
    return float(np.argmax(np.convolve(loud, np.ones(w), "valid")) * HOP)


def compare(src: str, stream: int = 0, start: float | None = None, dur: float = 20.0,
            hum: int | None = None, declip: bool = False) -> dict[str, str]:
    """Same excerpt at every level, all at the same loudness, in <media>_voice_compare/ — for listening."""
    import shutil
    start = busiest(src, stream, dur) if start is None else start
    out_dir = Path(src).with_name(Path(src).stem + "_voice_compare")
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir()
    raw = out_dir / "excerpt.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(start), "-i", src, "-t", str(dur), "-map", f"0:a:{stream}",
                    "-ar", str(SR), str(raw)], check=True)
    files = {"original": str(out_dir / "0_original.wav")}
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-af", "loudnorm=I=-14:TP=-2", "-ar", str(SR),
                    files["original"]], check=True)
    for i, level in enumerate(("light", "medium", "strong"), 1):
        dst = out_dir / f"{i}_{level}.wav"
        Path(clean(str(raw), 0, level, hum, declip)).replace(dst)
        files[level] = str(dst)
    for p in out_dir.iterdir():  # keep only the four files to listen to
        if p.name not in {Path(f).name for f in files.values()}:
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    print(f"excerpt {start:.1f}–{start + dur:.1f}s")
    return files


def _report(m: dict, src: str, stream: int) -> None:
    print(f"voice {m['voice_db']} dBFS · background {m['noise_db']} dBFS · SNR {m['snr_db']} dB · "
          f"background spread {m['background_spread_db']} dB / texture {m['background_texture_db']} dB · bandwidth {m['bandwidth_hz'] / 1000:.1f} kHz · "
          f"clipping {m['clipped_pct']}%" + (f" · hum {m['hum_hz']} Hz" if m["hum_hz"] else ""))
    if not m["problems"] and not m["level"]:
        print("✅ clean recording — the normal voice master is enough (no extra clean-up)")
        return
    for p in m["problems"]:
        print("  •", p)
    if m["level"] or m["hum_hz"] or m["declip"]:
        cmd = f'uv run python -m mce.voice clean "{src}" --stream {stream} --level {m["level"] or "light"}'
        cmd += (f" --hum {m['hum_hz']}" if m["hum_hz"] else "") + (" --declip" if m["declip"] else "")
        print("→ suggested:", cmd)
        print(f'  not sure? uv run python -m mce.voice compare "{src}" --stream {stream}   (20 s at every level, to listen)')


def main() -> None:
    ap = argparse.ArgumentParser(prog="mce.voice")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a1 = sub.add_parser("analyze")
    a1.add_argument("media")
    a1.add_argument("--stream", type=int, default=0)
    a1.add_argument("--transcript", help="word timings → exact speech vs pauses (better noise estimate)")
    a1.add_argument("--start", type=float, default=0.0)
    a1.add_argument("--dur", type=float, default=600.0)
    a1.add_argument("--json")
    a3 = sub.add_parser("compare", help="20 s excerpt at every level, to listen and choose")
    a3.add_argument("media")
    a3.add_argument("--stream", type=int, default=0)
    a3.add_argument("--start", type=float, help="default: the 20 s with the most speech")
    a3.add_argument("--dur", type=float, default=20.0)
    a3.add_argument("--hum", type=int, choices=[50, 60])
    a3.add_argument("--declip", action="store_true")
    a2 = sub.add_parser("clean")
    a2.add_argument("media")
    a2.add_argument("--stream", type=int, default=0)
    a2.add_argument("--level", choices=["light", "medium", "strong"], default="light")
    a2.add_argument("--hum", type=int, choices=[50, 60])
    a2.add_argument("--declip", action="store_true")
    a2.add_argument("--start", type=float)
    a2.add_argument("--dur", type=float)
    a = ap.parse_args()
    if a.cmd == "compare":
        files = compare(a.media, a.stream, a.start, a.dur, a.hum, a.declip)
        for k, v in files.items():
            m = analyze(v, 0)
            print(f"{k:9s} background {m['noise_db']:6.1f} dBFS · SNR {m['snr_db']:5.1f} dB  {v}")
        print("Listen to all four (same 20 s, same loudness) and pick the lightest level that sounds clean.")
    elif a.cmd == "analyze":
        m = analyze(a.media, a.stream, a.transcript, a.start, a.dur)
        _report(m, a.media, a.stream)
        if a.json:
            Path(a.json).write_text(json.dumps(m, indent=1), encoding="utf-8")
    else:
        out = clean(a.media, a.stream, a.level, a.hum, a.declip, a.start, a.dur)
        before = analyze(a.media, a.stream, start=a.start or 0, dur=a.dur or 600)
        after = analyze(out, 0)
        print(f"→ {out}\n  background {before['noise_db']} → {after['noise_db']} dBFS · "
              f"SNR {before['snr_db']} → {after['snr_db']} dB")


if __name__ == "__main__":
    main()
