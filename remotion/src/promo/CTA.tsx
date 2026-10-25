import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { RUBIK } from "../fonts";
import { clamp } from "../pop";
import { dir } from "../lang";
import { brand } from "../brand";
import type { Props } from "../schemas";

const fontFamily = RUBIK;

// "Click below" call-to-action for shorts: a blocky pill + bouncing arrow,
// rendered with alpha and layered over the edit in Premiere.
export const CTA: React.FC<Props<"CTA">> = ({ label, accent = brand.accent }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: 1330 }}>
      <div
        style={{
          fontFamily,
          direction: dir(label),
          fontSize: 92,
          fontWeight: 900,
          color: "#1b1b1b",
          background: accent,
          padding: "18px 54px 26px",
          border: "8px solid #1b1b1b",
          borderRadius: 14,
          boxShadow: "0 14px 0 #1b1b1b",
          opacity: interpolate(frame, [0, 0.1 * fps], [0, 1], clamp),
          scale: interpolate(frame, [0, 0.35 * fps], [0.6, 1], {
            ...clamp,
            easing: Easing.spring({ damping: 11 }),
          }),
        }}
      >
        {label}
      </div>
      <svg
        viewBox="0 0 120 150"
        width={210}
        style={{
          marginTop: 40,
          opacity: interpolate(frame, [0.15 * fps, 0.25 * fps], [0, 1], clamp),
          // Bounce toward the link under the short, ~2 times a second.
          translate: `0px ${interpolate(Math.sin((frame / fps) * Math.PI * 4), [-1, 1], [0, 46])}px`,
          filter: "drop-shadow(0 10px 0 #1b1b1b)",
        }}
      >
        <path d="M40 6h40v74h32L60 144 8 80h32z" fill={accent} stroke="#1b1b1b" strokeWidth={8} strokeLinejoin="round" />
      </svg>
    </AbsoluteFill>
  );
};
