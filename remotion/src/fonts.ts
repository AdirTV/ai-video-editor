import { loadFont as loadLocal } from "@remotion/fonts";
import { loadFont as loadCarlito } from "@remotion/google-fonts/Carlito";
import { loadFont as loadGveret } from "@remotion/google-fonts/GveretLevin";
import { loadFont as loadHeebo } from "@remotion/google-fonts/Heebo";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadKarantina } from "@remotion/google-fonts/Karantina";
import { loadFont as loadPixelify } from "@remotion/google-fonts/PixelifySans";
import { loadFont as loadRubik } from "@remotion/google-fonts/Rubik";
import { staticFile } from "remotion";

// Every font the shared graphics use, loaded once (each loadFont holds the render until the font is in).
// Hebrew + Latin wherever the font has both, so the same graphic works in either language.
// Fonts without Hebrew glyphs get a Hebrew-capable fallback in the family list.
const he: ("hebrew" | "latin")[] = ["hebrew", "latin"];

export const RUBIK = loadRubik("normal", { weights: ["500", "700", "900"], subsets: he }).fontFamily;
export const HEEBO = loadHeebo("normal", { weights: ["500", "600", "700", "800", "900"], subsets: he }).fontFamily;
export const KARANTINA = loadKarantina("normal", { weights: ["700"], subsets: he }).fontFamily;
export const GVERET = loadGveret("normal", { weights: ["400"], subsets: he }).fontFamily;
// Latin-only fonts: Hebrew falls back to Heebo glyph by glyph.
export const INTER = `${loadInter("normal", { weights: ["600", "800", "900"], subsets: ["latin"] }).fontFamily}, ${HEEBO}`;
export const CARLITO = `${loadCarlito("normal", { weights: ["700"], subsets: ["latin"] }).fontFamily}, ${HEEBO}`;
export const PIXELIFY = loadPixelify("normal", { weights: ["700"], subsets: ["latin"] }).fontFamily;

// Local Minecraft fonts in public/mc/. @remotion/fonts delays the render until they load and fails it
// (cancelRender) if a file is missing, instead of silently drawing a fallback font.
const local = (family: string, file: string) => {
  if (typeof document !== "undefined") loadLocal({ family, url: staticFile(file) });
  return family;
};
export const MINECRAFTIA = local("Minecraftia", "mc/Minecraftia.ttf");
export const MINECRAFT_TEN = local("MinecraftTen", "mc/MinecraftTen.ttf");
