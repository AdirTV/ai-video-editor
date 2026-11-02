import { Folder } from "remotion";

// Each folder in src/projects/ that has an index.tsx exporting `Compositions` shows up in Studio
// under its own folder. src/projects/ is gitignored, so these stay on your machine.
const ctx = require.context("./projects", true, /^\.\/[a-z0-9-]+\/index\.tsx$/);

export const ProjectCompositions: React.FC = () => (
  <>
    {ctx.keys().map((key) => {
      const C = ctx(key).Compositions as React.FC | undefined;
      return C ? <Folder key={key} name={key.split("/")[1]}><C /></Folder> : null;
    })}
  </>
);

// Add-ons: ../plugins/<name>/remotion/index.tsx exporting `Compositions` (see plugins/README.md). Their modules
// load here, before any composition renders, so what they register (e.g. a caption font) is in place.
const plugins = require.context("../../plugins", true, /^\.\/[a-z0-9-]+\/remotion\/index\.tsx$/);
const pluginComps = plugins.keys().map((key) => [key.split("/")[1], plugins(key).Compositions as React.FC | undefined] as const);

export const PluginCompositions: React.FC = () => (
  <>{pluginComps.map(([name, C]) => (C ? <Folder key={name} name={name}><C /></Folder> : null))}</>
);
