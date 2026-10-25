import { config } from "@remotion/eslint-config-flat";

export default [
  // src/projects/ is personal, gitignored per-video work: not part of the shared lint
  { ignores: ["src/projects/**"] },
  ...config,
];
