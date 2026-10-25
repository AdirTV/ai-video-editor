"""Media Encoder exports: wait() must only return for a finished file, and push falls back to Premiere."""
import json

import pytest

from mce import ame, ff, push


@pytest.fixture
def clock(monkeypatch):
    t = {"now": 0.0}
    monkeypatch.setattr(ame.time, "time", lambda: t["now"])
    monkeypatch.setattr(ame.time, "sleep", lambda s: t.__setitem__("now", t["now"] + s))
    return t


def test_wait_returns_once_log_says_done_and_file_is_whole(tmp_path, monkeypatch, clock):
    out, log = tmp_path / "v.mp4", tmp_path / "AMEEncodingLog.txt"
    out.write_bytes(b"x" * 10)
    log.write_text("old entry: Successfully\n", encoding="utf-16")  # AME's log is UTF-16 with a BOM
    since = {log: log.stat().st_size}  # the old "Successfully" must not count
    monkeypatch.setattr(ame, "logs", lambda: [log])
    calls = {"n": 0}

    def dur(p):  # the MP4 index lands with the end of the render
        if calls["n"] < 3:
            raise ff.FFError("moov atom not found")
        return 60.0
    monkeypatch.setattr(ff, "duration", dur)

    def sleep(s):
        calls["n"] += 1
        clock["now"] += s
        if calls["n"] == 3:
            with open(log, "a", encoding="utf-16-le") as f:
                f.write(f" - Output File: {out}\n10/25/2026 : File Successfully Encoded\n")
    monkeypatch.setattr(ame.time, "sleep", sleep)
    ame.wait(out, 60.0, since, fps=60)
    assert calls["n"] == 3


def test_wait_raises_on_failed_encode(tmp_path, monkeypatch, clock):
    out, log = tmp_path / "v.mp4", tmp_path / "AMEEncodingLog.txt"
    log.write_text(f" - Output File: {out}\nEncoding Failed: could not read frame\n", encoding="utf-8")
    monkeypatch.setattr(ame, "logs", lambda: [log])
    with pytest.raises(RuntimeError, match="Failed"):
        ame.wait(out, 60.0, {})


def test_wait_does_not_accept_a_partial_file(tmp_path, monkeypatch, clock):
    # no log entry, file stopped growing but its index isn't written: stalls, never "done"
    out = tmp_path / "v.mp4"
    out.write_bytes(b"x" * 10)
    monkeypatch.setattr(ame, "logs", lambda: [])

    def dur(p):
        raise ff.FFError("moov atom not found")
    monkeypatch.setattr(ff, "duration", dur)
    with pytest.raises(RuntimeError, match="stopped writing"):
        ame.wait(out, 60.0, {}, stall_timeout=60)


def test_wait_gives_up_when_nothing_is_written(tmp_path, monkeypatch, clock):
    monkeypatch.setattr(ame, "logs", lambda: [])
    with pytest.raises(RuntimeError, match="didn't start"):
        ame.wait(tmp_path / "v.mp4", 60.0, {}, start_timeout=30)


class FakeClient:
    def __init__(self, queue_reply):
        self.queue_reply, self.tools = queue_reply, []

    def call(self, tool, args):
        self.tools.append(tool)
        return self.queue_reply if tool == "add_to_render_queue" else json.dumps({"verified": True})


SPEC = {"fps": 60, "video": [[{"start": 0, "in": 0, "out": 10.0}, {"start": 10.0, "in": 5, "out": 7, "speed": 2}]]}


def call_for(c):
    return lambda tool, args, label: c.call(tool, args)


def test_render_uses_media_encoder(tmp_path, monkeypatch):
    monkeypatch.setattr(ame, "use", lambda: True)
    monkeypatch.setattr(ame, "preset", lambda: "/p.epr")
    waited = {}
    monkeypatch.setattr(ame, "wait", lambda out, end, since, fps: waited.update(end=end, fps=fps))
    c = FakeClient(json.dumps({"data": {"accepted": True, "jobId": "7", "verified": False}}))
    push.render(c, call_for(c), SPEC, str(tmp_path / "v.mp4"))
    assert c.tools == ["clear_sequence_in_out", "add_to_render_queue"]
    assert waited == {"end": 11.0, "fps": 60.0}


def test_render_falls_back_to_premiere(tmp_path, monkeypatch):
    monkeypatch.setattr(ame, "use", lambda: True)
    monkeypatch.setattr(ame, "preset", lambda: "/p.epr")
    c = FakeClient(json.dumps({"success": False, "error": "Adobe Media Encoder not available"}))
    push.render(c, call_for(c), SPEC, str(tmp_path / "v.mp4"))
    assert c.tools[-1] == "export_sequence"


def test_render_direct_skips_media_encoder(tmp_path, monkeypatch):
    monkeypatch.setattr(ame, "use", lambda: True)
    c = FakeClient("")
    push.render(c, call_for(c), SPEC, str(tmp_path / "v.mp4"), direct=True)
    assert c.tools == ["export_sequence"]


def test_log_verdict_reads_utf16_log_after_offset(tmp_path, monkeypatch):
    out, log = tmp_path / "v.mp4", tmp_path / "AMEEncodingLog.txt"
    log.write_text(f" - Output File: {out}\nFile Successfully Encoded\n", encoding="utf-16")
    since = {log: log.stat().st_size}
    monkeypatch.setattr(ame, "logs", lambda: [log])
    assert ame._log_verdict(out, since) is None  # an older render of the same name doesn't count
    with open(log, "a", encoding="utf-16-le") as f:
        f.write(f" - Output File: {out}\nFile Successfully Encoded\n\nQueue Stopped\n")
    assert ame._log_verdict(out, since) == "ok"
