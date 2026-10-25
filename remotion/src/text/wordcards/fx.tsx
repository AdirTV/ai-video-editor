import { AbsoluteFill, Easing, interpolate, random, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp } from "../../pop";

// Building blocks of the documentary word-card look: blur-in entrance, blurred echo, RGB-split glitch,
// film grain, vignette and a soft light pool.

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

// RGB split + horizontal slice displacement while `on`. Every slice is another full copy of the children, so
// only slices that actually move (|dx| ≥ 4 px) are drawn, and there are 6 of them (was 9: same look, fewer copies).
const SLICES = 6;
export const Glitch: React.FC<{ on: boolean; strength?: number; children: React.ReactNode }> = ({ on, strength = 1, children }) => {
  const frame = useCurrentFrame();
  if (!on) return <AbsoluteFill>{children}</AbsoluteFill>;
  return (
    <AbsoluteFill>
      <AbsoluteFill style={{ transform: `translateX(${-14 * strength}px)`, mixBlendMode: "screen", filter: "url(#wcRed)", opacity: 0.9 }}>{children}</AbsoluteFill>
      <AbsoluteFill style={{ transform: `translateX(${14 * strength}px)`, mixBlendMode: "screen", filter: "url(#wcCyan)", opacity: 0.9 }}>{children}</AbsoluteFill>
      {new Array(SLICES).fill(0).map((_, i) => {
        const top = random(`top${i}-${frame}`) * 100;
        const h = 2 + random(`h${i}-${frame}`) * 9;
        const dx = (random(`dx${i}-${frame}`) - 0.5) * 120 * strength;
        if (Math.abs(dx) < 4) return null;
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

// Film grain that changes every other frame. The noise is computed once (fixed seed, a bit larger than the frame)
// and jumped to a random offset instead of re-running feTurbulence over the whole frame each time.
const GRAIN_PAD = 160;
export const Grain: React.FC<{ opacity?: number }> = ({ opacity = 0.14 }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const k = Math.floor(frame / 2) % 12;
  const dx = Math.floor(random(`grainx${k}`) * GRAIN_PAD), dy = Math.floor(random(`grainy${k}`) * GRAIN_PAD);
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "overlay", opacity, overflow: "hidden" }}>
      <svg width={width + GRAIN_PAD} height={height + GRAIN_PAD}
        style={{ position: "absolute", left: 0, top: 0, transform: `translate(${-dx}px, ${-dy}px)`, willChange: "transform" }}>
        <filter id="wcGrain">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={0} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#wcGrain)" />
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
