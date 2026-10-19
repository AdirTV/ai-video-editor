import { loadFont } from "@remotion/google-fonts/Rubik";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";
import { dir, pick, type Lang } from "../lang";

const { fontFamily } = loadFont("normal", { weights: ["900"], subsets: ["hebrew", "latin"] });
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Pixel torch (16×16 grid).
const Torch: React.FC<{ size: number; glow: number }> = ({ size, glow }) => (
  <svg viewBox="0 0 16 16" width={size} height={size} shapeRendering="crispEdges"
    style={{ filter: `drop-shadow(0 0 ${8 + glow * 30}px rgba(255,190,60,${0.5 + glow * 0.5}))` }}>
    <rect x={7} y={6} width={2} height={10} fill="#7a5a2c" />
    <rect x={7} y={6} width={1} height={10} fill="#9b7640" />
    <rect x={7} y={4} width={2} height={2} fill="#ffd84d" />
    <rect x={6} y={3} width={4} height={1} fill="#ff9d1c" />
    <rect x={7} y={2} width={2} height={1} fill="#fff3a8" />
  </svg>
);

// "Light level" HUD: 15 blocks fill up, turn red at the top and the panel shakes — "too bright!".
export const LightMeter: React.FC<{ seconds?: number; label?: string; warn?: string; fill?: number; lang?: Lang }> = ({
  lang, label = pick(lang, "רמת אור", "Light level"), warn = pick(lang, "חזק מדי!", "Too bright!"), fill = 0.9,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const lvl = interpolate(frame, [6, fill * fps], [0, 15], { ...clamp, easing: Easing.in(Easing.quad) });
  const maxed = lvl >= 14.9;
  const t = frame / fps;
  const shake = maxed ? Math.sin(t * 70) * 9 : 0;
  const warnS = interpolate(frame, [fill * fps, fill * fps + 8], [0, 1], { ...clamp, easing: Easing.out(Easing.back(3)) });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: 300 }}>
      <div
        style={{
          scale: popScale(frame, durationInFrames, 10, 7),
          opacity: popOpacity(frame, durationInFrames, 7),
          translate: `${shake}px 0`,
          background: "rgba(20,20,28,0.88)",
          border: "8px solid #111",
          borderRadius: 18,
          boxShadow: "0 14px 0 #111",
          padding: "26px 34px 30px",
          display: "flex",
          alignItems: "center",
          gap: 26,
          direction: dir(label),
        }}
      >
        <Torch size={130} glow={lvl / 15} />
        <div>
          <div style={{ fontFamily, fontWeight: 900, fontSize: 64, color: "#fff", marginBottom: 12, display: "flex", gap: 22 }}>
            <span>{label}</span>
            <span style={{ color: maxed ? "#ff4d4d" : "#ffd84d", direction: "ltr" }}>{Math.round(lvl)}</span>
          </div>
          <div style={{ display: "flex", gap: 6, direction: "ltr" }}>
            {Array.from({ length: 15 }, (_, i) => {
              const on = lvl > i + 0.5;
              const c = maxed ? "#ff3b3b" : i < 7 ? "#7cff7c" : i < 11 ? "#ffd84d" : "#ff8a3b";
              return <div key={i} style={{ width: 30, height: 54, background: on ? c : "#333", border: "4px solid #111" }} />;
            })}
          </div>
        </div>
      </div>
      <div
        style={{
          fontFamily, fontWeight: 900, fontSize: 104, color: "#ff3b3b", marginTop: 34,
          WebkitTextStroke: "16px #111", paintOrder: "stroke fill", textShadow: "0 10px 0 #111",
          scale: warnS, rotate: `${-4 + Math.sin(t * 20) * 2}deg`, direction: dir(warn),
          opacity: popOpacity(frame, durationInFrames, 7),
        }}
      >
        {warn}
      </div>
    </AbsoluteFill>
  );
};
