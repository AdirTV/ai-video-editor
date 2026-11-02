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

// A font file in remotion/public/ (e.g. one an add-on ships). @remotion/fonts delays the render until it
// loads and fails it (cancelRender) if the file is missing, instead of silently drawing a fallback font.
export const localFont = (family: string, file: string) => {
  if (typeof document !== "undefined") loadLocal({ family, url: staticFile(file) });
  return family;
};

// Fonts Captions can use by name (the `font` prop / brand.json captionFont). Add-ons in plugins/ add theirs:
// `captionFonts.myfont = { family: localFont("My Font", "x/My.ttf"), width: 0.6, weight: 400 }`.
// width = average glyph width (em), used to keep a caption on one line; weight overrides the look's weight.
export const captionFonts: Record<string, { family: string; width?: number; weight?: number }> = {
  rubik: { family: RUBIK },
  heebo: { family: HEEBO },
  // Calibri-metric font: the stream-clip / podcast-short caption look (Hebrew falls back to Heebo)
  carlito: { family: CARLITO },
};
