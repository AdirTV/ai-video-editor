// Full-video renders (long-form / shorts as finished MP4s): H.264, opaque.
// Use with: npx remotion render <Comp> out.mp4 --config=remotion.video.config.ts
// (Not needed any more for plain .mp4 renders: remotion.config.ts picks H.264 from the .mp4 extension.)
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setPixelFormat("yuv420p");
Config.setCodec("h264");
Config.setCrf(18);
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
