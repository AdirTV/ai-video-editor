"""mce — AI auto-editor CLI (any footage: gameplay, vlogs, talking head, podcasts).

  mce analyze <video> [--out DIR] [--mic N] [--game N] [--layout auto|none|facecam_left|facecam_right]
  mce moment <analysis-dir> <seconds>...      contact sheet around given moments
  mce export <edit_plan.json> [-o out.xml]    Premiere-ready FCP7 XML
"""
import argparse
import json
import time
from pathlib import Path

from . import audio, fcpxml, sheets, timeline, vision
from .config import LANGUAGE, PROFILE
from .probe import probe


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _save(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1))


def analyze(args) -> None:
    src = str(Path(args.video).resolve())
    out = Path(args.out or Path(src).with_suffix("").as_posix() + "_analysis")
    out.mkdir(parents=True, exist_ok=True)
    info = probe(src)
    _log(f"{info.width}x{info.height} @ {info.fps_float:.2f}fps, {sheets.fmt(info.duration)}, "
         f"{len(info.audio_streams)} audio streams")

    layout = args.layout
    if layout == "auto":
        layout = vision.detect_layout(src, info.width, info.height, info.duration) if info.is_wide else "none"
    _log(f"layout: {layout}")

    mic_i = args.mic
    game_i = args.game if args.game is not None else (1 if len(info.audio_streams) > 1 else None)
    (out / "audio").mkdir(exist_ok=True)
    mic_wav = out / "audio" / "mic.wav"
    game_from_stems, st = False, None
    if args.separate:
        # Voice and game/music share one stream: split them so transcription, laughs and game sounds
        # each get a clean signal.
        from . import stems
        _log("separating voice from game/music (demucs)…")
        st = stems.separate(src, out / "audio" / "stems", stream=mic_i)
        audio.to_mono16k(st["vocals"], str(mic_wav))
        if game_i is None:
            game_from_stems = True
            audio.to_mono16k(st["no_vocals"], str(out / "audio" / "game.wav"))
    else:
        audio.extract(src, mic_i, str(mic_wav))
    mic_db = audio.envelope(audio.load(str(mic_wav)))
    speech = audio.speech_segments(mic_db)
    excite = audio.excitement(mic_db, speech)
    game = []
    if game_i is not None or game_from_stems:
        game_wav = out / "audio" / "game.wav"
        if not game_from_stems:
            audio.extract(src, game_i, str(game_wav))
        game = audio.game_events(audio.envelope(audio.load(str(game_wav))))
    _log(f"audio: {len(speech)} speech segments, {len(excite)} excited, {len(game)} game spikes")
    from . import events
    sounds = events.detect(str(mic_wav), groups=["laugh", "scream", "gasp"])
    if game_i is not None or game_from_stems:
        sounds += events.detect(str(out / "audio" / "game.wav"), groups=["explosion"])
    _log(f"sound events: " + ", ".join(f"{k} {sum(e['kind'] == k for e in sounds)}"
                                        for k in ("laugh", "scream", "gasp", "explosion")))

    seg_path = out / "transcript.json"
    if seg_path.exists() and not args.retranscribe:
        segments = json.loads(seg_path.read_text())
        _log("transcript: cached")
    else:
        from . import transcribe as tr
        lang = args.language
        _log(f"transcribing ({lang})…")
        vocab = Path(__file__).parent.parent / "vocab.txt"
        extra = vocab.read_text().strip().replace("\n", ", ") if vocab.exists() else ""
        base = tr.PROMPTS.get((args.profile, lang), "") if lang != "auto" else ""
        prompt = ", ".join(x for x in (base, extra) if x) or None
        segments = tr.transcribe(str(mic_wav), prompt=prompt, language=lang)
        _save(seg_path, segments)
        _log(f"language: {tr.LAST_LANGUAGE}")
    if args.speakers and not any("speaker" in s for s in segments):
        from . import transcribe as tr
        _log("diarizing speakers…")
        segments = tr.diarize(str(mic_wav), segments, None if args.speakers == "auto" else int(args.speakers))
        _save(seg_path, segments)
        _log("speakers: " + ", ".join(sorted({s["speaker"] for s in segments if "speaker" in s})))
    # Reports and labels follow the language actually spoken.
    from .i18n import guess, set_lang
    set_lang(guess(" ".join(s["text"] for s in segments)) if segments else args.language)
    _log(f"transcript: {len(segments)} segments")

    _log("scanning picture…")
    samples = vision.scan(src, info.width, info.height, layout, out / "thumbs")
    if args.profile != "minecraft":
        # HUD detectors (hearts, inventory panels, death screen) only mean something in Minecraft.
        for smp in samples:
            smp.update(heart_px=0, menu=0.0, redness=1.0, health=None)
    _save(out / "vision.json", samples)

    tl = timeline.build(info.duration, speech, excite, game, segments, samples, sounds)
    tl.update({"source": src, "layout": layout, "fps": info.fps_float,
               "audio": {"mic": mic_i, "game": game_i}, "stems": st, "width": info.width, "height": info.height})
    _save(out / "timeline.json", tl)
    (out / "timeline.md").write_text(timeline.to_markdown(tl, segments, samples))
    (out / "transcript.md").write_text("\n".join(
        f"[{sheets.fmt(s['start'])}]" + (f" {s['speaker']}:" if "speaker" in s else "") + f" {s['text']}"
        for s in segments) + "\n")

    sheets.overview(out / "thumbs", info.duration, out / "sheets")
    for h in sorted(tl["highlights"], key=lambda h: -h["score"])[:20]:
        sheets.moment(out / "thumbs", h["t"], info.duration, out / "sheets")
    _log(f"done → {out}")


def moment(args) -> None:
    out = Path(args.dir)
    tl = json.loads((out / "timeline.json").read_text())
    for t in args.seconds:
        print(sheets.moment(out / "thumbs", float(t), tl["duration"], out / "sheets"))


def export(args) -> None:
    plan_path = Path(args.plan)
    plan = json.loads(plan_path.read_text())
    info = probe(plan["source"])
    xml = fcpxml.build(plan, info)
    dest = Path(args.output or plan_path.with_suffix(".xml"))
    dest.write_text(xml)
    print(dest)


def main() -> None:
    p = argparse.ArgumentParser(prog="mce")
    sub = p.add_subparsers(required=True)

    a = sub.add_parser("analyze")
    a.add_argument("video")
    a.add_argument("--out")
    a.add_argument("--mic", type=int, default=0, help="audio stream index of the mic (0-based)")
    a.add_argument("--game", type=int, help="audio stream index of game sound")
    a.add_argument("--layout", default="auto", choices=["auto", "none", "facecam_left", "facecam_right"])
    a.add_argument("--retranscribe", action="store_true")
    a.add_argument("--separate", action="store_true",
                   help="voice and game/music are mixed in one stream: split them with demucs first")
    a.add_argument("--speakers", help="label who speaks (diarization): auto or a number; needs hf_token")
    a.add_argument("--language", default=LANGUAGE, help="he | en | auto (default from ~/.mce/config.json)")
    a.add_argument("--profile", default=PROFILE, choices=["general", "minecraft"],
                   help="minecraft adds HUD detection (health, menus, death screen)")
    a.set_defaults(fn=analyze)

    m = sub.add_parser("moment")
    m.add_argument("dir")
    m.add_argument("seconds", nargs="+")
    m.set_defaults(fn=moment)

    e = sub.add_parser("export")
    e.add_argument("plan")
    e.add_argument("-o", "--output")
    e.set_defaults(fn=export)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
