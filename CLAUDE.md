# AI video editor (Premiere + Claude)

- **Installing for a user?** Follow `INSTALL_FOR_CLAUDE.md` step by step.
- **Editing?** The `video-edit` skill is the workflow (plus `sfx`, and `minecraft-edit` for Minecraft footage);
  tools live in `mce/` (`uv run python -m mce.<tool>`), graphics in `remotion/`. Health check:
  `uv run python setup/doctor.py`.
- Skills: edit them in `skills/` (path placeholders), then `uv run python setup/install_skills.py`. Keep them
  creator-neutral — one creator's taste goes in their `style.md`.
- Never hardcode machine paths in code — use `mce/config.py` (`~/.mce/config.json`). Code must run on Mac and
  Windows: open text files with `encoding="utf-8"`, run ffmpeg through `mce/ff.py` (checked errors, file URLs).
- Tests: `uv run pytest -q` (no media or Premiere needed) after changing `mce/`. Remotion: `npm run lint` in `remotion/`.
- Remotion: shared components by role in `remotion/src/*/`; one-video graphics go in `remotion/src/projects/<name>/`
  (gitignored, auto-loaded) — see `remotion/README.md`.
- `style.md`, `vocab.txt` and `brand.json` are the user's personal files (gitignored); `style.template*.md` and
  `brand.example.json` are the shared starts.
