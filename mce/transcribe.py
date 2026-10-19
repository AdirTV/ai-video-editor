"""Hebrew transcription with word-level timestamps (WhisperX + ivrit.ai)."""
import gc

ASR_MODEL = "ivrit-ai/whisper-large-v3-turbo-ct2"

# Primes the decoder with spellings it should prefer; extend in vocab.txt.
DEFAULT_PROMPT = (
    "מיינקראפט, קריפר, אנדרמן, אנדר דרגון, הנדר, בלייז, פנינת אנדר, סטרונגהולד, "
    "יהלומים, נתריט, מגן, חרב, קשת, פורטל, ספאון, סרבייבל"
)


def transcribe(wav_path: str, prompt: str = DEFAULT_PROMPT, batch_size: int = 8) -> list[dict]:
    """Return segments: [{start, end, text, words: [{word, start, end, score}]}]."""
    import whisperx

    audio = whisperx.load_audio(wav_path)
    model = whisperx.load_model(
        ASR_MODEL, device="cpu", compute_type="int8", language="he",
        asr_options={"initial_prompt": prompt}, vad_options={"chunk_size": 10},
    )
    result = model.transcribe(audio, batch_size=batch_size, language="he", chunk_size=10)
    del model
    gc.collect()

    align_model, meta = whisperx.load_align_model(language_code="he", device="cpu")
    aligned = whisperx.align(result["segments"], align_model, meta, audio, "cpu",
                             return_char_alignments=False)
    segments = []
    for seg in aligned["segments"]:
        words = [
            {"word": w["word"], "start": round(w["start"], 2), "end": round(w["end"], 2),
             "score": round(w.get("score", 0), 2)}
            for w in seg.get("words", []) if "start" in w
        ]
        segments.append({"start": round(seg["start"], 2), "end": round(seg["end"], 2),
                         "text": seg["text"].strip(), "words": words})
    return segments
