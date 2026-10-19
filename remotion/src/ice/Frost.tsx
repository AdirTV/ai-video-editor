import { AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig } from "remotion";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// A six-armed pixel-ish snowflake.
const Flake: React.FC<{ size: number; color: string }> = ({ size, color }) => (
  <svg viewBox="-50 -50 100 100" width={size} height={size}>
    {[0, 60, 120].map((a) => (
      <g key={a} transform={`rotate(${a})`} stroke={color} strokeWidth={7} strokeLinecap="square">
        <line x1={0} y1={-46} x2={0} y2={46} />
        <line x1={0} y1={-30} x2={-12} y2={-42} />
        <line x1={0} y1={-30} x2={12} y2={-42} />
        <line x1={0} y1={30} x2={-12} y2={42} />
        <line x1={0} y1={30} x2={12} y2={42} />
      </g>
    ))}
  </svg>
);

// The screen freezes over: frost creeps in from the edges (like Minecraft's powder-snow overlay),
// snowflakes grow along the border, a cold tint settles in. `grow` = seconds to full frost.
export const Frost: React.FC<{ seconds?: number; grow?: number; tint?: number }> = ({ grow = 1.2, tint = 0.22 }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();
  const k = interpolate(frame, [0, grow * fps], [0, 1], clamp);
  const out = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0], clamp);
  const flakes = Array.from({ length: 46 }, (_, i) => {
    // spread on the border band
    const side = i % 4;
    const u = random(`u${i}`);
    const d = random(`d${i}`) * 150;
    const x = side === 0 ? u * width : side === 1 ? width - d : side === 2 ? u * width : d;
    const y = side === 0 ? d : side === 1 ? u * height : height - d;
    const delay = random(`t${i}`) * 0.7;
    const s = interpolate(k, [delay, Math.min(1, delay + 0.3)], [0, 1], clamp);
    return { x, y, s, size: 60 + random(`s${i}`) * 110, rot: random(`r${i}`) * 60 + frame * 0.4 };
  });
  const inner = interpolate(k, [0, 1], [95, 62]);
  return (
    <AbsoluteFill style={{ opacity: out }}>
      <AbsoluteFill style={{ background: `rgba(120,190,255,${tint * k})`, mixBlendMode: "screen" }} />
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse at center, rgba(255,255,255,0) ${inner}%, rgba(200,235,255,${0.55 * k}) 100%)`,
        }}
      />
      {flakes.map((f, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: f.x - f.size / 2,
            top: f.y - f.size / 2,
            scale: f.s,
            rotate: `${f.rot}deg`,
            opacity: 0.9 * f.s,
            filter: "drop-shadow(0 0 6px rgba(160,220,255,.9))",
          }}
        >
          <Flake size={f.size} color={i % 3 ? "#e8f7ff" : "#9fdcff"} />
        </div>
      ))}
    </AbsoluteFill>
  );
};
