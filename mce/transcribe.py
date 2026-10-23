"""Transcription with word-level timestamps (WhisperX), any language.

Hebrew uses ivrit.ai's fine-tuned Whisper (much better on Hebrew); every other
language uses Whisper large-v3-turbo. language="auto" detects it from the audio.

On Apple Silicon the same models run on the GPU through MLX (~6x faster than
CPU); elsewhere they run on CPU through WhisperX/CTranslate2.
"""
import gc
import platform
import sys

from .config import HF_TOKEN, LANGUAGE, PROFILE

MODELS = {"he": "ivrit-ai/whisper-large-v3-turbo-ct2"}
DEFAULT_MODEL = "large-v3-turbo"
MLX_MODELS = {"he": "mlx-community/ivrit-ai-whisper-large-v3-turbo-mlx"}
MLX_DEFAULT_MODEL = "mlx-community/whisper-large-v3-turbo"

# Prime the decoder with spellings it should prefer (game-specific profiles only).
PROMPTS = {
    ("minecraft", "he"): "מיינקראפט, קריפר, אנדרמן, אנדר דרגון, הנדר, בלייז, פנינת אנדר, סטרונגהולד, "
                         "יהלומים, נתריט, מגן, חרב, קשת, פורטל, ספאון, סרבייבל",
    ("minecraft", "en"): "Minecraft, Creeper, Enderman, Ender Dragon, Nether, Blaze, Ender Pearl, Stronghold, "
                         "diamonds, Netherite, shield, sword, bow, portal, spawn, survival",
}
DEFAULT_PROMPT = PROMPTS.get((PROFILE, "he"), "")  # kept for older callers

LAST_LANGUAGE = None  # language of the most recent transcription


def _use_mlx() -> bool:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return False
    try:
        import mlx_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _device() -> str:
    import torch
    return "mps" if torch.backends.mps.is_available() else "cpu"


def _asr_mlx(wav_path: str, lang: str, prompt: str) -> tuple[list[dict], str]:
    import mlx_whisper

    if lang == "auto":  # detect with the multilingual model, then use the language's own
        import mlx.core as mx
        from mlx_whisper.audio import N_FRAMES, log_mel_spectrogram, pad_or_trim
        from mlx_whisper.transcribe import ModelHolder

        model = ModelHolder.get_model(MLX_DEFAULT_MODEL, mx.float16)

        def one(clip):
            mel = pad_or_trim(log_mel_spectrogram(clip, n_mels=model.dims.n_mels), N_FRAMES, axis=-2)
            _, probs = model.detect_language(mel.astype(mx.float16))
            return max(probs, key=probs.get)

        import whisperx
        lang = _vote(whisperx.load_audio(wav_path), one)
    # No VAD here: hallucination_silence_threshold skips made-up text in long silences instead.
    result = mlx_whisper.transcribe(
        wav_path, path_or_hf_repo=MLX_MODELS.get(lang, MLX_DEFAULT_MODEL), language=lang,
        initial_prompt=prompt or None, condition_on_previous_text=False,
        word_timestamps=True, hallucination_silence_threshold=2.0,
    )
    segs = [{"start": s["start"], "end": s["end"], "text": s["text"]}
            for s in result["segments"] if s["text"].strip()]
    return segs, lang


def _vote(audio, detect_one, n: int = 12, sec: int = 30) -> str:
    """Majority language over n clips spread through the recording, skipping the quietest half.

    The first 30 s alone misleads on streams that open with music, a game intro or another language.
    """
    import numpy as np

    size = sec * 16000
    if len(audio) <= size:
        return detect_one(audio)
    starts = np.linspace(0, len(audio) - size, n).astype(int)
    loud = sorted(starts, key=lambda s: -float(np.sqrt(np.mean(audio[s:s + size] ** 2))))[:max(1, n // 2)]
    votes = [detect_one(audio[s:s + size]) for s in sorted(loud)]
    return max(set(votes), key=votes.count)


def detect_language(audio) -> str:
    import whisperx

    model = whisperx.load_model(DEFAULT_MODEL, device="cpu", compute_type="int8")
    lang = _vote(audio, model.detect_language)
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
    if lang == "auto" and not _use_mlx():
        lang = detect_language(audio)
    if prompt is None:
        prompt = PROMPTS.get((PROFILE, lang), "")

    if _use_mlx():
        raw, lang = _asr_mlx(wav_path, lang, prompt)
    else:
        model = whisperx.load_model(
            MODELS.get(lang, DEFAULT_MODEL), device="cpu", compute_type="int8", language=lang,
            asr_options={"initial_prompt": prompt or None}, vad_options={"chunk_size": 10},
        )
        raw = model.transcribe(audio, batch_size=batch_size, language=lang, chunk_size=10)["segments"]
        del model
        gc.collect()
    LAST_LANGUAGE = lang

    device = _device()
    align_model, meta = whisperx.load_align_model(language_code=lang, device=device)
    aligned = whisperx.align(raw, align_model, meta, audio, device, return_char_alignments=False)
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
    import whisperx
    from whisperx.diarize import DiarizationPipeline, assign_word_speakers

    device = _device()
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
