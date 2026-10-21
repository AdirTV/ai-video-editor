# Graphics (Remotion)

Animated overlays rendered with transparency and layered into Premiere. Preview: `npm run dev`.

```
src/
  Root.tsx         shared compositions (preview defaults only — renders pass --props)
  schemas.ts       props + descriptions of every shared composition
  brand.ts         reads brand.json (channel, colours, logo)
  captions/        Captions: word groups, karaoke, keyword colours, RTL/LTR from the text
  text/            BigText, Sticker, Alarm
  promo/           CTA, YouTubeCard
  fx/              Morph, Frost, LightMeter, LottieFx
  maps/            RouteMap, FlightMap
  minecraft/       Advancement, ItemTooltip, SpeedrunTimer, YouDied
  projects/        your own per-video graphics — gitignored, auto-loaded (see projects/README.md)
public/
  mc/              Minecraft icons, advancement frames, map pieces, fonts (shared)
  core/            placeholders for previews (shared)
  brand/           your logo (local)
  lottie/          Lottie files fetched by `mce.lottie` (local)
  projects/<name>/ media for your own projects (local)
```

Render with alpha:

```console
npx remotion render <Comp> out.mov --props='<json>' --image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444
```

**[CATALOG.md](CATALOG.md)** shows every shared composition with a still, its props and a render command.
Props are zod schemas in `src/schemas.ts` (Studio shows them as fields; bad `--props` fail with the field name).
Colours, channel name, caption font and logo fall back to `brand.json` at the repo root (`src/brand.ts`).

A new shared component goes in the folder for its role, gets a schema + catalog entry in `src/schemas.ts` and a
`<Composition>` in `Root.tsx` with neutral defaults; then `npm run catalog` refreshes CATALOG.md and
`docs/gallery/`. Something built for a single video belongs in `src/projects/`.

Remotion is free for individuals and companies of up to 3 people; beyond that a [company license](https://remotion.pro) is needed.
