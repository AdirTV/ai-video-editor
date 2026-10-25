import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";
import { dir, norm } from "../lang";
import { CARLITO, HEEBO, MINECRAFTIA, RUBIK } from "../fonts";
import { brand } from "../brand";
import type { Cap, Props } from "../schemas";

const FONTS = {
  rubik: RUBIK,
  heebo: HEEBO,
  // Calibri-metric font: the stream-clip / podcast-short caption look (Hebrew falls back to Heebo)
  carlito: CARLITO,
  // Minecraft pixel font (the "Minecraft, but…" short-channel caption look); a missing file fails the render
  minecraft: MINECRAFTIA,
};
// Average glyph width per font (em), used to keep a caption on one line.
const WIDTH: Record<string, number> = { minecraft: 0.66 };
type Font = keyof typeof FONTS;

// Highlight colour of a word: hl keys and words are compared without punctuation/niqqud/case,
// so {"GTA": …} also colours "GTA," and "gta!".
const hlColor = (hl: Cap["hl"], w: string) => {
  if (!hl) return undefined;
  if (hl[w]) return hl[w];
  const k = norm(w);
  if (!k) return undefined;
  for (const [key, c] of Object.entries(hl)) if (norm(key) === k) return c;
  return undefined;
};

export type { Cap } from "../schemas";

// "bold": white, thick black stroke + drop (default). "stream": white, thin navy outline, soft pop
// (the clip-channel look: game on top, face below, captions on the seam).
type Look = "bold" | "stream" | "karaoke" | "mc";
const LOOKS = {
  bold: { color: "white", stroke: "#111", strokeK: 0.15, shadow: () => "0 10px 0 #111", weight: 900, pop: 1 },
  karaoke: { color: "white", stroke: "#000", strokeK: 0.11, shadow: (s: number) => `0 ${Math.round(s * 0.05)}px ${Math.round(s * 0.1)}px rgba(0,0,0,.75)`, weight: 700, pop: 0.15 },
  // Minecraft-short look: pixel font, white, hard black outline + hard drop shadow
  mc: { color: "white", stroke: "#000", strokeK: 0.14, shadow: (s: number) => `${Math.round(s * 0.07)}px ${Math.round(s * 0.07)}px 0 #000`, weight: 900, pop: 0.6 },
  stream: { color: "white", stroke: "#0B1B2E", strokeK: 0.09, shadow: (s: number) => `0 ${Math.round(s * 0.04)}px ${Math.round(s * 0.08)}px rgba(0,0,0,.6)`, weight: 700, pop: 0.35 },
};

const Word: React.FC<{ cap: Cap; frames: number; size: number; font: Font; look: Look; color?: string }> = ({
  cap, frames, size, font, look, color,
}) => {
  const frame = useCurrentFrame();
  const L = LOOKS[look];
  const base = color ?? L.color;
  const pop = 1 + (popScale(frame, frames) - 1) * L.pop;
  return (
    <div
      style={{
        fontFamily: FONTS[font],
        fontWeight: font === "minecraft" ? 400 : L.weight,  // the pixel font has one weight
        // Always one line: shrink long groups to fit the safe width.
        fontSize: Math.min(cap.size ?? size, 940 / (cap.text.length * (WIDTH[font] ?? 0.56))),
        lineHeight: 1.05,
        textAlign: "center",
        whiteSpace: "nowrap",
        direction: dir(cap.text),
        unicodeBidi: "plaintext",
        color: base,
        WebkitTextStroke: `${Math.round((cap.size ?? size) * L.strokeK)}px ${L.stroke}`,
        paintOrder: "stroke fill",
        textShadow: L.shadow(cap.size ?? size),
        scale: pop,
        opacity: popOpacity(frame, frames),
      }}
    >
      {cap.text.split(" ").map((w, i) => (
        <span key={i} style={{ color: hlColor(cap.hl, w) ?? base }}>
          {(i ? " " : "") + w}
        </span>
      ))}
    </div>
  );
};

// Clip-channel karaoke: the phrase is shown whole on up to two balanced lines; words not yet said are dim,
// each turns white as it is spoken; "big" words are drawn ~1.5x.
const SPOKEN = "white";
const UPCOMING = 0.45;  // opacity of words not yet said (fill and outline fade together -> light grey)
const lines = (ws: string[]): string[][] => {
  const total = ws.join(" ").length;
  if (total <= 15 || ws.length < 2) return [ws];
  let best = 1, diff = 1e9;
  for (let i = 1; i < ws.length; i++) {
    const d = Math.abs(ws.slice(0, i).join(" ").length - ws.slice(i).join(" ").length);
    if (d < diff) { diff = d; best = i; }
  }
  return [ws.slice(0, best), ws.slice(best)];
};

const Karaoke: React.FC<{ cap: Cap; frames: number; size: number; font: Font }> = ({ cap, frames, size, font }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const L = LOOKS.karaoke;
  const ws = cap.text.split(" ");
  const big = new Set(cap.big ?? []);
  const t = frame / fps;
  const pop = 1 + (popScale(frame, frames) - 1) * L.pop;
  let k = 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", scale: pop,
      opacity: popOpacity(frame, frames), direction: dir(cap.text), unicodeBidi: "plaintext" }}>
      {lines(ws).map((ln, li) => {
        const chars = ln.reduce((n, w) => n + w.length * (big.has(w) ? 1.5 : 1), 0) + ln.length - 1;
        const fs = Math.min(size, 960 / (chars * 0.5));  // each line fits the safe width
        return (
          <div key={li} style={{ fontFamily: FONTS[font], fontWeight: L.weight, fontSize: fs, lineHeight: 1.08,
            whiteSpace: "nowrap", unicodeBidi: "plaintext", WebkitTextStroke: `${Math.round(fs * L.strokeK)}px ${L.stroke}`,
            paintOrder: "stroke fill", textShadow: L.shadow(fs) }}>
            {ln.map((w, i) => {
              const at = cap.words?.[k++] ?? 0;
              return (
                <span key={i} style={{ color: hlColor(cap.hl, w) ?? SPOKEN, opacity: t >= at ? 1 : UPCOMING,
                  fontSize: big.has(w) ? "1.5em" : undefined }}>
                  {(i ? " " : "") + w}
                </span>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

// Word-group captions, centred a bit below the middle of a 9:16 frame (top/size override per short).
export const Captions: React.FC<Props<"Captions">> = ({ caps, top = 980, size = 118, font = brand.captionFont as Font, look = brand.captionLook as Look, color }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      {caps.map((c, i) => {
        const from = Math.round(c.start * fps);
        const frames = Math.round(c.end * fps) - from;
        return (
          <Sequence key={i} from={from} durationInFrames={frames} name={c.text}>
            {look === "karaoke" ? (
              <AbsoluteFill style={{ alignItems: "center" }}>
                <div style={{ position: "absolute", top: c.y ?? top, transform: "translateY(-50%)" }}>
                  <Karaoke cap={c} frames={frames} size={size} font={font} />
                </div>
              </AbsoluteFill>
            ) : (
              <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: c.top ?? top }}>
                <Word cap={c} frames={frames} size={size} font={font} look={look} color={color} />
              </AbsoluteFill>
            )}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
