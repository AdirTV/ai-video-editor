"""The transcription stack really decodes and transcribes, not just imports.

faster-whisper 1.2.1 + PyAV 19 broke on Windows at decode time ("open() got an unexpected keyword argument
'metadata_errors'") while `import faster_whisper` was fine — so these run the decode path itself.
"""
import wave

import numpy as np
import pytest


def _wav(path, seconds=1.0, rate=16000):
    t = np.arange(int(seconds * rate)) / rate
    pcm = (0.2 * np.sin(2 * np.pi * 440 * t) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    return path


def test_faster_whisper_decodes_a_file(tmp_path):
    from faster_whisper import decode_audio
    audio = decode_audio(str(_wav(tmp_path / "קובץ בדיקה.wav")), sampling_rate=16000)
    assert audio.dtype == np.float32
    assert abs(len(audio) - 16000) < 200


@pytest.mark.slow
def test_tiny_model_transcribes(tmp_path):
    """Downloads whisper 'tiny' (~75 MB) and runs it on a file path: the same decode + inference path as a real job."""
    from faster_whisper import WhisperModel
    model = WhisperModel("tiny", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(_wav(tmp_path / "tone.wav", seconds=3)), language="en")
    list(segments)  # transcription is lazy: run it
    assert info.duration == pytest.approx(3, abs=0.1)
