import { Composition } from "remotion";
import { z } from "zod";
import { Captions } from "./captions/Captions";
import { LottieFx } from "./fx/LottieFx";
import { Frost } from "./fx/Frost";
import { LightMeter } from "./fx/LightMeter";
import { Morph } from "./fx/Morph";
import { FlightMap } from "./maps/FlightMap";
import { ChatMessage } from "./stream/ChatMessage";
import { RouteMap } from "./maps/RouteMap";
import { Advancement } from "./minecraft/Advancement";
import { ItemTooltip } from "./minecraft/ItemTooltip";
import { SpeedrunTimer } from "./minecraft/SpeedrunTimer";
import { YouDied } from "./minecraft/YouDied";
import { CTA } from "./promo/CTA";
import { YouTubeCard } from "./promo/YouTubeCard";
import { Alarm } from "./text/Alarm";
import { BigText } from "./text/BigText";
import { Sticker } from "./text/Sticker";
import { TextPop } from "./text/TextPop";
import { WordCards, wordCardsMetadata } from "./text/WordCards";
import { ProjectCompositions } from "./loadProjects";
import { schemas, type Cap, type Props } from "./schemas";

// The shared graphics. Defaults are only for previewing in Studio; real renders pass --props.
// Your own per-video compositions go in src/projects/<name>/ (not committed), see src/projects/README.md.

const FPS = 60;

// duration from a "seconds" prop
const bySeconds = ({ props }: { props: { seconds?: number } }) => ({ durationInFrames: Math.ceil((props.seconds ?? 1) * FPS) });

// Studio validates props against the schema, CLI renders don't: check here so bad --props fail with the field name.
const checked = <P,>(id: string, schema: z.ZodType, then?: (a: { props: P }) => { durationInFrames: number }) =>
  ({ props }: { props: P }) => {
    const r = schema.safeParse(props);
    if (!r.success) {
      const issues = r.error.issues.map((i) => `${i.path.join(".") || "(props)"}: ${i.message}`).join("; ");
      throw new Error(`Bad props for ${id}: ${issues} (see remotion/CATALOG.md)`);
    }
    return then ? then({ props }) : {};
  };

// Without a transcript every line needs its time; with one (transcript: "projects/x/transcript.json") just the words.
const sampleCards = [
  { base: "כמה", script: "חברים", baseAt: 0.1, scriptAt: 0.35, scriptGlow: true, end: 1.1 },
  { base: "עולם", keyword: "מיינקראפט", script: "אחד", icon: "mc/Diamond.png", iconSide: "right" as const, baseAt: 1.15, keywordAt: 1.5, scriptAt: 1.9, end: 2.6 },
  { base: "ואז הבית", keyword: "התפוצץ", keyColor: "#FF5A1F", glitch: true, baseAt: 2.7, keywordAt: 3.0, end: 4.0 },
  { base: "זה התחיל כמו", keyword: "סרבייבל", script: "רגיל", theme: "cream" as const, baseAt: 4.1, keywordAt: 4.4, scriptAt: 4.8, end: 5.6 },
];
const checkedCards = (id: string) => async (a: { props: Props<"WordCards"> }) => {
  checked(id, schemas.WordCards)(a);
  return wordCardsMetadata(FPS)(a);
};

const sampleCaps: Cap[] = [
  { start: 0, end: 0.6, text: "ככה נראות" },
  { start: 0.6, end: 1.3, text: "הכתוביות", hl: { הכתוביות: "#FFD84D" } },
  { start: 1.3, end: 2, text: "with any language" },
];

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="Captions" component={Captions} schema={schemas.Captions} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ caps: sampleCaps, top: 980, size: 118, seconds: 2 }} calculateMetadata={checked("Captions", schemas.Captions, bySeconds)} />
      <Composition id="CTA" component={CTA} schema={schemas.CTA} durationInFrames={108} fps={FPS} width={1080} height={1920}
        defaultProps={{ label: "לסרטון המלא" }} calculateMetadata={checked("CTA", schemas.CTA)} />
      <Composition id="BigText" component={BigText} schema={schemas.BigText} durationInFrames={78} fps={FPS} width={1080} height={1920}
        defaultProps={{ text: "2027" }} calculateMetadata={checked("BigText", schemas.BigText)} />
      <Composition id="Sticker" component={Sticker} schema={schemas.Sticker} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ text: "חדש!", seconds: 1.2 }} calculateMetadata={checked("Sticker", schemas.Sticker, bySeconds)} />
      <Composition id="TextPop" component={TextPop} schema={schemas.TextPop} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ text: "איזה מטורף!", seconds: 2 }} calculateMetadata={checked("TextPop", schemas.TextPop, bySeconds)} />
      <Composition id="Alarm" component={Alarm} schema={schemas.Alarm} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ text: "זהירות!", seconds: 1.2 }} calculateMetadata={checked("Alarm", schemas.Alarm, bySeconds)} />
      <Composition id="Morph" component={Morph} schema={schemas.Morph} durationInFrames={60} fps={FPS} width={1080} height={1920}
        defaultProps={{ from: "mc/Creeper.webp", to: "mc/Axolotl.webp", swapAt: 23 }} calculateMetadata={checked("Morph", schemas.Morph)} />
      <Composition id="Frost" component={Frost} schema={schemas.Frost} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ grow: 1.2, tint: 0.22, seconds: 2 }} calculateMetadata={checked("Frost", schemas.Frost, bySeconds)} />
      <Composition id="LightMeter" component={LightMeter} schema={schemas.LightMeter} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ label: "רמת אור", warn: "חזק מדי!", fill: 0.9, seconds: 1.6 }} calculateMetadata={checked("LightMeter", schemas.LightMeter, bySeconds)} />
      <Composition id="LottieFx" component={LottieFx} schema={schemas.LottieFx} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ emoji: "😂", size: 420, seconds: 2 }} calculateMetadata={checked("LottieFx", schemas.LottieFx, bySeconds)} />
      <Composition id="YouTubeCard" component={YouTubeCard} schema={schemas.YouTubeCard} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 4.58, thumb: "core/thumb.png", title: "הסרטון המלא כבר בערוץ!", meta: "הועלה עכשיו", tapAt: 2.43 }} calculateMetadata={checked("YouTubeCard", schemas.YouTubeCard, bySeconds)} />
      <Composition id="YouDied" component={YouDied} schema={schemas.YouDied} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 1.6 }} calculateMetadata={checked("YouDied", schemas.YouDied, bySeconds)} />
      <Composition id="Advancement" component={Advancement} schema={schemas.Advancement} fps={FPS} width={1920} height={1080} durationInFrames={60}
        defaultProps={{ seconds: 3, text: "מצאת יהלומים", icon: "Diamond.png", frame: "challenge" as const, scale: 1 }}
        calculateMetadata={checked("Advancement", schemas.Advancement, bySeconds)} />
      <Composition id="AdvancementV" component={Advancement} schema={schemas.Advancement} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 3, text: "נסעת בעגלה", icon: "Minecart.png", frame: "task" as const, scale: 0.8, top: 260, side: "center" as const }}
        calculateMetadata={checked("AdvancementV", schemas.Advancement, bySeconds)} />
      <Composition id="ItemTooltip" component={ItemTooltip} schema={schemas.ItemTooltip} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 3, lines: [
          { text: "חרב יהלום" },
          { text: "", count: 120, prefix: "₪", color: "#FFAA00", at: 0.3 } ] }}
        calculateMetadata={checked("ItemTooltip", schemas.ItemTooltip, bySeconds)} />
      <Composition id="SpeedrunTimer" component={SpeedrunTimer} schema={schemas.SpeedrunTimer} fps={FPS} width={1920} height={1080} durationInFrames={60}
        defaultProps={{ seconds: 6, from: 0, to: 600, scale: 0.9, splits: [
          { label: "התחלה", at: 0 }, { label: "ברזל", at: 140 }, { label: "נת'ר", at: 380 }, { label: "סוף", at: 600 } ] }}
        calculateMetadata={checked("SpeedrunTimer", schemas.SpeedrunTimer, bySeconds)} />
      <Composition id="RouteMap" component={RouteMap} schema={schemas.RouteMap} fps={FPS} width={1920} height={1080} durationInFrames={60}
        defaultProps={{ seconds: 5, size: 900, stops: [
          { x: 0.15, y: 0.2, label: "בית" }, { x: 0.4, y: 0.5, label: "תחנה", icon: "Minecart.png" },
          { x: 0.82, y: 0.82, label: "יעד" } ] }}
        calculateMetadata={checked("RouteMap", schemas.RouteMap, bySeconds)} />
      <Composition id="FlightMap" component={FlightMap} schema={schemas.FlightMap} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 2.6 }} calculateMetadata={checked("FlightMap", schemas.FlightMap, bySeconds)} />
      <Composition id="ChatMessage" component={ChatMessage} schema={schemas.ChatMessage} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 3, user: "viewer_01", userColor: "#DAA520",
          parts: [{ text: "Greatest player of the year", at: 0 }, { text: "(only you play this game)", at: 1.2, big: true }] }}
        calculateMetadata={checked("ChatMessage", schemas.ChatMessage, bySeconds)} />
      <Composition id="WordCards" component={WordCards} schema={schemas.WordCards} fps={FPS} width={1920} height={1080} durationInFrames={60}
        defaultProps={{ cards: sampleCards }} calculateMetadata={checkedCards("WordCards")} />
      <Composition id="WordCardsV" component={WordCards} schema={schemas.WordCards} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ cards: sampleCards }} calculateMetadata={checkedCards("WordCardsV")} />
      <ProjectCompositions />
    </>
  );
};
