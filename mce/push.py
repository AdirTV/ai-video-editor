"""Build a timeline spec, import it into the open Premiere project and finish it
there: per-clip effects, Film Impact transitions, cleanup and a preview render.

Extra spec fields (see timeline_xml for the rest):
  clip  "effects": [{"name": "Gaussian Blur", "props": {"Amount": 60}}]
  clip  "pop": "start" | "end" | "both"            -> Film Impact "Pop Motion"
  top   "transitions": [{"name": "Glitch", "track": 0, "t": 2.417, "dur": 0.25}]
  top   "replaces": "<sequence name to delete after import>"
  top   "project": "/abs/x.prproj" -> make sure that project is the active one before importing
  top   "auto_sfx": true   -> place sound effects from the SFX library (see mce/sfx.py)
  top   "music_playlist": {"songs": [{"file": "m1", "until": 30}, {"file": "m2"}], "xfade": null}
        -> songs back to back, crossfaded on alternating tracks (A fades out over B's entrance)
  top   "music_fit": {"hit": 2.417} -> start the song so a drop lands on that second (or true: best energy)
  top   "duck_music": true -> music lifts in speech pauses (or {"music_file", "under", "lift_db"})
  top   "limit_db": -2     -> Hard Limiter (max amplitude) on every audio clip
  top   "vo_lufs": -14     -> gain the voiceover clips (file key "vo_file", default "vo") to this loudness

  uv run python -m mce.push <spec.json> [--export out.mp4]
"""
import argparse
import json
from pathlib import Path

from .premiere import Client
from .timeline_xml import build


def _ok(res: str) -> bool:
    try:
        d = json.loads(res)
    except json.JSONDecodeError:
        return False
    d = d.get("data", d)
    return bool(d.get("verified") or d.get("outcome") == "verified" or d.get("imported") or d.get("deleted"))


def push(spec_path: str, export: str | None = None) -> None:
    spec = json.loads(Path(spec_path).read_text())
    if spec.get("vo_lufs"):
        from .loudness import normalize_vo
        print("Loudness:", normalize_vo(spec, spec.get("vo_file", "vo"), spec["vo_lufs"]))
    if spec.get("music_playlist"):
        from .music import apply_playlist
        pl = spec["music_playlist"]
        print("Music:\n  " + "\n  ".join(apply_playlist(spec, pl["songs"], pl.get("xfade"), pl.get("db", -20),
                                                           pl.get("end", "fade"))))
    elif spec.get("music_fit"):
        from .music import apply_fit
        print("Music:", apply_fit(spec, **({} if spec["music_fit"] is True else spec["music_fit"])))
    if spec.get("duck_music"):
        from .loudness import duck_music
        print("Ducking:", duck_music(spec, **({} if spec["duck_music"] is True else spec["duck_music"])))
    if spec.get("auto_sfx"):
        from .sfx import plan
        spec, report = plan(spec)
        print("\n".join(["SFX:"] + report))
    xml = Path(spec_path).with_suffix(".xml")
    xml.write_text(build(spec))
    c = Client()
    try:
        def call(tool, args, label):
            res = c.call(tool, args)
            print(("✓ " if _ok(res) else "✗ ") + label + ("" if _ok(res) else f"  → {res[:200]}"))
            return res

        if spec.get("project"):
            # several projects can be open (other sessions); never import into whichever happens to be active
            def project_info() -> dict:
                try:
                    d = json.loads(c.call("get_project_info", {}))
                    return d.get("data", d)
                except json.JSONDecodeError:  # no project open
                    return {}
            info = project_info()
            if Path(info.get("path", "")).resolve() != Path(spec["project"]).resolve():
                call("open_project", {"path": spec["project"]}, f"open {Path(spec['project']).name}")
                info = project_info()
                if Path(info.get("path", "")).resolve() != Path(spec["project"]).resolve():
                    raise SystemExit(f"active project is {info.get('path')}, not {spec['project']} — stopping")
        try:  # an older sequence with the same name would be the one activated and exported
            seqs = json.loads(c.call("list_sequences", {}))
            seqs = seqs.get("data", seqs) if isinstance(seqs, dict) else seqs
            if any(q.get("name") == spec["name"] for q in seqs) and spec.get("replaces") != spec["name"]:
                raise SystemExit(f"a sequence named '{spec['name']}' already exists — give this build a new "
                                 f"name (and \"replaces\": the old one)")
        except json.JSONDecodeError:
            pass
        import time
        t_import = time.time()
        call("import_fcp_xml", {"path": str(xml), "mode": "into_open_project"}, "import")
        # Premiere writes a "FCP Translation Results <date>.txt" (and pops a dialog) when it had to change
        # something on import — surface it instead of letting it hide in the bin
        for rep in sorted((Path.home() / "Documents").glob("FCP Translation Results*.txt")):
            if rep.stat().st_mtime >= t_import - 2:
                text = rep.read_text(encoding="utf-8-sig", errors="replace").strip()
                print(f"⚠️ Premiere translation report ({rep.name}):\n   " + text.replace("\n", "\n   "))
        call("set_active_sequence", {"sequence_id": spec["name"]}, f"activate {spec['name']}")
        seq = json.loads(c.call("get_active_sequence", {"track_type": "video", "clip_limit": 200}))
        seq = seq.get("data", seq)
        ids = {cl["name"]: cl["nodeId"] for t in seq["videoTracks"] for cl in t["clips"]}

        for track in spec["video"]:
            for clip in track:
                nid = ids.get(clip.get("name"))
                if not nid:
                    continue
                for fx in clip.get("effects", []):
                    call("apply_effect", {"node_id": nid, "effect_name": fx["name"]}, f"{fx['name']} → {clip['name']}")
                    for prop, val in fx.get("props", {}).items():
                        call("set_effect_property", {"node_id": nid, "effect_name": fx["name"],
                                                     "property_name": prop, "value": val}, f"  {prop}={val}")
                if clip.get("pop"):
                    call("add_transition_to_clip", {"node_id": nid, "transition_name": "Pop Motion",
                                                    "position": clip["pop"], "duration_seconds": 0.25},
                         f"Pop Motion ({clip['pop']}) → {clip['name']}")
        # Pro tip: a Hard Limiter at -2 dB maximum amplitude so nothing peaks. Premiere's
        # API can't add effects to the Mix track, so it goes on every audio clip; QA then
        # checks the true peak of the whole render.
        if spec.get("limit_db") is not None:
            aseq = json.loads(c.call("get_active_sequence", {"track_type": "audio", "clip_limit": 200}))
            aseq = aseq.get("data", aseq)
            for t_ in aseq.get("audioTracks", []):
                for cl in t_["clips"]:
                    call("apply_audio_effect", {"node_id": cl["nodeId"], "effect_name": "Hard Limiter"},
                         f"Hard Limiter → {cl['name']}")
                    res = call("set_effect_property", {"node_id": cl["nodeId"], "effect_name": "Hard Limiter",
                                                       "property_name": "Maximum Amplitude", "value": spec["limit_db"]},
                               f"  Maximum Amplitude={spec['limit_db']} dB")
                    if not _ok(res):
                        # a limiter left at an unverified amplitude silenced a whole render (2026-10-19):
                        # take it off again and rely on the pre-mastered voice + QA's true-peak check
                        call("remove_effect_by_name", {"node_id": cl["nodeId"], "effect_name": "Hard Limiter"},
                             f"  removed unverified Hard Limiter → {cl['name']}")
        for tr in spec.get("transitions", []):
            call("add_transition", {"transition_name": tr["name"], "track_index": tr.get("track", 0),
                                    "cut_point_seconds": tr["t"], "duration_seconds": tr.get("dur", 0.25)},
                 f"{tr['name']} @ {tr['t']} (V{tr.get('track', 0) + 1})")
        if spec.get("replaces"):
            call("delete_sequence", {"sequence_id": spec["replaces"]}, f"delete {spec['replaces']}")
            call("set_active_sequence", {"sequence_id": spec["name"]}, "re-activate")
        call("save_project", {}, "save project")
        if export:
            # Deleting a sequence can make Premiere switch timelines asynchronously;
            # confirm what is active right before rendering.
            call("set_active_sequence", {"sequence_id": spec["name"]}, "activate for export")
            active = json.loads(c.call("get_active_sequence", {"clip_limit": 1}))
            active = active.get("data", active).get("name")
            if active != spec["name"]:
                raise RuntimeError(f"refusing to export: active sequence is {active!r}")
            call("export_sequence", {"output_path": export, "overwrite": True}, f"export {export}")
            # Self-review before anyone else sees it: objective checks + full contact sheets.
            from .qa import check_render, check_spec, sheets
            print("QA:\n" + "\n".join(check_render(export) + check_spec(spec)))
            review = Path(spec_path).parent / "review" / Path(export).stem
            print("Review sheets:", *map(str, sheets(export, review)), sep="\n  ")
    finally:
        c.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("--export")
    a = p.parse_args()
    push(a.spec, a.export)
