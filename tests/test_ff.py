from fractions import Fraction

import pytest

from mce import ff


@pytest.mark.parametrize("raw, want", [
    ("30000/1001", Fraction(30000, 1001)),
    ("2987/100", Fraction(30000, 1001)),   # phone VFR average → 29.97
    ("60/1", Fraction(60)),
    ("5994/100", Fraction(60000, 1001)),
    ("25/1", Fraction(25)),
    ("24000/1001", Fraction(24000, 1001)),
])
def test_snap_fps(raw, want):
    assert ff.snap_fps(Fraction(raw)) == want


def test_snap_fps_keeps_unusual_rates():
    assert float(ff.snap_fps(Fraction(15))) == 15


def test_stream_fps_handles_missing_rate():
    assert ff.stream_fps({"avg_frame_rate": "0/0", "r_frame_rate": "30/1"}) == 30
    assert ff.stream_fps({"avg_frame_rate": "0/0", "r_frame_rate": "0/0"}) is None


@pytest.mark.parametrize("path", [
    r"C:\Users\אדיר\Desktop\editing\וידאו 1.mp4",
    r"D:\media\clip #1 (final).mov",
])
def test_windows_path_roundtrip(path):
    url = ff.pathurl(path, windows=True)
    assert url.startswith("file://localhost/C%3A/") or url.startswith("file://localhost/D%3A/")
    assert "%5C" not in url  # no encoded backslashes
    assert ff.url_to_path(url, windows=True) == path


def test_windows_url_written_by_premiere():
    url = "file://localhost/C%3a/Users/adir/Desktop/%D7%A9%D7%9C%D7%95%D7%9D.mp4"
    assert ff.url_to_path(url, windows=True) == r"C:\Users\adir\Desktop\שלום.mp4"


def test_mac_path_roundtrip(tmp_path):
    p = tmp_path / "עריכה" / "clip 1.mp4"
    url = ff.pathurl(str(p), windows=False)
    assert url.startswith("file:///")
    assert ff.url_to_path(url, windows=False) == str(p.resolve())
    assert ff.url_to_path(url.replace("file:///", "file://localhost/"), windows=False) == str(p.resolve())


def test_run_reports_missing_binary():
    with pytest.raises(ff.FFError, match="isn't installed"):
        ff.run(["definitely-not-ffmpeg-xyz", "-i", "a.mp4"])


def test_phone_rotation_and_display_size():
    # iPhone portrait clip: stored 1920x1080, display matrix -90 (= turn 90° clockwise to show)
    s = {"width": 1920, "height": 1080, "side_data_list": [{"side_data_type": "Display Matrix", "rotation": -90}]}
    assert ff.rotation(s) == 90
    assert ff.display_size(s) == (1080, 1920)
    assert ff.rotation({"width": 1920, "height": 1080, "tags": {"rotate": "90"}}) == 90
    assert ff.rotation({"width": 1920, "height": 1080}) == 0
    assert ff.display_size({"width": 1920, "height": 1080}) == (1920, 1080)
