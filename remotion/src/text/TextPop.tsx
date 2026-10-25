import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { RUBIK } from "../fonts";
import { clamp } from "../pop";
import { dir } from "../lang";
import { brand } from "../brand";
import type { Props } from "../schemas";

const fontFamily = RUBIK;


// Animation Composer's "overshoot" curve (from a downloaded .aep): a damped cosine that tapers to 0 over the last 20%.
const overshoot = (t: number, bounces: number, decay = 7) => {
  const y = Math.cos(t * bounces * Math.PI * 2) / Math.exp(t * decay);
  return t < 0.8 ? y : y * (1 - (t - 0.8) / 0.2);
};

const split = (text: string, byWord: boolean) =>
  byWord
    ? text.split(/(\s+)/).filter(Boolean)
    : (text.match(/\P{M}\p{M}*/gu) ?? []); // keep niqqud / accents on their letter

// A line of text whose letters (or words) pop in one after another with a springy overshoot,
// a soft glow behind them and a light sweep across once they land; the line pops out at the end.
export const TextPop: React.FC<Props<"TextPop">> = ({
  text, color = "#fff", glow = brand.accent, size = 150, top = 820, by = "char", stagger = 2, bounces = 2, sweep = true,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps, width } = useVideoConfig();
  const parts = split(text, by === "word");
  const inFrames = Math.round(fps * 0.55);
  const landed = (parts.length - 1) * stagger + inFrames;
  // one line: shrink long text to fit the frame
  const fontSize = Math.min(size, (width * 0.88) / Math.max(1, text.length * 0.6));

  const outFrames = 8;
  const out = interpolate(frame, [durationInFrames - outFrames, durationInFrames], [1, 0], {
    ...clamp, easing: Easing.in(Easing.back(2)),
  });

  const letters = (live: boolean) =>
    parts.map((p, i) => {
      const t = interpolate(frame - i * stagger, [0, inFrames], [0, 1], clamp);
      const s = live ? 1 - overshoot(t, bounces) : 1;
      const space = /^\s+$/.test(p);
      return (
        <span
          key={i}
          style={{
            display: "inline-block",
            whiteSpace: "pre",
            scale: Math.max(0, s),
            translate: live ? `0 ${(1 - s) * fontSize * 0.35}px` : undefined,
            opacity: live ? interpolate(t, [0, 0.08], [0, 1], clamp) : 1,
            width: space ? fontSize * 0.28 : undefined,
          }}
        >
          {space ? "" : p}
        </span>
      );
    });

  // light sweep: a bright band crosses the text once every letter has landed
  const band = interpolate(frame, [landed, landed + fps * 0.5], [-30, 130], clamp);
  const line: React.CSSProperties = {
    display: "flex", direction: dir(text), fontFamily, fontWeight: 900, fontSize, lineHeight: 1.1, whiteSpace: "nowrap",
  };

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: top }}>
      <div style={{ position: "relative", scale: out }}>
        <div
          style={{
            ...line,
            color,
            textShadow: `0 0 ${fontSize * 0.06}px ${glow}, 0 0 ${fontSize * 0.2}px ${glow}, 0 0 ${fontSize * 0.45}px ${glow}, 0 ${fontSize * 0.06}px ${fontSize * 0.04}px rgba(0,0,0,.45)`,
          }}
        >
          {letters(true)}
        </div>
        {sweep && frame >= landed && band < 130 ? (
          <div
            style={{
              ...line,
              position: "absolute", inset: 0, color: "transparent",
              backgroundImage: `linear-gradient(105deg, transparent ${band - 12}%, rgba(255,255,255,.95) ${band}%, transparent ${band + 12}%)`,
              backgroundClip: "text", WebkitBackgroundClip: "text",
            }}
          >
            {letters(false)}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};
