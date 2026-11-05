"""push against a fake Premiere bridge: paths sent to Premiere, and stopping when a required step fails."""
import json
from pathlib import Path

import pytest

from mce import push as push_mod


class FakeBridge:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def call(self, tool, args=None, retry=True):
        self.calls.append((tool, args or {}))
        r = self.replies.get(tool, '{"verified": true}')
        return r(args or {}) if callable(r) else r

    def close(self):
        pass

    def tools_called(self):
        return [t for t, _ in self.calls]


def run(monkeypatch, tmp_path, replies, spec_arg="spec.json"):
    spec = {"name": "Test seq", "video": [], "audio": []}
    (tmp_path / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    bridge = FakeBridge(replies)
    monkeypatch.setattr(push_mod, "Client", lambda: bridge)
    monkeypatch.setattr(push_mod, "build", lambda spec: "<xmeml/>")
    monkeypatch.chdir(tmp_path)
    return bridge, lambda: push_mod.push(spec_arg, keep_edits=False)


SEQ = '{"name": "Test seq", "videoTracks": [], "audioTracks": []}'


@pytest.mark.parametrize("spec_arg", ["spec.json", "./spec.json"])
def test_relative_spec_sends_absolute_xml_path(monkeypatch, tmp_path, spec_arg):
    seen = {}

    def imp(args):
        seen["path"] = args["path"]
        return '{"imported": true}' if Path(args["path"]).is_file() else "FCP XML file not found on disk"
    bridge, go = run(monkeypatch, tmp_path, {"list_sequences": "[]", "import_fcp_xml": imp,
                                            "get_active_sequence": SEQ}, spec_arg)
    go()
    assert Path(seen["path"]).is_absolute()
    assert Path(seen["path"]) == (tmp_path / "spec.xml").resolve()


def test_failed_import_stops_before_dependent_steps(monkeypatch, tmp_path):
    bridge, go = run(monkeypatch, tmp_path, {"list_sequences": "[]",
                                            "import_fcp_xml": "Error: FCP XML file not found on disk"})
    with pytest.raises(SystemExit, match="FCP XML file not found on disk"):
        go()
    called = bridge.tools_called()
    assert "set_active_sequence" not in called and "get_active_sequence" not in called and "save_project" not in called


def test_non_json_reply_reports_the_original_error(monkeypatch, tmp_path):
    bridge, go = run(monkeypatch, tmp_path, {"list_sequences": "[]", "import_fcp_xml": '{"imported": true}',
                                            "get_active_sequence": "Error: no active sequence"})
    with pytest.raises(SystemExit, match="no active sequence"):
        go()
    assert "save_project" not in bridge.tools_called()


def test_json_error_reply_stops(monkeypatch, tmp_path):
    bridge, go = run(monkeypatch, tmp_path, {"list_sequences": "[]", "import_fcp_xml": '{"imported": true}',
                                            "get_active_sequence": '{"success": false, "error": "No active sequence"}'})
    with pytest.raises(SystemExit, match="No active sequence"):
        go()


def test_missing_spec_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit, match="spec not found"):
        push_mod.push("nope.json", keep_edits=False)


@pytest.mark.parametrize("reply, ok", [
    ('{"imported": true}', True), ('{"data": {"verified": true}}', True), ('{"verified": false}', False),
    ("Error: something", False), ("[]", False), ('"text"', False),
])
def test_ok(reply, ok):
    assert push_mod._ok(reply) is ok
