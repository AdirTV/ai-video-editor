// Full-video renders (long-form / shorts as finished MP4s): H.264, opaque.
// Use with: npx remotion render <Comp> out.mp4 --config=remotion.video.config.ts
import { Config } from "@remotion/cli/config";

Config.setRspack(true);
Config.setVideoImageFormat("jpeg");
Config.setPixelFormat("yuv420p");
Config.setCodec("h264");
Config.setCrf(18);
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
