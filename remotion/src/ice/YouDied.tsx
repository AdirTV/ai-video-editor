import { loadFont } from "@remotion/google-fonts/PixelifySans";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

const { fontFamily } = loadFont("normal", { weights: ["700"], subsets: ["latin"] });
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Button: React.FC<{ label: string; delay: number }> = ({ label, delay }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [delay, delay + 6], [0, 1], clamp);
  return (
    <div
      style={{
        width: 760,
        height: 104,
        marginTop: 26,
        background: "#6f6f6f",
        border: "6px solid #000",
        boxShadow: "inset 6px 6px 0 #a8a8a8, inset -6px -6px 0 #4a4a4a",
        color: "#fff",
        fontSize: 56,
        textShadow: "5px 5px 0 #3f3f3f",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: o,
        translate: `0 ${(1 - o) * 30}px`,
      }}
    >
      {label}
    </div>
  );
};

// Minecraft death screen: an ice-shard hit (white flash + cracks), then the red "You Died!" screen.
export const YouDied: React.FC<{ seconds?: number }> = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const flash = interpolate(frame, [0, 3, 10], [0.9, 0.6, 0], clamp);
  const cracks = interpolate(frame, [0, 4, 20, 30], [0, 1, 1, 0], clamp);
  const red = interpolate(frame, [4, 18], [0, 1], clamp);
  const title = interpolate(frame, [10, 24], [2.2, 1], { ...clamp, easing: Easing.out(Easing.back(2)) });
  const out = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], clamp);
  return (
    <AbsoluteFill style={{ fontFamily, opacity: out }}>
      <AbsoluteFill
        style={{
          opacity: red,
          background: "linear-gradient(180deg, rgba(80,0,0,0.55) 0%, rgba(160,10,10,0.72) 100%)",
        }}
      />
      <svg width={1080} height={1920} style={{ position: "absolute", opacity: cracks }}>
        {/* shattered-ice cracks from the impact point */}
        {[
          "M540 700 L420 520 L380 300 L300 120",
          "M540 700 L680 560 L760 380 L900 260 L1000 80",
          "M540 700 L760 760 L960 720 L1080 800",
          "M540 700 L330 780 L160 760 L0 880",
          "M540 700 L590 920 L560 1180 L640 1460",
          "M540 700 L450 900 L300 1100 L220 1400",
          "M420 520 L300 560", "M760 380 L820 470", "M590 920 L700 990", "M330 780 L360 900",
        ].map((d, i) => (
          <path key={i} d={d} stroke="#eaf8ff" strokeWidth={i < 6 ? 9 : 6} fill="none" strokeLinejoin="miter"
            style={{ filter: "drop-shadow(0 0 8px rgba(150,220,255,1))" }} />
        ))}
      </svg>
      <AbsoluteFill style={{ background: "#fff", opacity: flash }} />
      <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: 560, opacity: red }}>
        <div style={{ fontSize: 150, color: "#fff", textShadow: "12px 12px 0 #3f3f3f", scale: title }}>You Died!</div>
        <div style={{ fontSize: 62, color: "#fff", textShadow: "6px 6px 0 #3f3f3f", marginTop: 40, marginBottom: 60 }}>
          Score: <span style={{ color: "#ffff55" }}>0</span>
        </div>
        <Button label="Respawn" delay={22} />
        <Button label="Title Screen" delay={27} />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
