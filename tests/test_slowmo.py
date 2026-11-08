"""Frame math for RIFE slow motion / frame-rate conversion (no binary or media needed)."""
from fractions import Fraction
from pathlib import Path

import pytest

from mce import slowmo


@pytest.mark.parametrize("n, factor, want", [(120, 2, 240), (60, 4, 240), (60, 8, 480)])
def test_slowmo_multiplies_frames(n, factor, want):
    assert slowmo.target_frames(n, factor) == want


@pytest.mark.parametrize("n, src, out, want", [(60, 30, 60, 120), (120, 60, 120, 240), (48, 24, 60, 120),
                                                (60, 30000 / 1001, 60000 / 1001, 120)])
def test_fps_out_keeps_duration(n, src, out, want):
    assert slowmo.target_frames(n, 2, src, out) == want


def test_bad_requests():
    with pytest.raises(ValueError):
        slowmo.target_frames(1, 2)
    with pytest.raises(ValueError):
        slowmo.target_frames(60, 2, 60, 30)  # --fps-out must go up


def test_output_fps_and_name():
    assert slowmo.output_fps(Fraction(30)) == 30
    assert slowmo.output_fps(Fraction(30000, 1001), 59.94) == Fraction(60000, 1001)
    assert slowmo.default_output("/v/clip.mp4", 4) == Path("/v/clip_slowmo_x4.mov")
    assert slowmo.default_output("/v/clip.mp4", fps_out=60) == Path("/v/clip_60fps.mov")
    assert not slowmo.needs_v4(2, None) and slowmo.needs_v4(4, None) and slowmo.needs_v4(2, 60)


def test_missing_binary_message(monkeypatch, tmp_path):
    monkeypatch.setenv("MCE_RIFE", str(tmp_path / "nope"))
    assert slowmo.find_rife() is None
    with pytest.raises(SystemExit, match="rife-ncnn-vulkan not found"):
        slowmo.interpolate("x.mp4", 0, 1)
