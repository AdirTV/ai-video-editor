# AI video editor (Premiere + Claude)

- **Installing for a user?** Follow `INSTALL_FOR_CLAUDE.md` step by step.
- **Editing?** The `minecraft-edit` and `sfx` skills explain the workflow; tools live in `mce/`
  (`uv run python -m mce.<tool>`), graphics in `remotion/`. Health check: `uv run python setup/doctor.py`.
- Never hardcode machine paths in code — use `mce/config.py` (`~/.mce/config.json`).
- Remotion: shared components by role in `remotion/src/*/`; one-video graphics go in `remotion/src/projects/<name>/`
  (gitignored, auto-loaded) — see `remotion/README.md`.
- `style.md` and `vocab.txt` are the user's personal files (gitignored); `style.template.md` is the shared start.
