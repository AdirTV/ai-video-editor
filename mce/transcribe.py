"""Transcription with word-level timestamps (WhisperX), any language.

Hebrew uses ivrit.ai's fine-tuned Whisper (much better on Hebrew); every other
language uses Whisper large-v3-turbo. language="auto" detects it from the audio.
"""
import gc

from .config import HF_TOKEN, LANGUAGE, PROFILE

MODELS = {"he": "ivrit-ai/whisper-large-v3-turbo-ct2"}
DEFAULT_MODEL = "large-v3-turbo"

# Prime the decoder with spellings it should prefer (game-specific profiles only).
PROMPTS = {
    ("minecraft", "he"): "מיינקראפט, קריפר, אנדרמן, אנדר דרגון, הנדר, בלייז, פנינת אנדר, סטרונגהולד, "
                         "יהלומים, נתריט, מגן, חרב, קשת, פורטל, ספאון, סרבייבל",
    ("minecraft", "en"): "Minecraft, Creeper, Enderman, Ender Dragon, Nether, Blaze, Ender Pearl, Stronghold, "
                         "diamonds, Netherite, shield, sword, bow, portal, spawn, survival",
}
DEFAULT_PROMPT = PROMPTS.get((PROFILE, "he"), "")  # kept for older callers

LAST_LANGUAGE = None  # language of the most recent transcription


def detect_language(audio) -> str:
    import whisperx

    model = whisperx.load_model(DEFAULT_MODEL, device="cpu", compute_type="int8")
    lang = model.detect_language(audio)
    del model
    gc.collect()
    return lang


def transcribe(wav_path: str, prompt: str | None = None, batch_size: int = 8,
               language: str | None = None) -> list[dict]:
    """Return segments: [{start, end, text, words: [{word, start, end, score}]}]."""
    import whisperx

    global LAST_LANGUAGE
    audio = whisperx.load_audio(wav_path)
    lang = (language or LANGUAGE or "auto").lower()
    if lang == "auto":
        lang = detect_language(audio)
    LAST_LANGUAGE = lang
    if prompt is None:
        prompt = PROMPTS.get((PROFILE, lang), "")

    model = whisperx.load_model(
        MODELS.get(lang, DEFAULT_MODEL), device="cpu", compute_type="int8", language=lang,
        asr_options={"initial_prompt": prompt or None}, vad_options={"chunk_size": 10},
    )
    result = model.transcribe(audio, batch_size=batch_size, language=lang, chunk_size=10)
    del model
    gc.collect()

    align_model, meta = whisperx.load_align_model(language_code=lang, device="cpu")
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


DIARIZE_MODEL = "pyannote/speaker-diarization-community-1"


def diarize(wav_path: str, segments: list[dict], speakers: int | None = None) -> list[dict]:
    """Label who speaks: adds "speaker" ("S1", "S2"… in order of first appearance) to segments and words.

    Needs a free Hugging Face token (config `hf_token`, env HF_TOKEN or `hf auth login`) whose account
    accepted the terms of pyannote/speaker-diarization-community-1 on huggingface.co.
    """
    import torch
    import whisperx
    from whisperx.diarize import DiarizationPipeline, assign_word_speakers

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    try:
        pipe = DiarizationPipeline(DIARIZE_MODEL, token=HF_TOKEN, device=device)
    except Exception as e:  # gated model: no token / terms not accepted
        raise SystemExit(f"diarization unavailable ({e.__class__.__name__}): accept the terms at "
                         f"https://huggingface.co/{DIARIZE_MODEL} and set hf_token in ~/.mce/config.json") from e
    df = pipe(whisperx.load_audio(wav_path), num_speakers=speakers)
    out = assign_word_speakers(df, {"segments": segments}, fill_nearest=True)["segments"]
    names: dict[str, str] = {}
    for seg in out:
        for x in [seg, *seg.get("words", [])]:
            if "speaker" in x:
                x["speaker"] = names.setdefault(x["speaker"], f"S{len(names) + 1}")
    return out
