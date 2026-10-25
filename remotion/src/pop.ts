import { Easing, interpolate } from "remotion";

// Shared interpolate options: hold the first/last value outside the input range.
export const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// 1 → 0 over the last `dur` frames of an element `n` frames long (a plain fade-out).
export const fadeOut = (frame: number, dur: number, n: number) => interpolate(frame, [n - dur, n], [1, 0], clamp);

// Pop in (overshoot) and pop out over the element's own [0, duration) frames.
export const popScale = (frame: number, duration: number, inFrames = 9, outFrames = 6) =>
  frame < duration - outFrames
    ? interpolate(frame, [0, inFrames * 0.6, inFrames], [0.5, 1.12, 1], {
        ...clamp,
        easing: Easing.out(Easing.quad),
      })
    : interpolate(frame, [duration - outFrames, duration], [1, 0.6], {
        ...clamp,
        easing: Easing.in(Easing.quad),
      });

export const popOpacity = (frame: number, duration: number, outFrames = 6) => {
  // keep the input range strictly increasing even for very short elements
  const a = Math.min(2, duration * 0.25);
  const b = Math.max(a + 0.01, duration - outFrames * 0.5);
  return interpolate(frame, [0, a, b, Math.max(b + 0.01, duration)], [0, 1, 1, 0], clamp);
};
