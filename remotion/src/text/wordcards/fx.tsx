import { AbsoluteFill, Easing, interpolate, random, useCurrentFrame, useVideoConfig } from "remotion";

// Building blocks of the documentary word-card look: blur-in entrance, blurred echo, RGB-split glitch,
// film grain, vignette and a soft light pool.

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const ease = Easing.bezier(0.16, 1, 0.3, 1);

// 0 → 1 over `dur` seconds from `at` (seconds of the current Sequence).
export const useEnter = (at: number, dur = 0.24) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return interpolate(frame / fps, [at, at + dur], [0, 1], { ...clamp, easing: ease });
};

// Blurred, small and transparent → sharp: the line flies in from the distance (the second half of the zoom-through).
export const enterStyle = (p: number, rise = 0): React.CSSProperties => ({
  opacity: p,
  filter: p < 1 ? `blur(${(1 - p) * 14}px)` : undefined,
  transform: `translateY(${(1 - p) * rise}px) scale(${0.78 + p * 0.22})`,
});

export const glow = (color: string, k = 1) => `0 0 ${8 * k}px ${color}, 0 0 ${22 * k}px ${color}, 0 0 ${48 * k}px ${color}aa`;

// RGB split + horizontal slice displacement while `on`.
export const Glitch: React.FC<{ on: boolean; strength?: number; children: React.ReactNode }> = ({ on, strength = 1, children }) => {
  const frame = useCurrentFrame();
  if (!on) return <AbsoluteFill>{children}</AbsoluteFill>;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `translateX(${-14 * strength}px)`, mixBlendMode: "screen", filter: "url(#wcRed)", opacity: 0.9 }}>{children}</AbsoluteFill>
      <AbsoluteFill style={{ transform: `translateX(${14 * strength}px)`, mixBlendMode: "screen", filter: "url(#wcCyan)", opacity: 0.9 }}>{children}</AbsoluteFill>
      {new Array(9).fill(0).map((_, i) => {
        const top = random(`top${i}-${frame}`) * 100;
        const h = 2 + random(`h${i}-${frame}`) * 9;
        const dx = (random(`dx${i}-${frame}`) - 0.5) * 120 * strength;
        return (
          <AbsoluteFill key={i} style={{ clipPath: `inset(${top}% 0 ${Math.max(0, 100 - top - h)}% 0)`, transform: `translateX(${dx}px)` }}>
            {children}
          </AbsoluteFill>
        );
      })}
    </AbsoluteFill>
  );
};

export const GlitchFilters: React.FC = () => (
  <svg width="0" height="0" style={{ position: "absolute" }}>
    <filter id="wcRed">
      <feColorMatrix type="matrix" values="1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0" />
    </filter>
    <filter id="wcCyan">
      <feColorMatrix type="matrix" values="0 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 1 0" />
    </filter>
  </svg>
);

// Film grain, re-seeded every other frame.
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.14 }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const seed = Math.floor(frame / 2) % 12;
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "overlay", opacity }}>
      <svg width={width} height={height}>
        <filter id={`wcGrain${seed}`}>
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter={`url(#wcGrain${seed})`} />
      </svg>
    </AbsoluteFill>
  );
};

export const Vignette: React.FC<{ strength?: number; color?: string }> = ({ strength = 0.85, color = "0,0,0" }) => (
  <AbsoluteFill style={{ pointerEvents: "none", background: `radial-gradient(ellipse 70% 65% at 50% 48%, rgba(${color},0) 35%, rgba(${color},${strength}) 100%)` }} />
);

export const Pool: React.FC<{ color: string }> = ({ color }) => (
  <AbsoluteFill style={{ background: `radial-gradient(ellipse 60% 55% at 50% 48%, rgba(${color},0.9) 0%, rgba(${color},0) 70%)` }} />
);
