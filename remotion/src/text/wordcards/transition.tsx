import { AbsoluteFill, Easing, Freeze, interpolate, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { clamp } from "../../pop";

// "Zoom-through" cut between cards, measured frame by frame off the reference opener: ~5 frames before the cut
// the outgoing card starts rushing at the camera (scale 1 → ~3, accelerating, blurring); the next card cuts in at
// the peak while the outgoing letters hang behind it as a dim, huge, blurred backdrop for most of a second.
// The incoming lines arrive from far away (small → full size, see enterStyle), so it reads as one push forward.

export const LEAD = 0.15; // seconds the rush starts before the cut
const RUSH = 0.2; // seconds of the fast part
export const HOLD = 0.75; // seconds the backdrop stays after the cut


// t = seconds since the rush began
export const rushStyle = (t: number, origin = "50% 45%"): React.CSSProperties => {
  const p = interpolate(t, [0, RUSH], [0, 1], { ...clamp, easing: Easing.in(Easing.quad) });
  const q = interpolate(t, [RUSH, LEAD + HOLD], [0, 1], clamp);
  const fade = interpolate(t, [LEAD + HOLD - 0.3, LEAD + HOLD], [1, 0], clamp);
  return {
    transform: `scale(${1 + 2 * p + 0.4 * q}) rotate(${-2.5 * p}deg)`,
    transformOrigin: origin,
    filter: p > 0 ? `blur(${14 * p + 4 * q}px)` : undefined,
    // opaque until the cut (it covers its own card), then it thins out into the backdrop
    opacity: t < LEAD ? 1 : (1 - 0.55 * p) * fade,
  };
};

// Place next to a card's Sequence. From LEAD before `cut` it replays the card's frame at that moment (frozen),
// opaque over the card itself; after the cut it's blended onto whatever comes next. `blend` follows the outgoing
// card: "screen" for light-on-dark (its black drops out), "multiply" for dark-on-light (its paper drops out).
export const ZoomTail: React.FC<{ cut: number; cardStart: number; blend?: "screen" | "multiply"; origin?: string; name?: string; children: React.ReactNode }> = ({
  cut, cardStart, blend = "screen", origin, name, children,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const from = Math.round((cut - LEAD) * fps);
  const lead = Math.round(cut * fps) - from;
  const t = (frame - from) / fps;
  return (
    <Sequence from={from} durationInFrames={lead + Math.round(HOLD * fps)} name={name ?? "zoom-through"} style={{ zIndex: 10, mixBlendMode: frame - from < lead ? "normal" : blend }}>
      <AbsoluteFill style={rushStyle(t, origin)}>
        <Freeze frame={from - Math.round(cardStart * fps)}>{children}</Freeze>
      </AbsoluteFill>
    </Sequence>
  );
};
