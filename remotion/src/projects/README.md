# Your own projects

Per-video graphics that only make sense for one video live here, one folder per project:

```
src/projects/my-video/index.tsx      ← exports `Compositions` (a fragment of <Composition>s)
src/projects/my-video/Intro.tsx
public/projects/my-video/…           ← that video's images, music, voiceover
```

```tsx
import { Composition } from "remotion";
import { Intro } from "./Intro";

export const Compositions: React.FC = () => (
  <Composition id="MyVideoIntro" component={Intro} fps={60} width={1080} height={1920} durationInFrames={120} />
);
```

Studio picks the folder up on its own (folder names: lowercase letters, numbers, `-`).
Everything here except this README is gitignored — it stays on your machine.
Reuse the shared components (`../../captions/Captions`, `../../text/BigText`…) instead of copying them.
If you build something every editor could use, move it out into the shared folders and register it in `src/Root.tsx`.
