"""Export an edit plan as FCP7 XML (xmeml v4), which Premiere Pro imports as an
editable sequence: real cuts on the original media, speed changes, facecam
layout, separate mic/game audio tracks and comment markers.

Edit plan (JSON):
{
  "source": "/abs/path/recording.mp4",
  "name": "My edit",
  "layout": "facecam_left" | "facecam_right" | "none",
  "cam": {"scale": 30, "x": 1592, "y": 878},      # facecam box: % scale, center in sequence px
  "audio": {"mic": 0, "game": 1},                  # audio stream indices in the source
  "game_audio_db": -8,
  "segments": [{"in": 12.0, "out": 40.5, "speed": 1, "keep_audio": true, "note": "...",
                "j": 0.3,     # J-cut: this segment's audio starts 0.3 s before its picture
                "l": 0.5}],   # L-cut: this segment's audio continues 0.5 s over the next picture
  "jump_cover": {"overlap": 0.12, "broll": ["/abs/b1.mp4"], "pre": 0.5, "post": 1.0},
                # cuts inside one take: overlapped audio on alternating tracks + B-roll on top
  "markers": [{"src": 123.4, "type": "broll", "note": "...", "dur": 0}]
}
Marker times are source seconds; they land on the timeline wherever that
moment ended up (markers on cut material are dropped).
"""
from pathlib import Path
from xml.sax.saxutils import escape

from .ff import pathurl
from .probe import MediaInfo

SEQ_W, SEQ_H = 1920, 1080
CAM_DEFAULT = {"scale": 30, "x": 1592, "y": 878}
class _Labels(dict):
    """Marker names in the current language (see i18n)."""

    def get(self, k, default=None):
        from .i18n import MSG, t
        return t("mk_" + k) if "mk_" + k in MSG else default


MARKER_LABELS = _Labels()


def _rate(info: MediaInfo) -> str:
    tb = round(info.fps_float)
    ntsc = "TRUE" if abs(info.fps_float - tb) > 0.01 else "FALSE"
    return f"<rate><timebase>{tb}</timebase><ntsc>{ntsc}</ntsc></rate>"


def _param(pid: str, value: str, name: str | None = None) -> str:
    return (f'<parameter authoringApp="PremierePro"><parameterid>{pid}</parameterid>'
            f"<name>{name or pid}</name><value>{value}</value></parameter>")


def _motion(scale: float, x: float, y: float, keys: list[tuple[int, float, float, float]] = (),
            rotation: float = 0) -> str:
    """Basic Motion. keys: (when_frame, scale, x, y) keyframes, same units as the statics.
    rotation: degrees clockwise (static)."""
    sk = "".join(f"<keyframe><when>{w}</when><value>{s:g}</value></keyframe>" for w, s, _, _ in keys)
    ck = "".join(f"<keyframe><when>{w}</when><value><horiz>{h:g}</horiz><vert>{v:g}</vert></value></keyframe>"
                 for w, _, h, v in keys)
    return ("<filter><effect><name>Basic Motion</name><effectid>basic</effectid>"
            "<effectcategory>motion</effectcategory><effecttype>motion</effecttype>"
            "<mediatype>video</mediatype>"
            + _param("scale", f"{scale:g}{sk}", "Scale").replace(f"<value>{scale:g}{sk}</value>", f"<value>{scale:g}</value>{sk}")
            + _param("center", f"<horiz>{x:g}</horiz><vert>{y:g}</vert>", "Center").replace("</value></parameter>", f"</value>{ck}</parameter>")
            + (_param("rotation", f"{rotation:g}", "Rotation") if rotation else "")
            + "</effect></filter>")


def _crop(left=0.0, right=0.0, top=0.0, bottom=0.0) -> str:
    return ("<filter><effect><name>Crop</name><effectid>crop</effectid>"
            "<effectcategory>motion</effectcategory><effecttype>motion</effecttype>"
            "<mediatype>video</mediatype>"
            + "".join(_param(k, f"{v:g}") for k, v in
                      (("left", left), ("right", right), ("top", top), ("bottom", bottom)))
            + "</effect></filter>")


def _speed(pct: float) -> str:
    return ("<filter><effect><name>Time Remap</name><effectid>timeremap</effectid>"
            "<effectcategory>motion</effectcategory><effecttype>motion</effecttype>"
            "<mediatype>video</mediatype>"
            + _param("variablespeed", "0") + _param("speed", f"{pct:g}")
            + _param("reverse", "FALSE") + _param("frameblending", "FALSE")
            + "</effect></filter>")


def _gain(db: float, keys: list[tuple[int, float]] = ()) -> str:
    """Audio level in dB, optionally keyframed: keys = (when_frame, dB)."""
    lin = lambda d: f"{10 ** (d / 20):.4f}"
    kf = "".join(f"<keyframe><when>{w}</when><value>{lin(d)}</value></keyframe>" for w, d in keys)
    return ("<filter><effect><name>Audio Levels</name><effectid>audiolevels</effectid>"
            "<effectcategory>audiolevels</effectcategory><effecttype>audiolevels</effecttype>"
            "<mediatype>audio</mediatype>"
            + _param("level", lin(db), "Level").replace("</parameter>", f"{kf}</parameter>")
            + "</effect></filter>")


def _file(info: MediaInfo, file_id: str, total: int) -> str:
    p = Path(info.path).resolve()
    audio = "".join(
        f"<audio><samplecharacteristics><depth>16</depth><samplerate>{a['sample_rate']}</samplerate>"
        f"</samplecharacteristics><channelcount>{a['channels']}</channelcount></audio>"
        for a in info.audio_streams
    )
    return (f'<file id="{file_id}"><name>{escape(p.name)}</name>'
            f"<pathurl>{pathurl(p)}</pathurl>{_rate(info)}<duration>{total}</duration>"
            f"<media><video><samplecharacteristics>{_rate(info)}<width>{info.width}</width>"
            f"<height>{info.height}</height><pixelaspectratio>square</pixelaspectratio>"
            f"</samplecharacteristics></video>{audio}</media></file>")


def build(plan: dict, info: MediaInfo) -> str:
    fps = info.fps_float
    rate = _rate(info)
    total = round(info.duration * fps)
    layout = plan.get("layout", "none") if info.is_wide else "none"
    cam = {**CAM_DEFAULT, **plan.get("cam", {})}
    streams = plan.get("audio", {"mic": 0, "game": 1})
    game_db = plan.get("game_audio_db", -8)
    if game_db > 6:  # Premiere clamps XML audio levels at +6 dB (Translation Report dialog)
        raise ValueError(f"game_audio_db {game_db} > +6 dB — Premiere would clamp it; boost the source instead")

    file_written = False

    def file_ref() -> str:
        nonlocal file_written
        if file_written:
            return '<file id="file-1"/>'
        file_written = True
        return _file(info, "file-1", total)

    # xmeml center = offset from frame center / source size (measured by
    # round-tripping Premiere's own XML export).
    kx, ky = 1 / info.width, 1 / info.height

    # Where the gameplay half / facecam half sit relative to the clip center.
    half_off = info.width / 4  # 960 for a 3840-wide source
    game_off = {"facecam_left": half_off, "facecam_right": -half_off}.get(layout, 0.0)
    cam_off = -game_off

    tracks: dict[str, list[str]] = {"v1": [], "v2": [], "v3": [], "a1": [], "a2": [], "a3": [], "a4": []}
    mapping = []  # (src_in, src_out, tl_start, speed) for marker placement
    tl = 0
    # J/L cuts: the audio boundary between segment k and k+1 moves by
    # shift = l(k) - j(k+1) seconds (>0: L-cut, k's sound runs over k+1's picture;
    # <0: J-cut, k+1's sound starts under k's picture). Only between 1x segments.
    segs = plan["segments"]
    shifts = [0.0] * (len(segs) + 1)  # shifts[n] = boundary after segment n (1-based)
    for k in range(1, len(segs)):
        a_, b_ = segs[k - 1], segs[k]
        if float(a_.get("speed", 1) or 1) == 1 and float(b_.get("speed", 1) or 1) == 1:
            shifts[k] = float(a_.get("l", 0)) - float(b_.get("j", 0))

    # Jump-cut cover (a pro editor's tip): where a chunk was cut out of one continuous
    # take, (1) the audio of the two sides goes on alternating tracks and overlaps
    # by `overlap` s each way with short fades, so the jump isn't heard, and (2) a
    # B-roll shot covers the cut from `pre` s before to `post` s after, so it isn't seen.
    cover = plan.get("jump_cover")
    cover = {} if cover is True else (cover or None)
    jump = [False] * (len(segs) + 1)  # jump[n] = jump cut after segment n
    if cover is not None:
        for k in range(1, len(segs)):
            a_, b_ = segs[k - 1], segs[k]
            if (float(a_.get("speed", 1) or 1) == 1 and float(b_.get("speed", 1) or 1) == 1
                    and not a_.get("l") and not b_.get("j") and abs(b_["in"] - a_["out"]) > 0.05):
                jump[k] = True
    ov = round(float((cover or {}).get("overlap", 0.12)) * fps)
    lane = 0  # flips at every jump cut: audio alternates between track pairs
    jump_cuts_tl: list[float] = []

    for n, seg in enumerate(plan["segments"], 1):
        speed = float(seg.get("speed", 1) or 1)
        src_in, src_out = round(seg["in"] * fps), round(seg["out"] * fps)
        dur = max(1, round((src_out - src_in) / speed))
        # Retimed clips express in/out in retimed media frames.
        c_in = round(src_in / speed)
        c_out = c_in + dur
        start, end = tl, tl + dur
        mapping.append((seg["in"], seg["out"], tl / fps, speed))
        name = escape(seg.get("note") or f"seg {n}")
        ids = {k: f"{k}-{n}" for k in tracks}
        keep_audio = seg.get("keep_audio", speed == 1)
        if n > 1 and jump[n - 1]:
            lane ^= 1
            jump_cuts_tl.append(start / fps)
        mic_key, game_key = ("a3", "a4") if lane else ("a1", "a2")
        active = ["v1"] + (["v2"] if layout != "none" else []) + ([mic_key, game_key] if keep_audio else [])
        links = "".join(
            f"<link><linkclipref>{ids[k]}</linkclipref>"
            f"<mediatype>{'video' if k.startswith('v') else 'audio'}</mediatype>"
            f"<trackindex>{int(k[1])}</trackindex><clipindex>{n}</clipindex></link>"
            for k in active
        )
        speed_f = _speed(speed * 100) if speed != 1 else ""

        def item(key: str, body: str, extra: str = "", lead: int = 0, tail: int = 0) -> str:
            # lead/tail (frames) extend an audio item before/after its picture.
            return (f'<clipitem id="{ids[key]}"><name>{name}</name><enabled>TRUE</enabled>'
                    f"<duration>{round(total / speed)}</duration>{rate}"
                    f"<start>{start - lead}</start><end>{end + tail}</end>"
                    f"<in>{c_in - lead}</in><out>{c_out + tail}</out>"
                    f"{file_ref()}{body}{speed_f}{extra}{links}</clipitem>")

        if layout == "none":
            tracks["v1"].append(item("v1", ""))
        else:
            crop_cam = (50, 0) if layout == "facecam_left" else (0, 50)
            tracks["v1"].append(item("v1", _crop(*crop_cam)
                                     + _motion(100, -game_off * kx, 0)))
            s = cam["scale"] / 100
            tracks["v2"].append(item("v2", _crop(*reversed(crop_cam))
                                     + _motion(cam["scale"], (cam["x"] - cam_off * s - SEQ_W / 2) * kx,
                                             (cam["y"] - SEQ_H / 2) * ky)))
        if keep_audio:
            # lead > 0: J-cut into this segment; tail > 0: L-cut out of it (negative
            # values trim this segment's audio to make room for the neighbour's).
            lead = round(-shifts[n - 1] * fps) if n > 1 else 0
            tail = round(shifts[n] * fps)
            jin, jout = n > 1 and jump[n - 1], jump[n]
            lead += ov if jin else 0   # overlap into the previous take's audio
            tail += ov if jout else 0  # and into the next one's
            lead = max(-dur + 1, min(lead, c_in))           # needs source handle before in
            tail = max(-dur + 1, min(tail, total - c_out))  # and after out
            for key, stream, gain in ((mic_key, streams.get("mic", 0), 0), (game_key, streams.get("game", 1), game_db)):
                if stream is None or stream >= len(info.audio_streams):
                    continue
                src_track = (f"<sourcetrack><mediatype>audio</mediatype>"
                             f"<trackindex>{stream + 1}</trackindex></sourcetrack>")
                fade = []
                if jin:   # fade in across the overlap
                    fade += [(c_in - lead, gain - 30), (c_in - lead + 2 * ov, gain)]
                if jout:  # fade out across the overlap
                    fade += [(c_out + tail - 2 * ov, gain), (c_out + tail, gain - 30)]
                lvl = _gain(gain, fade) if (gain or fade) else ""
                tracks[key].append(item(key, src_track, lvl, lead, tail))
        tl = end

    markers = []
    broll_files = (cover or {}).get("broll") or []
    pre, post = float((cover or {}).get("pre", 0.5)), float((cover or {}).get("post", 1.0))
    broll_defs: dict[str, dict] = {}
    for i, cut in enumerate(jump_cuts_tl):
        a_t, b_t = max(0.0, cut - pre), min(tl / fps, cut + post)
        if not broll_files:
            f = round(cut * fps)
            markers.append(f"<marker><name>{escape(MARKER_LABELS.get('broll', 'B-ROLL'))}</name>"
                           f"<comment>{escape(f'jump cut — cover {a_t:.2f}–{b_t:.2f}s with B-roll')}</comment>"
                           f"<in>{f}</in><out>-1</out></marker>")
            continue
        from .timeline_xml import _probe
        path = broll_files[i % len(broll_files)]
        info_b = broll_defs.setdefault(path, {**_probe(path), "id": f"broll-{len(broll_defs) + 1}", "written": False})
        bfps = info_b.get("fps") or fps
        length = b_t - a_t
        mid = max(0.0, info_b["duration"] / 2 - length / 2)
        b_in, b_dur = round(mid * bfps), round(length * fps)
        btb = round(bfps)
        brate = f"<rate><timebase>{btb}</timebase><ntsc>{'TRUE' if abs(bfps - btb) > 0.01 else 'FALSE'}</ntsc></rate>"
        if info_b["written"]:
            fref = f'<file id="{info_b["id"]}"/>'
        else:
            info_b["written"] = True
            pb = Path(path).resolve()
            fref = (f'<file id="{info_b["id"]}"><name>{escape(pb.name)}</name><pathurl>{pathurl(pb)}</pathurl>'
                    f"{brate}<duration>{round(info_b['duration'] * bfps)}</duration><media><video><samplecharacteristics>"
                    f"{brate}<width>{info_b['width']}</width><height>{info_b['height']}</height></samplecharacteristics>"
                    f"</video></media></file>")
        sc = max(SEQ_W / info_b["width"], SEQ_H / info_b["height"]) * 100
        tracks["v3"].append(
            f'<clipitem id="v3-b{i + 1}"><name>B-roll (jump cut)</name><enabled>TRUE</enabled>'
            f"<duration>{round(info_b['duration'] * bfps)}</duration>{brate}"
            f"<start>{round(a_t * fps)}</start><end>{round(a_t * fps) + b_dur}</end>"
            f"<in>{b_in}</in><out>{b_in + round(length * bfps)}</out>{fref}{_motion(sc, 0, 0, rotation=info_b.get("rot", 0))}</clipitem>")

    for m in plan.get("markers", []):
        t = _src_to_tl(m["src"], mapping)
        if t is None:
            continue
        f = round(t * fps)
        label = MARKER_LABELS.get(m.get("type", "note"), "📝")
        markers.append(f"<marker><name>{escape(label)}</name><comment>{escape(m.get('note', ''))}</comment>"
                       f"<in>{f}</in><out>{f + round(m.get('dur', 0) * fps) if m.get('dur') else -1}</out></marker>")

    def track(items: list[str], audio: bool = False) -> str:
        extra = "<outputchannelindex>1</outputchannelindex>" if audio else ""
        return f"<track>{''.join(items)}<enabled>TRUE</enabled><locked>FALSE</locked>{extra}</track>"

    video = track(tracks["v1"]) + (track(tracks["v2"]) if tracks["v2"] or tracks["v3"] else "") \
        + (track(tracks["v3"]) if tracks["v3"] else "")
    audio = track(tracks["a1"], True) + track(tracks["a2"], True) \
        + ((track(tracks["a3"], True) + track(tracks["a4"], True)) if tracks["a3"] or tracks["a4"] else "")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">'
        f'<sequence id="sequence-1"><name>{escape(plan.get("name", "auto edit"))}</name>'
        f"<duration>{tl}</duration>{rate}"
        f"<timecode>{rate}<string>00:00:00:00</string><frame>0</frame><displayformat>NDF</displayformat></timecode>"
        f"<media><video><format><samplecharacteristics>{rate}<width>{SEQ_W}</width><height>{SEQ_H}</height>"
        "<pixelaspectratio>square</pixelaspectratio><fielddominance>none</fielddominance>"
        f"</samplecharacteristics></format>{video}</video>"
        "<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics>"
        "<depth>16</depth><samplerate>48000</samplerate></samplecharacteristics></format>"
        f"{audio}</audio></media>{''.join(markers)}</sequence></xmeml>\n"
    )


def _src_to_tl(t: float, mapping) -> float | None:
    for src_in, src_out, tl_start, speed in mapping:
        if src_in <= t < src_out:
            return tl_start + (t - src_in) / speed
    return None
