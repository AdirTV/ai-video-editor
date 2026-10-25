"""Read container metadata with ffprobe."""
from dataclasses import dataclass, field
from fractions import Fraction

from .ff import FFError, display_size, probe_json, rotation, stream_fps


@dataclass
class MediaInfo:
    path: str
    width: int
    height: int
    fps: Fraction
    duration: float
    audio_streams: list[dict] = field(default_factory=list)
    rotation: int = 0  # width/height are as shown; the stored frames are turned by this (phones)

    @property
    def fps_float(self) -> float:
        return float(self.fps)

    @property
    def is_wide(self) -> bool:
        """True for the side-by-side facecam+gameplay layout (e.g. 3840x1080)."""
        return self.width / self.height > 3.0


def probe(path: str) -> MediaInfo:
    data = probe_json(path)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    if video is None:
        raise FFError(f"{path} has no video stream")
    audio = [
        {
            "index": i,
            "channels": s.get("channels", 2),
            "sample_rate": int(s.get("sample_rate", 48000)),
            "title": s.get("tags", {}).get("title", ""),
        }
        # iPhone spatial audio (apple_apac) is a 2nd stream ffmpeg can't decode — not a separate source
        for i, s in enumerate(x for x in data["streams"] if x["codec_type"] == "audio")
        if s.get("codec_name") != "apple_apac"
    ]
    return MediaInfo(
        path=path,
        width=display_size(video)[0],
        height=display_size(video)[1],
        fps=stream_fps(video) or Fraction(30),
        duration=float(data["format"]["duration"]),
        audio_streams=audio,
        rotation=rotation(video),
    )
