"""Read container metadata with ffprobe."""
import json
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass
class MediaInfo:
    path: str
    width: int
    height: int
    fps: Fraction
    duration: float
    audio_streams: list[dict] = field(default_factory=list)

    @property
    def fps_float(self) -> float:
        return float(self.fps)

    @property
    def is_wide(self) -> bool:
        """True for the side-by-side facecam+gameplay layout (e.g. 3840x1080)."""
        return self.width / self.height > 3.0


def probe(path: str) -> MediaInfo:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
        check=True, capture_output=True, text=True,
    ).stdout
    data = json.loads(out)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
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
        width=int(video["width"]),
        height=int(video["height"]),
        fps=Fraction(video["avg_frame_rate"]),
        duration=float(data["format"]["duration"]),
        audio_streams=audio,
    )
