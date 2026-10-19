import { loadFont } from "@remotion/google-fonts/Rubik";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity } from "../pop";
import { dir, pick, type Lang } from "../lang";

const { fontFamily } = loadFont("normal", { weights: ["900"], subsets: ["hebrew", "latin"] });
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Red alarm: pulsing red edges + a warning sign that slams in.
export const Alarm: React.FC<{ seconds?: number; text?: string; lang?: Lang }> = ({ lang, text = pick(lang, "זהירות!", "Watch out!") }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const pulse = 0.55 + 0.45 * Math.abs(Math.sin((frame / fps) * Math.PI * 3));
  const o = popOpacity(frame, durationInFrames, 8);
  const slam = interpolate(frame, [0, 9], [2.6, 1], { ...clamp, easing: Easing.out(Easing.back(2.2)) });
  return (
    <AbsoluteFill style={{ opacity: o }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at center, rgba(255,0,0,0) 45%, rgba(255,20,20,${0.75 * pulse}) 100%)`,
        }}
      />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: 330 }}>
        <div style={{ scale: slam, rotate: `${Math.sin(frame * 0.9) * 3}deg`, display: "flex", flexDirection: "column", alignItems: "center" }}>
          <svg viewBox="0 0 120 106" width={300} style={{ filter: "drop-shadow(0 14px 0 #111)" }}>
            <path d="M60 6 L114 100 H6 Z" fill="#ffd84d" stroke="#111" strokeWidth={9} strokeLinejoin="round" />
            <rect x={53} y={36} width={14} height={36} fill="#111" />
            <rect x={53} y={80} width={14} height={12} fill="#111" />
          </svg>
          <div
            style={{
              fontFamily, fontWeight: 900, fontSize: 120, color: "#fff", direction: dir(text), marginTop: 10,
              WebkitTextStroke: "18px #111", paintOrder: "stroke fill", textShadow: "0 12px 0 #111",
            }}
          >
            {text}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
