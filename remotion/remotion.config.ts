/**
 * Note: When using the Node.JS APIs, the config file
 * doesn't apply. Instead, pass options directly to the APIs (scripts/catalog.mts does).
 *
 * All configuration options: https://remotion.dev/docs/config
 */

import path from "node:path";
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
// The output file's extension picks the format, no flags needed:
//   out.mov  → transparent ProRes 4444 (an overlay for Premiere — graphics, captions)
//   out.webm → transparent VP9
//   out.mp4 (or no output path) → opaque H.264, for finished full-frame videos / previews
// Flags on the command line (--codec, --pixel-format, …) still override this.
const outArg = process.argv
  .slice(2)
  .find((a) => !a.startsWith("-") && /\.(mov|webm|mp4|mkv|m4v)$/i.test(a));
const ext = outArg?.split(".").pop()?.toLowerCase();
if (ext === "mov") {
  Config.setVideoImageFormat("png");
  Config.setPixelFormat("yuva444p10le");
  Config.setCodec("prores");
  Config.setProResProfile("4444");
} else if (ext === "webm") {
  Config.setVideoImageFormat("png");
  Config.setPixelFormat("yuva420p");
  Config.setCodec("vp9");
} else {
  Config.setVideoImageFormat("jpeg");
  Config.setPixelFormat("yuv420p");
  Config.setCodec("h264");
  Config.setCrf(18);
}
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
// Add-ons in ../plugins/<name>/remotion/ live outside this folder: let them find this folder's packages.
Config.overrideBundlerConfig((c) => ({
  ...c,
  resolve: { ...c.resolve, modules: [path.resolve("node_modules"), "node_modules"] },
}));
