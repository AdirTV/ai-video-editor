import { loadFont as loadHeebo } from "@remotion/google-fonts/Heebo";
import { loadFont as loadRubik } from "@remotion/google-fonts/Rubik";
import { loadFont as loadCarlito } from "@remotion/google-fonts/Carlito";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";
import { dir } from "../lang";

const FONTS = {
  rubik: loadRubik("normal", { weights: ["900"], subsets: ["hebrew", "latin"] }).fontFamily,
  heebo: loadHeebo("normal", { weights: ["900"], subsets: ["hebrew", "latin"] }).fontFamily,
  // Calibri-metric font: the stream-clip / podcast-short caption look
  carlito: loadCarlito("normal", { weights: ["700"], subsets: ["latin"] }).fontFamily,
};
type Font = keyof typeof FONTS;

export type Cap = { start: number; end: number; text: string; hl?: Record<string, string> };

// "bold": white, thick black stroke + drop (default). "stream": light-blue, thin navy outline, soft pop
// (the clip-channel look: game on top, face below, captions on the seam).
type Look = "bold" | "stream";
const LOOKS = {
  bold: { color: "white", stroke: "#111", strokeK: 0.15, shadow: (s: number) => "0 10px 0 #111", weight: 900, pop: 1 },
  stream: { color: "#A9D8FF", stroke: "#0B1B2E", strokeK: 0.09, shadow: (s: number) => `0 ${Math.round(s * 0.04)}px ${Math.round(s * 0.08)}px rgba(0,0,0,.6)`, weight: 700, pop: 0.35 },
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
        fontWeight: L.weight,
        // Always one line: shrink long groups to fit the safe width.
        fontSize: Math.min(size, 940 / (cap.text.length * 0.56)),
        lineHeight: 1.05,
        textAlign: "center",
        whiteSpace: "nowrap",
        direction: dir(cap.text),
        unicodeBidi: "plaintext",
        color: base,
        WebkitTextStroke: `${Math.round(size * L.strokeK)}px ${L.stroke}`,
        paintOrder: "stroke fill",
        textShadow: L.shadow(size),
        scale: pop,
        opacity: popOpacity(frame, frames),
      }}
    >
      {cap.text.split(" ").map((w, i) => (
        <span key={i} style={{ color: cap.hl?.[w] ?? base }}>
          {(i ? " " : "") + w}
        </span>
      ))}
    </div>
  );
};

// Word-group captions, centred a bit below the middle of a 9:16 frame (top/size override per short).
export const Captions: React.FC<{
  caps: Cap[]; top?: number; size?: number; seconds?: number; font?: Font; look?: Look; color?: string;
}> = ({ caps, top = 980, size = 118, font = "rubik", look = "bold", color }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      {caps.map((c, i) => {
        const from = Math.round(c.start * fps);
        const frames = Math.round(c.end * fps) - from;
        return (
          <Sequence key={i} from={from} durationInFrames={frames} name={c.text}>
            <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: top }}>
              <Word cap={c} frames={frames} size={size} font={font} look={look} color={color} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
