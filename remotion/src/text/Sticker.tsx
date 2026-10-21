import { loadFont } from "@remotion/google-fonts/Rubik";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";
import { dir } from "../lang";
import { brand } from "../brand";
import type { Props } from "../schemas";

const { fontFamily } = loadFont("normal", { weights: ["900"], subsets: ["hebrew", "latin"] });

// A tilted label that pops in (e.g. "חדש!", "מערות הקרח") — block pill with a hard shadow.
export const Sticker: React.FC<Props<"Sticker">> = ({
  text, bg = brand.accent2, color = "#111", top = 360, size = 120, tilt = -6,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const wob = interpolate(frame, [0, 10, 18], [tilt * 3, -tilt * 0.6, tilt], {
    extrapolateRight: "clamp", easing: Easing.out(Easing.quad),
  });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: top }}>
      <div
        style={{
          fontFamily, fontWeight: 900, fontSize: size, color, background: bg, direction: dir(text),
          padding: `${size * 0.12}px ${size * 0.45}px ${size * 0.2}px`,
          border: "10px solid #111", borderRadius: 18, boxShadow: "0 16px 0 #111",
          rotate: `${wob}deg`,
          scale: popScale(frame, durationInFrames, 10, 7),
          opacity: popOpacity(frame, durationInFrames, 7),
          whiteSpace: "nowrap",
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
