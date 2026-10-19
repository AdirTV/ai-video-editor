import { Easing, interpolate } from "remotion";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

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

export const popOpacity = (frame: number, duration: number, outFrames = 6) =>
  interpolate(frame, [0, 2, duration - outFrames * 0.5, duration], [0, 1, 1, 0], clamp);
