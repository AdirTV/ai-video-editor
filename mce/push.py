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

Before rebuilding, changes made by hand in Premiere to the old sequence ("replaces", else
the same name) are pulled into the spec (mce/pull.py); after importing, the new sequence is
snapshotted so the next pull can tell hand edits apart. Clips get stable "id"s.

--export renders in Adobe Media Encoder when the export_via setting allows it (default: when installed —
a render there can't take Premiere down), else inside Premiere; --export-direct forces the latter.

  uv run python -m mce.push <spec.json> [--export out.mp4] [--export-direct] [--no-pull] [--force]
"""
import argparse
import copy
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


GROUP_STEPS = ("vo", "music", "sfx")
CLIP_LIMIT = 200  # clips read back per track: the bridge now rejects more than 200 (push warns if a track is longer)


def prepare(spec: dict, quiet: bool = False) -> tuple[dict, dict[str, str]]:
    """push's own steps on the spec (voice loudness, music, ducking, SFX). Returns the
    spec and {clip id: "vo" | "music" | "sfx"} for every clip a step created or changed,
    so pull can tell those apart from the spec's own clips."""
    say = (lambda *a: None) if quiet else print
    groups: dict[str, str] = {}
    n = 0

    def step(group, fn, files=()):
        nonlocal n
        before = {c["id"]: json.dumps(c, sort_keys=True) for k in ("video", "audio")
                  for tr in spec.get(k, []) for c in tr if c.get("id")}
        out = fn()
        for k in ("video", "audio"):
            for tr in spec.get(k, []):
                for c in tr:
                    if not c.get("id"):
                        n += 1
                        c["id"] = f"auto-{group}-{n}"
                        groups[c["id"]] = group
                    elif before.get(c["id"]) != json.dumps(c, sort_keys=True) or c.get("file") in files:
                        groups.setdefault(c["id"], group)
        return out

    if spec.get("vo_lufs"):
        from .loudness import normalize_vo
        say("Loudness:", step("vo", lambda: normalize_vo(spec, spec.get("vo_file", "vo"), spec["vo_lufs"]),
                                     {spec.get("vo_file", "vo")}))
    if spec.get("music_playlist"):
        from .music import apply_playlist
        pl = spec["music_playlist"]
        say("Music:\n  " + "\n  ".join(step("music", lambda: apply_playlist(
            spec, pl["songs"], pl.get("xfade"), pl.get("db", -20), pl.get("end", "fade")),
            {song["file"] for song in pl["songs"]})))
    elif spec.get("music_fit"):
        from .music import apply_fit
        say("Music:", step("music", lambda: apply_fit(spec, **({} if spec["music_fit"] is True else spec["music_fit"])),
                                  {(spec["music_fit"] if isinstance(spec["music_fit"], dict) else {}).get("music_file", "music")}))
    if spec.get("duck_music"):
        from .loudness import duck_music
        say("Ducking:", step("music", lambda: duck_music(spec, **({} if spec["duck_music"] is True else spec["duck_music"])),
                                    {(spec["duck_music"] if isinstance(spec["duck_music"], dict) else {}).get("music_file", "music")}))
    if spec.get("auto_sfx"):
        from .sfx import plan

        def sfx():
            nonlocal spec
            new, report = plan(spec)
            if new is not spec:
                spec.clear()
                spec.update(new)
            return report
        say("\n".join(["SFX:"] + step("sfx", sfx)))
    return spec, groups


def assign_ids(spec: dict) -> bool:
    """Stable ids on the spec's clips, so pull can find them again after Claude edits the spec."""
    used = {c.get("id") for k in ("video", "audio") for tr in spec.get(k, []) for c in tr}
    n, changed = 0, False
    for k in ("video", "audio"):
        for tr in spec.get(k, []):
            for c in tr:
                if not c.get("id"):
                    n += 1
                    while f"c{n}" in used:
                        n += 1
                    c["id"] = f"c{n}"
                    used.add(c["id"])
                    changed = True
    return changed


def push(spec_path: str, export: str | None = None, keep_edits: bool = True, force: bool = False,
         export_direct: bool = False) -> None:
    c = Client()
    try:
        def call(tool, args, label):
            res = c.call(tool, args)
            print(("✓ " if _ok(res) else "✗ ") + label + ("" if _ok(res) else f"  → {res[:200]}"))
            return res

        spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
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
        if keep_edits:
            # the editor may have changed the old sequence by hand: carry that into the spec before rebuilding
            from .pull import pull
            r = pull(spec_path, client=c, quiet=True)
            if r and r[1] and not force:
                raise SystemExit("stopping: some of your Premiere changes couldn't be placed in the spec (above) — "
                                 "fix the spec, or push with --force to drop them")
            spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
        if assign_ids(spec):
            Path(spec_path).write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
        spec, groups = prepare(spec)
        built = copy.deepcopy(spec)  # before headroom boosts swap files: what pull compares against
        xml = Path(spec_path).with_suffix(".xml")
        xml.write_text(build(spec), encoding="utf-8")
        replaces = spec.get("replaces")
        try:  # an older sequence with the same name would be the one activated and exported
            seqs = json.loads(c.call("list_sequences", {}))
            seqs = seqs.get("data", seqs) if isinstance(seqs, dict) else seqs
            exists = any(q.get("name") == spec["name"] for q in seqs)
            if exists and replaces != spec["name"]:
                raise SystemExit(f"a sequence named '{spec['name']}' already exists — give this build a new "
                                 f"name (and \"replaces\": the old one)")
            if replaces == spec["name"]:
                # same name: delete the old one *before* importing — after, a delete by name could hit the
                # new one (and on a first build there is nothing to delete)
                if exists:
                    call("delete_sequence", {"sequence_id": replaces}, f"delete old {replaces}")
                replaces = None
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
        long = [f"{k}{i + 1}" for k in ("video", "audio") for i, tr in enumerate(spec.get(k, [])) if len(tr) > CLIP_LIMIT]
        if long:
            print(f"⚠️ tracks with more than {CLIP_LIMIT} clips ({', '.join(long)}): effects past clip {CLIP_LIMIT} are not applied")
        seq = json.loads(c.call("get_active_sequence", {"track_type": "video", "clip_limit": CLIP_LIMIT}))
        seq = seq.get("data", seq)
        def node(ti, clip):  # by track + start: pieces of a razored clip share a name
            tracks = seq["videoTracks"]
            cands = [cl for cl in (tracks[ti]["clips"] if ti < len(tracks) else []) if cl.get("name") == clip.get("name")]
            best = min(cands, key=lambda cl: abs(cl["start"] - clip["start"]), default=None)
            return best["nodeId"] if best and abs(best["start"] - clip["start"]) < 0.05 else None

        for ti, track in enumerate(spec["video"]):
            for clip in track:
                nid = node(ti, clip)
                if not nid:
                    continue
                for fx in clip.get("effects", []):
                    call("apply_effect", {"node_id": nid, "effect_name": fx["name"]}, f"{fx['name']} → {clip.get('name', '?')}")
                    for prop, val in fx.get("props", {}).items():
                        call("set_effect_property", {"node_id": nid, "effect_name": fx["name"],
                                                     "property_name": prop, "value": val}, f"  {prop}={val}")
                if clip.get("pop"):
                    call("add_transition_to_clip", {"node_id": nid, "transition_name": "Pop Motion",
                                                    "position": clip["pop"], "duration_seconds": 0.25},
                         f"Pop Motion ({clip['pop']}) → {clip.get('name', '?')}")
        # Pro tip: a Hard Limiter at -2 dB maximum amplitude so nothing peaks. Premiere's
        # API can't add effects to the Mix track, so it goes on every audio clip; QA then
        # checks the true peak of the whole render.
        if spec.get("limit_db") is not None:
            aseq = json.loads(c.call("get_active_sequence", {"track_type": "audio", "clip_limit": CLIP_LIMIT}))
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
        if replaces:
            call("delete_sequence", {"sequence_id": replaces}, f"delete {replaces}")
            call("set_active_sequence", {"sequence_id": spec["name"]}, "re-activate")
        call("save_project", {}, "save project")
        try:
            from .pull import make_snapshot, read_live, snapshot_path
            snap = snapshot_path(spec_path, spec["name"])
            parsed = read_live(c, spec["name"], snap.with_suffix(".pushed.xml"))
            snap.write_text(json.dumps(make_snapshot(built, parsed, groups, spec["name"]), ensure_ascii=False), encoding="utf-8")
            if replaces:
                old = snapshot_path(spec_path, replaces)
                for f in (old, old.with_suffix(".pushed.xml"), old.with_suffix(".live.xml")):
                    f.unlink(missing_ok=True)
            print("✓ snapshot for pull")
        except (SystemExit, Exception) as e:  # never fail a push over this
            print(f"✗ snapshot for pull: {e}")
        if export:
            # Deleting a sequence can make Premiere switch timelines asynchronously;
            # confirm what is active right before rendering.
            call("set_active_sequence", {"sequence_id": spec["name"]}, "activate for export")
            active = json.loads(c.call("get_active_sequence", {"clip_limit": 1}))
            active = active.get("data", active).get("name")
            if active != spec["name"]:
                raise RuntimeError(f"refusing to export: active sequence is {active!r}")
            render(c, call, spec, export, direct=export_direct)
            # Self-review before anyone else sees it: objective checks + full contact sheets.
            from .qa import check_render, check_spec, sheets
            print("QA:\n" + "\n".join(check_render(export) + check_spec(spec)))
            review = Path(spec_path).parent / "review" / Path(export).stem
            print("Review sheets:", *map(str, sheets(export, review)), sep="\n  ")
    finally:
        c.close()


def seq_end(spec: dict) -> float:
    """Where the sequence ends: its last picture frame (audio tails are trimmed to it)."""
    return max((c["start"] + (c["out"] - c["in"]) / (c.get("speed") or 1)
                for tr in spec.get("video", []) for c in tr), default=0.0)


def render(c, call, spec: dict, export: str, direct: bool = False) -> None:
    """Media Encoder when allowed and installed (falling back to Premiere if the hand-over fails), else Premiere."""
    from . import ame
    preset = None if direct else (ame.use() and ame.preset())
    if not direct and not preset and ame.EXPORT_VIA == "ame":
        print("⚠️ export_via is \"ame\" but Adobe Media Encoder isn't installed: rendering inside Premiere")
    if preset:
        out = Path(export)
        out.unlink(missing_ok=True)  # AME renames instead of overwriting ("x_1.mp4")
        # AME renders in to out: stale marks would cut the render short
        call("clear_sequence_in_out", {}, "clear in/out marks")
        since = ame.log_sizes()
        res = c.call("add_to_render_queue", {"output_path": str(out), "preset_path": preset, "start_batch": True})
        try:
            d = json.loads(res)
            d = d.get("data", d)
        except (json.JSONDecodeError, AttributeError):
            d = {}
        # AME only takes the job: "accepted" with a job id is all Premiere can confirm (wait() checks the rest)
        if isinstance(d, dict) and d.get("accepted") and d.get("jobId"):
            print(f"✓ Media Encoder: rendering {out.name} (Premiere stays free)")
            ame.wait(out, seq_end(spec), since, fps=float(spec.get("fps", 30)))
            print(f"✓ export {export}")
            return
        print(f"⚠️ Media Encoder hand-over failed, rendering inside Premiere instead: {str(res)[:300]}")
    call("export_sequence", {"output_path": export, "overwrite": True}, f"export {export}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("spec")
    p.add_argument("--export")
    p.add_argument("--no-pull", action="store_true", help="don't carry hand edits from Premiere into the spec")
    p.add_argument("--force", action="store_true", help="push even if some hand edits couldn't be placed")
    p.add_argument("--export-direct", action="store_true", help="render inside Premiere, not in Media Encoder")
    a = p.parse_args()
    push(a.spec, a.export, keep_edits=not a.no_pull, force=a.force, export_direct=a.export_direct)
