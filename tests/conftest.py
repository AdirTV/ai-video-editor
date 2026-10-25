"""Shared fixtures. Tests run without media, ffmpeg or Premiere: probing is faked."""
import pytest

from mce import timeline_xml

FAKE_MEDIA = {
    "cam.mp4": {"width": 1920, "height": 1080, "fps": 59.94, "duration": 600.0, "audio": [{"channels": 2, "rate": 48000}]},
    "phone.mov": {"width": 1080, "height": 1920, "fps": 30.0, "duration": 120.0, "audio": [{"channels": 2, "rate": 48000}]},
    "game.mp4": {"width": 1920, "height": 1080, "fps": 60.0, "duration": 900.0, "audio": [{"channels": 2, "rate": 48000}]},
    "gfx.mov": {"width": 1920, "height": 1080, "fps": 60.0, "duration": 6.0, "audio": [], "alpha": True},
    "song.wav": {"width": None, "height": None, "fps": None, "duration": 200.0, "audio": [{"channels": 2, "rate": 48000}]},
}


@pytest.fixture(autouse=True)
def fake_probe(monkeypatch):
    def probe(path: str) -> dict:
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        return {"still": False, **FAKE_MEDIA[name]}
    monkeypatch.setattr(timeline_xml, "_probe", probe)
