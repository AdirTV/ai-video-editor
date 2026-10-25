"""Pure helpers: gain headroom, SFX placement, retake matching."""
import pytest

from mce import headroom, retakes, sfx


def test_fit_gain_leaves_normal_clips_alone():
    s = {"files": {"a": {"path": "/x.wav"}}, "audio": [[{"file": "a", "gain_db": 4.0}]]}
    assert headroom.fit_gain(s) == []
    assert s["audio"][0][0]["file"] == "a"


def test_fit_gain_boosts_loud_requests(monkeypatch):
    monkeypatch.setattr(headroom, "_boosted", lambda p, st, b: f"/cache/boost{b}.wav")
    s = {"files": {"a": {"path": "/x.wav"}},
         "audio": [[{"file": "a", "gain_db": 14.0, "gain_keys": [[0, 14.0], [1, 10.0]]}]]}
    headroom.fit_gain(s)
    c = s["audio"][0][0]
    assert headroom._peak_db(c) <= headroom.MAX_CLIP_DB
    boost = 14.0 - c["gain_db"]
    assert s["files"][c["file"]]["path"] == f"/cache/boost{int(boost)}.wav"
    assert c["gain_keys"][1][1] == pytest.approx(10.0 - boost)


def test_end_pop_follows_speed(monkeypatch):
    monkeypatch.setattr(sfx, "_sample_peak", lambda p: -6.0)
    monkeypatch.setattr(sfx, "load_index", lambda lib: {"items": [
        {"path": "/sfx/pop.wav", "kind": "pop", "tags": "pop", "duration": 0.3, "peak": 0.0, "loudness": -12}]})
    s = {"files": {}, "video": [[{"file": "v", "start": 10.0, "in": 0.0, "out": 4.0, "speed": 2.0, "pop": "end"}]],
         "audio": []}
    out, _ = sfx.plan(s, lib=__import__("pathlib").Path("/sfx"))
    starts = [c["start"] for tr in out["audio"] for c in tr if "pop" in out["files"][c["file"]]["path"]]
    assert starts and starts[0] == pytest.approx(10.0 + 2.0 - 0.15, abs=0.05)


def tok(w: str) -> str:
    return retakes.norm(w)[0]


@pytest.mark.parametrize("a, b", [("שלום", "שלום,"), ("Hello", "hello!"), ("מלך", "מלכ"), ("והבית", "הבית"),
                                  ("שָׁלוֹם", "שלום")])
def test_retake_words_match(a, b):
    assert retakes.same(tok(a), tok(b))


def test_retake_numbers_normalize():
    assert retakes.norm("GTA6") == ["gta", "6"]


def test_retake_words_differ():
    assert not retakes.same(tok("שלום"), tok("להתראות"))
    assert not retakes.same(tok("cat"), tok("dog"))


# --- take check (stalls / drawn-out words) and audio tails -------------------------------------------------

def _env(spans: list[tuple[float, float, float]], dur: float, floor: float = -60.0):
    """Synthetic voice envelope: (start, end, level dB) spans over a quiet floor, HOP steps from t=0."""
    import numpy as np
    from mce import takecheck
    n = int(round(dur / takecheck.HOP))
    env = np.full(n, floor)
    for a, b, lvl in spans:
        env[int(a / takecheck.HOP):int(b / takecheck.HOP)] = lvl
    return env


def _w(*ws):
    return [{"word": w, "start": a, "end": b} for w, a, b in ws]


def test_takecheck_clean_take_has_no_flaws():
    from mce import takecheck
    words = _w(("I", 0.1, 0.25), ("really", 0.3, 0.6), ("need", 0.65, 0.9), ("your", 0.95, 1.1), ("help.", 1.15, 1.5))
    assert takecheck.flaws(words, _env([(0.1, 1.5, -18)], 1.7), 0.0) == []


def test_takecheck_flags_a_mid_sentence_stall():
    from mce import takecheck
    words = _w(("I", 0.1, 0.25), ("really", 0.3, 0.6), ("need", 0.65, 0.9), ("your", 1.4, 1.55), ("help.", 1.6, 1.9))
    env = _env([(0.1, 0.9, -18), (1.4, 1.9, -18)], 2.1)
    kinds = [f["kind"] for f in takecheck.flaws(words, env, 0.0)]
    assert "stall" in kinds


def test_takecheck_allows_a_pause_after_punctuation():
    from mce import takecheck
    words = _w(("Is", 0.1, 0.25), ("he", 0.3, 0.45), ("copying", 0.5, 0.8), ("me?", 0.85, 1.1),
               ("Just", 1.6, 1.8), ("kidding.", 1.85, 2.2))
    env = _env([(0.1, 1.1, -18), (1.6, 2.2, -18)], 2.4)
    assert takecheck.flaws(words, env, 0.0) == []


def test_takecheck_flags_a_drawn_out_word():
    from mce import takecheck
    words = _w(("so", 0.1, 0.3), ("I", 0.35, 0.5), ("must", 0.55, 1.9), ("win", 1.95, 2.2), ("this.", 2.25, 2.5))
    kinds = [f["kind"] for f in takecheck.flaws(words, _env([(0.1, 2.5, -18)], 2.7), 0.0)]
    assert kinds == ["drawn-out word"]


def test_trim_audio_tail_cuts_sound_past_the_picture():
    from mce.timeline_xml import trim_audio_tail
    s = {"video": [[{"file": "v", "start": 0, "in": 0, "out": 10}]],
         "audio": [[{"file": "a", "start": 9.0, "in": 0.0, "out": 2.0, "name": "SFX impact"},
                    {"file": "b", "start": 10.5, "in": 0.0, "out": 1.0, "name": "SFX late"}],
                   [{"file": "m", "start": 0, "in": 5.0, "out": 17.0, "name": "music"}]]}
    notes = trim_audio_tail(s)
    assert len(notes) == 3
    sfx_clip = s["audio"][0][0]
    assert sfx_clip["start"] + sfx_clip["out"] - sfx_clip["in"] == pytest.approx(10.0)
    assert sfx_clip["fade_out"] > 0
    assert [c["name"] for c in s["audio"][0]] == ["SFX impact"]   # the clip that starts after the end is gone
    assert s["audio"][1][0]["out"] == pytest.approx(15.0)   # in 5 + 10 s of picture


def test_check_spec_flags_overlay_past_the_base_picture():
    from mce.qa import check_spec
    s = {"fps": 60, "video": [[{"file": "v", "start": 0, "in": 0, "out": 10, "name": "face"}],
                              [{"file": "g", "start": 9, "in": 9, "out": 10.5, "name": "finale"}]]}
    assert any("finale" in x for x in check_spec(s))



def test_gfxcheck_finds_uncovered_edges():
    import numpy as np
    from mce.gfxcheck import gaps
    alpha = np.full((192, 270), 255, np.uint8)
    assert gaps(alpha) == []
    alpha[:, -5:] = 0              # a layer slid 5 px left: the right edge shows through
    assert gaps(alpha) == ["right"]
