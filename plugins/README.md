# Add-ons

An add-on extends the editor for one kind of video (a game, a format) without being part of this repo.
Put each one in its own folder here — usually a clone of its own repo:

```
git clone <add-on repo> plugins/<name>
uv run python setup/install_skills.py
```

Everything in `plugins/` except this README is ignored by git, and `setup/update.py` pulls add-ons that are
git checkouts. What an add-on can ship (all optional):

| Path | What it does |
|---|---|
| `skills/<skill>/SKILL.md` | installed with the editor's skills (path placeholders like `{{MCE_HOME}}` work) |
| `remotion/index.tsx` | exports `Compositions` (a fragment of `<Composition>`s); Studio and renders load it. Import the editor's helpers as `../../../remotion/src/fonts` etc.; a caption font goes in `captionFonts` |
| `public/` | copied into `remotion/public/` by `install_skills.py` (images, fonts) |
| `mce_plugin.py` | Python hooks: an analysis profile (`--profile <name>`: HUD readings, transcription words) and extra sound-effect kinds — see `mce/plugins.py` |
