"""General multi-source timeline → FCP7 XML for Premiere (shorts, b-roll edits).

Spec (JSON), all times in seconds:
{
  "name": "...", "width": 1080, "height": 1920, "fps": 60,
  "files": {"vid": {"path": "/abs/a.mp4"}, "img": {"path": "/abs/b.png"}},
  "video": [                                  # one list per track, V1 first
    [{"file": "vid", "start": 0, "in": 81.3, "out": 82.6, "scale": 177.8, "x": 540, "y": 960,
      "speed": 1, "name": "hook grid"}]
  ],
  "audio": [                                  # one list per track, A1 first
    [{"file": "vid", "start": 0, "in": 0, "out": 2.4, "gain_db": -18, "stream": 1}]
  ],
  "markers": [{"t": 1.2, "type": "fx", "note": "..."}]
}
Audio clips: "fade_in"/"fade_out" seconds (relative to gain_db) for crossfades at jump cuts.
Scale is percent, x/y are the clip's center in sequence pixels (default: frame center).
Stills (png/jpg) can use any in/out.
"""
import json
import subprocess
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from .fcpxml import MARKER_LABELS, _crop, _gain, _motion, _speed

STILL_EXT = {".png", ".jpg", ".jpeg", ".psd", ".tif", ".tiff"}
STILL_DUR = 3600.0


def _probe(path: str) -> dict:
    data = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path],
        check=True, capture_output=True, text=True).stdout)
    still = Path(path).suffix.lower() in STILL_EXT
    v = next((s for s in data["streams"] if s["codec_type"] == "video" and not
              (s.get("disposition", {}).get("attached_pic"))), None)
    return {
        "still": still,
        "width": int(v["width"]) if v else None,
        "height": int(v["height"]) if v else None,
        "duration": STILL_DUR if still else float(data["format"]["duration"]),
        "fps": (lambda n, d: n / d)(*map(int, v["avg_frame_rate"].split("/"))) if v and not still else None,
        "audio": [{"channels": s.get("channels", 2), "rate": int(s.get("sample_rate", 48000))}
                  for s in data["streams"] if s["codec_type"] == "audio"],
    }


def build(spec: dict) -> str:
    fps = int(spec.get("fps", 60))
    W, H = spec.get("width", 1080), spec.get("height", 1920)
    rate = f"<rate><timebase>{fps}</timebase><ntsc>FALSE</ntsc></rate>"
    fr = lambda s: round(s * fps)

    def frate(f: dict) -> tuple[float, str]:
        """A file's own frame rate (59.94 sources keep NTSC timing) and its xmeml tag."""
        r = f.get("fps") or fps
        tb = round(r)
        return r, f"<rate><timebase>{tb}</timebase><ntsc>{'TRUE' if abs(r - tb) > 0.01 else 'FALSE'}</ntsc></rate>"
    files = {k: {**v, **_probe(v["path"])} for k, v in spec["files"].items()}
    written: set[str] = set()

    def file_xml(fid: str) -> str:
        if fid in written:
            return f'<file id="{fid}"/>'
        written.add(fid)
        f = files[fid]
        p = Path(f["path"]).resolve()
        r, frt = frate(f)
        video = (f"<video><samplecharacteristics>{frt}<width>{f['width']}</width><height>{f['height']}</height>"
                 "<pixelaspectratio>square</pixelaspectratio></samplecharacteristics></video>") if f["width"] else ""
        audio = "".join(f"<audio><samplecharacteristics><depth>16</depth><samplerate>{a['rate']}</samplerate>"
                        f"</samplecharacteristics><channelcount>{a['channels']}</channelcount></audio>"
                        for a in f["audio"])
        return (f'<file id="{fid}"><name>{escape(p.name)}</name><pathurl>file://{quote(str(p))}</pathurl>'
                f"{frt}<duration>{round(f['duration'] * r)}</duration><media>{video}{audio}</media></file>")

    n = 0

    def clip(c: dict, kind: str) -> tuple[str, int]:
        nonlocal n
        n += 1
        f = files[c["file"]]
        speed = float(c.get("speed", 1) or 1)
        dur = max(1, round(fr(c["out"] - c["in"]) / speed))
        start = fr(c["start"])
        cf, crate = frate(f)  # clip in/out/keyframes count source frames
        c_in = round(c["in"] * cf / speed)
        c_dur = round(dur * cf / fps)
        filters = ""
        if kind == "video":
            if c.get("crop"):
                filters += _crop(*c["crop"])
            # xmeml center = offset from frame center / source size (measured
            # by round-tripping Premiere's own XML export).
            nx = lambda x: (x - W / 2) / f["width"]
            ny = lambda y: (y - H / 2) / f["height"]
            # keys: [{"t": seconds from clip start, "scale", "x", "y"}]; <when> counts
            # source frames like <in> does.
            keys = [(c_in + round(k["t"] * cf), k.get("scale", c.get("scale", 100)),
                     nx(k.get("x", c.get("x", W / 2))), ny(k.get("y", c.get("y", H / 2))))
                    for k in c.get("keys", [])]
            filters += _motion(c.get("scale", 100), nx(c.get("x", W / 2)), ny(c.get("y", H / 2)), keys)
            if speed != 1:
                filters += _speed(speed * 100)
        else:
            if speed != 1:
                filters += _speed(speed * 100)
            if c.get("gain_db") or c.get("gain_keys") or c.get("fade_in") or c.get("fade_out"):
                # gain_keys: [[seconds from clip start, dB], ...] (e.g. music ducking)
                keys = [(c_in + round(t * cf), d) for t, d in c.get("gain_keys", [])]
                if not keys and (c.get("fade_in") or c.get("fade_out")):
                    # short fades relative to gain_db (jump-cut crossfades); -40 dB = silent
                    g, ln = c.get("gain_db", 0), (c["out"] - c["in"]) / speed
                    fi, fo = c.get("fade_in", 0), c.get("fade_out", 0)
                    pts = ([(0, g - 40), (fi, g)] if fi else [(0, g)]) + \
                          ([(ln - fo, g), (ln, g - 40)] if fo else [(ln, g)])
                    keys = [(c_in + round(t * cf), d) for t, d in pts]
                filters += _gain(c.get("gain_db", 0), keys)
        src = (f"<sourcetrack><mediatype>audio</mediatype><trackindex>{c.get('stream', 1)}</trackindex>"
               "</sourcetrack>") if kind == "audio" else ""
        name = escape(c.get("name") or Path(f["path"]).name)
        xml = (f'<clipitem id="{kind[0]}{n}"><name>{name}</name><enabled>TRUE</enabled>'
               f"<duration>{round(f['duration'] * cf / speed)}</duration>{crate}"
               f"<start>{start}</start><end>{start + dur}</end><in>{c_in}</in><out>{c_in + c_dur}</out>"
               f"{file_xml(c['file'])}{src}{filters}</clipitem>")
        return xml, start + dur

    end = 0

    def tracks(kind: str) -> str:
        nonlocal end
        out = ""
        for items in spec.get(kind, []):
            body = ""
            for c in sorted(items, key=lambda c: c["start"]):
                xml, e = clip(c, kind)
                body += xml
                end = max(end, e)
            extra = "<outputchannelindex>1</outputchannelindex>" if kind == "audio" else ""
            out += f"<track>{body}<enabled>TRUE</enabled><locked>FALSE</locked>{extra}</track>"
        return out

    video, audio = tracks("video"), tracks("audio")
    markers = "".join(
        f"<marker><name>{escape(MARKER_LABELS.get(m.get('type', 'note'), '📝'))}</name>"
        f"<comment>{escape(m.get('note', ''))}</comment><in>{fr(m['t'])}</in><out>-1</out></marker>"
        for m in spec.get("markers", []))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">'
        f'<sequence id="sequence-1"><name>{escape(spec.get("name", "auto edit"))}</name>'
        f"<duration>{end}</duration>{rate}"
        f"<timecode>{rate}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>"
        f"<media><video><format><samplecharacteristics>{rate}<width>{W}</width><height>{H}</height>"
        "<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance>"
        f"</samplecharacteristics></format>{video}</video>"
        "<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics>"
        "<depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>"
        f"{audio}</audio></media>{markers}</sequence></xmeml>\n"
    )
