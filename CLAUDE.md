# AI video editor (Premiere + Claude)

- **Installing for a user?** Follow `INSTALL_FOR_CLAUDE.md` step by step.
- **Editing?** The `video-edit` skill is the workflow (plus `sfx`, and any skill an add-on in `plugins/` brings);
  tools live in `mce/` (`uv run python -m mce.<tool>`), graphics in `remotion/`. Health check:
  `uv run python setup/doctor.py`.
- Skills: edit them in `skills/` (path placeholders), then `uv run python setup/install_skills.py`. Keep them
  creator-neutral — one creator's taste goes in their `style.md`.
- Never hardcode machine paths in code — use `mce/config.py` (`~/.mce/config.json`). Code must run on Mac and
  Windows: open text files with `encoding="utf-8"`, run ffmpeg through `mce/ff.py` (checked errors, file URLs).
- Tests: `uv run pytest -q` (no media or Premiere needed) after changing `mce/`. `MCE_SLOW_TESTS=1` adds a real tiny-model transcription; tests marked `premiere` need Premiere open (`MCE_PREMIERE_TESTS=1`). Remotion: `npm run lint` in `remotion/`.
- Remotion: shared components by role in `remotion/src/*/`; one-video graphics go in `remotion/src/projects/<name>/`
  (gitignored, auto-loaded) — see `remotion/README.md`.
- `style.md`, `vocab.txt` and `brand.json` are the user's personal files (gitignored); `style.template*.md` and
  `brand.example.json` are the shared starts.
- Add-ons (`plugins/<name>/`, gitignored, each its own repo) extend the editor for one kind of video — see
  `plugins/README.md`. Keep this repo general: anything specific to one game or format belongs in an add-on.
- Helping one creator or one kind of creator (a style, a caption look, a graphic only they need)? It goes in their
  `style.md` / `brand.json` or in an add-on — never in this repo's `mce/`, `remotion/src/` or `skills/`, which every user gets.
