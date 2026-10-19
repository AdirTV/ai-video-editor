import { loadFont as loadHeebo } from "@remotion/google-fonts/Heebo";
import { loadFont as loadRubik } from "@remotion/google-fonts/Rubik";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";

const FONTS = {
  rubik: loadRubik("normal", { weights: ["900"], subsets: ["hebrew", "latin"] }).fontFamily,
  heebo: loadHeebo("normal", { weights: ["900"], subsets: ["hebrew", "latin"] }).fontFamily,
};
type Font = keyof typeof FONTS;

export type Cap = { start: number; end: number; text: string; hl?: Record<string, string> };

const Word: React.FC<{ cap: Cap; frames: number; size: number; font: Font }> = ({ cap, frames, size, font }) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        fontFamily: FONTS[font],
        fontWeight: 900,
        // Always one line: shrink long groups to fit the safe width.
        fontSize: Math.min(size, 940 / (cap.text.length * 0.56)),
        lineHeight: 1.05,
        textAlign: "center",
        whiteSpace: "nowrap",
        direction: "rtl",
        unicodeBidi: "plaintext",
        color: "white",
        WebkitTextStroke: `${Math.round(size * 0.15)}px #111`,
        paintOrder: "stroke fill",
        textShadow: "0 10px 0 #111",
        scale: popScale(frame, frames),
        opacity: popOpacity(frame, frames),
      }}
    >
      {cap.text.split(" ").map((w, i) => (
        <span key={i} style={{ color: cap.hl?.[w] ?? "white" }}>
          {(i ? " " : "") + w}
        </span>
      ))}
    </div>
  );
};

// Word-group captions, centred a bit below the middle of a 9:16 frame (top/size override per short).
export const Captions: React.FC<{ caps: Cap[]; top?: number; size?: number; seconds?: number; font?: Font }> = ({
  caps, top = 980, size = 118, font = "rubik",
}) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      {caps.map((c, i) => {
        const from = Math.round(c.start * fps);
        const frames = Math.round(c.end * fps) - from;
        return (
          <Sequence key={i} from={from} durationInFrames={frames} name={c.text}>
            <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: top }}>
              <Word cap={c} frames={frames} size={size} font={font} />
            </AbsoluteFill>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
