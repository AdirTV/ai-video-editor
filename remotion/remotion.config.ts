/**
 * Note: When using the Node.JS APIs, the config file
 * doesn't apply. Instead, pass options directly to the APIs (scripts/catalog.mts does).
 *
 * All configuration options: https://remotion.dev/docs/config
 */

import { Config } from "@remotion/cli/config";

Config.setRspack(true);
// Every graphic is an overlay for Premiere: render transparent ProRes 4444 by default,
// so `npx remotion render <Comp> out.mov --props=…` needs no extra flags.
Config.setVideoImageFormat("png");
Config.setPixelFormat("yuva444p10le");
Config.setCodec("prores");
Config.setProResProfile("4444");
Config.setOverwriteOutput(true);
Config.setDefaultPremountInSeconds(2);
