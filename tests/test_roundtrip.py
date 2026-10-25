"""timeline_xml.build → pull.parse must give back the spec: this is what lets hand edits survive a re-push."""
import pytest

from mce import pull, timeline_xml



def spec(fps):
    return {
        "name": "רצף בדיקה", "fps": fps, "width": 1080, "height": 1920,
        "files": {"cam": {"path": "/m/cam.mp4"}, "game": {"path": "/m/game.mp4"}, "song": {"path": "/m/song.wav"}},
        "video": [
            [{"file": "cam", "start": 0.0, "in": 10.0, "out": 14.5, "scale": 180, "x": 540, "y": 900},
             {"file": "game", "start": 4.5, "in": 100.0, "out": 106.0, "speed": 2.0},
             {"file": "cam", "start": 7.5, "in": 20.0, "out": 23.0,
              "keys": [{"t": 0, "scale": 100, "x": 540, "y": 960}, {"t": 1.5, "scale": 130, "x": 600, "y": 900}]}],
        ],
        "audio": [
            [{"file": "cam", "start": 0.0, "in": 10.0, "out": 14.5, "gain_db": 3.0},
             {"file": "game", "start": 4.5, "in": 100.0, "out": 106.0, "speed": 2.0, "gain_db": -6.0}],
            [{"file": "song", "start": 0.0, "in": 30.0, "out": 40.5, "gain_db": -20,
              "gain_keys": [[0, -20], [2, -28], [4, -20]]}],
        ],
    }


@pytest.mark.parametrize("fps", [60, 59.94, 30, 29.97, 25])
def test_build_parse_roundtrip(fps):
    s = spec(fps)
    FRAME = 1 / fps + 1e-4  # positions are quantized to sequence frames
    parsed = pull.parse(timeline_xml.build(s))
    assert parsed["fps"] == pytest.approx(fps, abs=0.01)
    for kind in ("video", "audio"):
        for want_track, got_track in zip(s[kind], parsed[kind]):
            assert len(want_track) == len(got_track)
            for want, got in zip(want_track, got_track):
                speed = want.get("speed", 1)
                assert got["start"] == pytest.approx(want["start"], abs=FRAME)
                assert got["in"] == pytest.approx(want["in"], abs=FRAME * speed)
                assert got["out"] == pytest.approx(want["out"], abs=FRAME * speed)
                assert got["speed"] == pytest.approx(speed)
                assert got["path"].endswith(s["files"][want["file"]]["path"].rsplit("/", 1)[-1])
                if kind == "video":
                    assert got["scale"] == pytest.approx(want.get("scale", 100))
                    assert got["x"] == pytest.approx(want.get("x", 540), abs=0.5)
                    assert got["y"] == pytest.approx(want.get("y", 960), abs=0.5)
                    for wk, gk in zip(want.get("keys", []), got.get("keys", [])):
                        assert gk["t"] == pytest.approx(wk["t"], abs=FRAME)
                        assert gk["scale"] == pytest.approx(wk["scale"])
                        assert gk["x"] == pytest.approx(wk["x"], abs=0.5)
                else:
                    assert got["gain_db"] == pytest.approx(want["gain_db"], abs=0.05)
                    for (wt, wd), (gt, gd) in zip(want.get("gain_keys", []), got.get("gain_keys", [])):
                        assert gt == pytest.approx(wt, abs=FRAME) and gd == pytest.approx(wd, abs=0.05)


@pytest.mark.parametrize("fps", [60, 29.97])
def test_back_to_back_clips_share_a_frame(fps):
    """Rounding start and length separately used to leave 1-frame black gaps at cuts."""
    s = {"fps": fps, "files": {"cam": {"path": "/m/cam.mp4"}},
         "video": [[{"file": "cam", "start": round(i * 1.237, 3), "in": i * 1.237, "out": (i + 1) * 1.237}
                    for i in range(20)]]}
    clips = pull.parse(timeline_xml.build(s))["video"][0]
    for a, b in zip(clips, clips[1:]):
        assert round((a["start"] + a["dur"]) * fps) == round(b["start"] * fps)


def test_ntsc_sequence_rate_tag():
    xml = timeline_xml.build({**spec(29.97), "video": [], "audio": []})
    assert "<timebase>30</timebase><ntsc>TRUE</ntsc>" in xml


def test_hebrew_names_survive():
    s = spec(60)
    s["video"][0][0]["name"] = "פתיח – שלום & ברוכים"
    parsed = pull.parse(timeline_xml.build(s))
    assert parsed["video"][0][0]["name"] == "פתיח – שלום & ברוכים"


def test_alpha_graphic_skips_its_last_frame():
    # Premiere can't read the last frame of alpha .movs ("Error retrieving frame 359 … substituting 358")
    s = {"name": "g", "fps": 60, "files": {"gfx": {"path": "/m/gfx.mov"}, "game": {"path": "/m/game.mp4"}},
         "video": [[{"file": "game", "start": 0, "in": 0, "out": 6.0}],
                   [{"file": "gfx", "start": 0, "in": 0, "out": 6.0}]], "audio": []}
    x = timeline_xml.build(s)
    assert "<in>0</in><out>359</out><file id=\"gfx\"" in x.replace("\n", "")
    assert "<in>0</in><out>360</out><file id=\"game\"" in x.replace("\n", "")


def test_xml_crop_is_not_an_added_effect(monkeypatch, tmp_path):
    # Premiere lists our XML crop as "Crop (Legacy)"; read as an added effect, push stacked a 2nd Crop on it
    import json
    s = spec(60)
    s["video"][0][0]["crop"] = [0, 50, 0, 0]
    x = timeline_xml.build(s)
    monkeypatch.setattr(pull, "export_live", lambda client, seq, dest: x)

    class Client:
        def call(self, tool, args):
            assert tool == "get_full_sequence_info"
            return json.dumps({"videoTracks": [{"index": 0, "clips": [
                {"startSeconds": 0.0, "nodeId": "n1", "effects": ["Motion", "Opacity", "Crop (Legacy)"]}]}]})

    live = pull.read_live(Client(), "seq", tmp_path / "live.xml")
    assert live["video"][0][0]["fx"] == {}
    assert live["video"][0][0]["crop"][1] == 50


def test_phone_clip_is_turned_upright_and_crop_follows(monkeypatch):
    # Premiere ignores the phone's rotation flag in FCP XML: the builder adds the turn itself, and a crop of
    # the picture as shown lands on the stored frame's matching side
    import re
    from mce import timeline_xml as tx
    monkeypatch.setitem(__import__("conftest").FAKE_MEDIA, "upright.mov",
                        {"width": 1080, "height": 1920, "fps": 30.0, "duration": 10.0, "audio": [], "rot": 90})
    s = {"name": "p", "fps": 30, "files": {"p": {"path": "/m/upright.mov"}}, "audio": [],
         "video": [[{"file": "p", "start": 0, "in": 0, "out": 2, "crop": [10, 0, 25, 0]}]]}
    x = tx.build(s)
    assert re.search(r"<parameterid>rotation</parameterid>.*?<value>90</value>", x, re.S)
    assert tx._stored_crop([10, 0, 25, 0], 90) == [25, 0, 0, 10]
    assert tx._stored_crop([10, 20, 30, 40], 0) == [10, 20, 30, 40]
