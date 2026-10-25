import { AbsoluteFill, Easing, Img, interpolate, random, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp, popOpacity, popScale } from "../pop";
import type { Props } from "../schemas";


// One mob turns into another: A pops in and wobbles, a flash + Minecraft
// "poof" of square particles hides the swap at `swapAtSec`, then B pops out of it.
// `swapAt` (a frame number) is the old prop, still honoured so earlier renders don't change.
export const Morph: React.FC<Props<"Morph">> = ({ from, to, swapAtSec = 0.38, swapAt: swapAtFrame }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const swapAt = swapAtFrame ?? Math.round(swapAtSec * fps);

  const wobble = Math.sin(frame * 1.3) * interpolate(frame, [8, swapAt], [0, 1], clamp);
  const aShrink = interpolate(frame, [swapAt - 3, swapAt + 1], [1, 0], { ...clamp, easing: Easing.in(Easing.quad) });
  const b = frame - swapAt;
  const hop = b > 8 ? -Math.abs(Math.sin((b - 8) * 0.22)) * 60 : 0;
  const flash = interpolate(frame, [swapAt - 1, swapAt + 1, swapAt + 7], [0, 1, 0], clamp);

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingBottom: 420 }}>
      <div style={{ position: "relative", width: 640, height: 640 }}>
        {frame < swapAt + 1 && (
          <Img
            src={staticFile(from)}
            style={{
              position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "contain",
              imageRendering: "pixelated",
              filter: "drop-shadow(0 18px 0 rgba(0,0,0,.45))",
              scale: `${popScale(frame, durationInFrames) * aShrink * (1 + wobble * 0.08)} ${popScale(frame, durationInFrames) * aShrink * (1 - wobble * 0.08)}`,
              rotate: `${wobble * 6}deg`,
              opacity: popOpacity(frame, durationInFrames),
            }}
          />
        )}
        {b >= 0 && (
          <Img
            src={staticFile(to)}
            style={{
              position: "absolute", inset: 40, width: 560, height: 560, objectFit: "contain",
              filter: "drop-shadow(0 18px 0 rgba(0,0,0,.45))",
              scale: popScale(b, durationInFrames - swapAt),
              opacity: popOpacity(b, durationInFrames - swapAt),
              translate: `0px ${hop}px`,
            }}
          />
        )}
        {/* poof: blocky smoke particles flying out from the centre */}
        {Array.from({ length: 22 }).map((_, i) => {
          const t = interpolate(frame, [swapAt - 1, swapAt + 16], [0, 1], clamp);
          if (t <= 0 || t >= 1) return null;
          const ang = random(`a${i}`) * Math.PI * 2;
          const dist = 120 + random(`d${i}`) * 260;
          const size = 26 + random(`s${i}`) * 40;
          const ease = Easing.out(Easing.cubic)(t);
          return (
            <div
              key={i}
              style={{
                position: "absolute", left: 320 - size / 2, top: 320 - size / 2, width: size, height: size,
                background: random(`c${i}`) > 0.5 ? "#f2f2f2" : "#bdbdbd",
                border: "4px solid #555",
                translate: `${Math.cos(ang) * dist * ease}px ${Math.sin(ang) * dist * ease - 40 * t}px`,
                scale: 1 - t * 0.7,
                opacity: 1 - t,
              }}
            />
          );
        })}
        <div
          style={{
            position: "absolute", inset: -200, borderRadius: "50%",
            background: "radial-gradient(circle, rgba(255,255,255,.95) 0%, rgba(255,255,255,0) 60%)",
            opacity: flash,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
