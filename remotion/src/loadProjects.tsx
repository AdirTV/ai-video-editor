import { Folder } from "remotion";

// Each folder in src/projects/ that has an index.tsx exporting `Compositions` shows up in Studio
// under its own folder. src/projects/ is gitignored, so these stay on your machine.
const ctx = require.context("./projects", true, /^\.\/[a-z0-9-]+\/index\.tsx$/);

export const ProjectCompositions: React.FC = () => (
  <>
    {ctx.keys().map((key) => {
      const C: React.FC | undefined = ctx(key).Compositions;
      return C ? <Folder key={key} name={key.split("/")[1]}><C /></Folder> : null;
    })}
  </>
);
