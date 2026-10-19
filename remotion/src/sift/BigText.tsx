import { loadFont } from "@remotion/google-fonts/Rubik";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";

const { fontFamily } = loadFont("normal", { weights: ["900"], subsets: ["latin"] });

// One huge word that pops in with a tilt and pops out (e.g. "2027").
export const BigText: React.FC<{ text: string; color: string }> = ({ text, color }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", paddingTop: 260 }}>
      <div
        style={{
          fontFamily,
          fontWeight: 900,
          fontSize: 330,
          color,
          WebkitTextStroke: "26px #111",
          paintOrder: "stroke fill",
          textShadow: "0 18px 0 #111",
          scale: popScale(frame, durationInFrames, 10, 7),
          opacity: popOpacity(frame, durationInFrames, 7),
          rotate: `${interpolate(frame, [0, 10, durationInFrames], [-14, 4, -2], { extrapolateRight: "clamp" })}deg`,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
