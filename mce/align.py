"""Forced alignment: time the words of a known script against the recording.

Much more accurate than ASR timestamps when the text is known (a voiceover
script): ASR can mishear a word and shift a whole section. Works in any language
WhisperX has an aligner for (Hebrew, English, …).

  from mce.align import align_script
  words = align_script("vo.wav", [(0.3, 2.7, "Are they adding a new dimension?")], lang="en")
  → [{"word", "start", "end"}...] in source seconds

Words the aligner can't place (digits, symbols, other scripts) get times
interpolated from their neighbours, so numbers like "2027" still get a slot.
For best results spell numbers out in the script you pass (e.g. "twenty twenty
seven" / "אלפיים עשרים ושבע") and map back for display.
"""
import json
import sys

from .i18n import guess
from .transcribe import _device


def align_script(wav_path: str, clips: list[tuple[float, float, str]], lang: str | None = None) -> list[dict]:
    import whisperx

    audio = whisperx.load_audio(wav_path)
    lang = lang or guess(" ".join(c[2] for c in clips))
    model, meta = whisperx.load_align_model(language_code=lang, device=_device())
    out = []
    for a, b, text in clips:
        res = whisperx.align([{"start": a, "end": b, "text": text}], model, meta, audio, _device(),
                             return_char_alignments=False)
        words = [w for seg in res["segments"] for w in seg.get("words", [])]  # aligner splits sentences
        # Fill in words without timestamps by interpolating between placed neighbours.
        times = [(w.get("start"), w.get("end")) for w in words]
        for i, w in enumerate(words):
            if w.get("start") is None:
                prev_end = next((times[j][1] for j in range(i - 1, -1, -1) if times[j][1] is not None), a)
                next_start = next((times[j][0] for j in range(i + 1, len(times)) if times[j][0] is not None), b)
                w["start"], w["end"] = prev_end, next_start
                times[i] = (prev_end, next_start)
            out.append({"word": w["word"], "start": round(w["start"], 3), "end": round(w["end"], 3)})
    return out


if __name__ == "__main__":
    # uv run python -m mce.align <wav> '<json [[in, out, "text"], ...]>' [lang]
    clips = [tuple(c) for c in json.loads(sys.argv[2])]
    print(json.dumps(align_script(sys.argv[1], clips, sys.argv[3] if len(sys.argv) > 3 else None),
                     ensure_ascii=False, indent=1))
