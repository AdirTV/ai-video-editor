import { zColor } from "@remotion/zod-types";
import { z } from "zod";

// Props of every shared composition, in one place: Studio shows them as editable fields,
// Remotion validates --props against them, and scripts/catalog.mts turns them into CATALOG.md.
// Pure zod (no JSX) so plain Node can import it.

const seconds = z.number().positive().optional().describe("Length of the clip in seconds");
const lang = z.enum(["he", "en"]).optional().describe("Language of the built-in labels (default he)");
const color = zColor().optional();

export const capSchema = z.object({
  start: z.number().describe("Start (s from the start of the clip)"),
  end: z.number().describe("End (s)"),
  text: z.string(),
  hl: z.record(z.string(), z.string()).optional().describe('Word → colour, e.g. {"GTA": "#FFD84D"}'),
  size: z.number().optional().describe("Font size for this caption only (a punch word)"),
  words: z.array(z.number()).optional().describe("Karaoke: each word's start (s from cap start)"),
  big: z.array(z.string()).optional().describe("Karaoke: words drawn larger"),
  y: z.number().optional().describe("Karaoke: vertical centre of this caption (px)"),
  top: z.number().optional().describe("Other looks: this caption's top (px), overrides the global top"),
});

const point = z.object({ lon: z.number(), lat: z.number(), label: z.string() });

export const schemas = {
  Captions: z.object({
    caps: z.array(capSchema).describe("Caption groups with timings (mce.talkshort writes them as caps_props.json)"),
    top: z.number().optional().describe("Top of the caption line (px). Default 980"),
    size: z.number().optional().describe("Font size (px); long groups shrink to stay on one line. Default 118"),
    seconds,
    font: z.enum(["rubik", "heebo", "carlito", "minecraft"]).optional().describe("Default: brand.json captionFont, else rubik"),
    look: z.enum(["bold", "stream", "karaoke", "mc"]).optional().describe("Default: brand.json captionLook, else bold"),
    color: color.describe("Base text colour (highlights come from hl)"),
  }),
  CTA: z.object({
    label: z.string().describe('e.g. "לסרטון המלא"'),
    accent: color.describe("Pill and arrow colour. Default: brand accent"),
  }),
  BigText: z.object({
    text: z.string().describe('One huge word, e.g. "2027"'),
    color: color.describe("Default: brand accent"),
  }),
  Sticker: z.object({
    seconds,
    text: z.string(),
    bg: color.describe("Default: brand accent2"),
    color: color.describe("Text colour. Default #111"),
    top: z.number().optional().describe("px. Default 360"),
    size: z.number().optional().describe("px. Default 120"),
    tilt: z.number().optional().describe("Degrees. Default -6"),
  }),
  Alarm: z.object({ seconds, text: z.string().optional(), lang }),
  Morph: z.object({
    from: z.string().describe("Image under public/, e.g. mc/Creeper.webp"),
    to: z.string().describe("Image it turns into"),
    swapAt: z.number().describe("Frame of the swap (hidden by a flash + particles)"),
  }),
  Frost: z.object({
    seconds,
    grow: z.number().optional().describe("Seconds to full frost. Default 1.2"),
    tint: z.number().min(0).max(1).optional().describe("Cold tint strength. Default 0.22"),
  }),
  LightMeter: z.object({
    seconds, label: z.string().optional(), warn: z.string().optional(),
    fill: z.number().min(0).max(1).optional().describe("How full the meter gets. Default 0.9"), lang,
  }),
  LottieFx: z.object({
    seconds,
    src: z.string().optional().describe("Lottie JSON: URL or file under public/ (mce.lottie downloads to lottie/)"),
    emoji: z.string().optional().describe('Animated Noto emoji instead of src, e.g. "😂"'),
    size: z.number().optional().describe("px. Default 360"),
    x: z.number().optional(), y: z.number().optional().describe("Centre (px). Default: frame centre"),
    loop: z.boolean().optional(), speed: z.number().optional(), pop: z.boolean().optional(),
    rotate: z.number().optional().describe("Degrees"),
  }),
  YouTubeCard: z.object({
    seconds,
    thumb: z.string().describe("Thumbnail under public/"),
    title: z.string(),
    channel: z.string().optional().describe("Default: brand channel"),
    meta: z.string().describe('e.g. "הועלה עכשיו"'),
    tapAt: z.number().describe("Second at which the finger taps the video"),
    lang,
  }),
  YouDied: z.object({ seconds }),
  Advancement: z.object({
    seconds,
    title: z.string().optional().describe("Default by frame: הישג חדש / מטרה הושגה / אתגר הושלם"),
    text: z.string(),
    icon: z.string().describe("File in public/mc/, e.g. Diamond.png"),
    frame: z.enum(["task", "goal", "challenge"]).optional().describe("challenge = purple, the rare one"),
    scale: z.number().optional(), top: z.number().optional(),
    side: z.enum(["right", "left", "center"]).optional(), lang,
  }),
  ItemTooltip: z.object({
    seconds,
    lines: z.array(z.object({
      text: z.string(), color: color,
      count: z.number().optional().describe("Number that rolls up from 0 (a price)"),
      prefix: z.string().optional(), suffix: z.string().optional(),
      at: z.number().optional().describe("Second this line appears"),
    })),
    top: z.number().optional(), scale: z.number().optional(), tilt: z.number().optional(),
  }),
  SpeedrunTimer: z.object({
    seconds,
    title: z.string().optional(), category: z.string().optional().describe('e.g. "Any%"'),
    splits: z.array(z.object({ label: z.string(), at: z.number().describe("Run time (s) of this split") })),
    from: z.number().describe("Run clock at the start of the clip (s)"),
    to: z.number().describe("Run clock at the end (s) — a short clip can cover a long run"),
    scale: z.number().optional(), corner: z.enum(["tl", "tr"]).optional(),
  }),
  RouteMap: z.object({
    seconds,
    stops: z.array(z.object({
      x: z.number().min(0).max(1), y: z.number().min(0).max(1), label: z.string(),
      icon: z.string().optional().describe("File in public/mc/"),
    })).describe("Positions 0..1 inside the map"),
    upTo: z.number().optional().describe("Legs to draw (bring the same map back later showing more)"),
    fromLeg: z.number().optional(), size: z.number().optional(),
  }),
  FlightMap: z.object({
    seconds, size: z.number().optional(), top: z.number().optional(),
    from: point.optional(), to: point.optional(), km: z.number().optional().describe("Distance counter"),
  }),
};

export type Props<K extends keyof typeof schemas> = z.infer<(typeof schemas)[K]>;
export type Cap = z.infer<typeof capSchema>;

// What each composition is for, and which frame shows it best in the gallery (fraction of its length).
export const catalog: Record<string, { component: keyof typeof schemas; about: string; still?: number }> = {
  Captions: { component: "Captions", about: "Word-group captions: pop in/out, keyword colours, one line, RTL/LTR from the text. Looks: bold, stream, karaoke, mc." },
  CTA: { component: "CTA", about: "\"Watch the full video\" pill with a bouncing arrow, for the end of a short." },
  BigText: { component: "BigText", about: "One huge word that pops in with a tilt (a year, a number, a punch word).", still: 0.4 },
  Sticker: { component: "Sticker", about: "Tilted label with a hard shadow (\"חדש!\", a place name)." },
  Alarm: { component: "Alarm", about: "Pulsing red edges + a warning sign that slams in." },
  Morph: { component: "Morph", about: "A turns into B behind a flash and a poof of square particles.", still: 0.25 },
  Frost: { component: "Frost", about: "The screen freezes over from the edges.", still: 0.8 },
  LightMeter: { component: "LightMeter", about: "Minecraft-style light-level meter that fills up and goes red." },
  LottieFx: { component: "LottieFx", about: "A Lottie animation or an animated emoji placed on the frame." },
  YouTubeCard: { component: "YouTubeCard", about: "\"The full video is up\": the thumbnail on a YouTube watch page, tapped by a finger." },
  YouDied: { component: "YouDied", about: "Minecraft death screen after a hit flash.", still: 0.8 },
  Advancement: { component: "Advancement", about: "Minecraft \"Advancement Made!\" toast (landscape)." },
  AdvancementV: { component: "Advancement", about: "Same toast, placed for vertical video." },
  ItemTooltip: { component: "ItemTooltip", about: "Minecraft item tooltip used as a price tag; numbers roll up.", still: 0.7 },
  SpeedrunTimer: { component: "SpeedrunTimer", about: "LiveSplit-style speedrun timer with splits.", still: 0.7 },
  RouteMap: { component: "RouteMap", about: "Minecraft filled map that unfolds; a route draws stop to stop.", still: 0.9 },
  FlightMap: { component: "FlightMap", about: "Pixel world map with a flight arc and a km counter.", still: 0.9 },
};
