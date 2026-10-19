import { loadFont } from "@remotion/google-fonts/Heebo";
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

const { fontFamily } = loadFont("normal", { weights: ["800", "900"], subsets: ["hebrew", "latin"] });

// Minecraft's text shadow: a hard copy offset down-right in a darker shade.
const mcShadow = (px: number, c: string) => `${px}px ${px}px 0 ${c}`;

// In-game "Advancement Made!" toast, in Hebrew. Slides in from the top edge, holds, slides out.
// frame: "task" | "goal" | "challenge" (challenge = purple title, the rare one).
export const Advancement: React.FC<{
  seconds?: number; title?: string; text: string; icon: string;
  frame?: "task" | "goal" | "challenge"; scale?: number; top?: number; side?: "right" | "left" | "center";
}> = ({ title, text, icon, frame: kind = "task", scale = 1, top = 60, side = "right" }) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const inP = spring({ frame: f, fps, config: { damping: 16, stiffness: 140, mass: 0.8 } });
  const outP = interpolate(f, [durationInFrames - 16, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.cubic),
  });
  const y = interpolate(inP, [0, 1], [-260, 0]) + interpolate(outP, [0, 1], [0, -260]);
  // icon pops a beat after the panel lands
  const iconS = spring({ frame: f - 8, fps, config: { damping: 9, stiffness: 220 } });
  const shine = interpolate(f, [10, 40], [-120, 220], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  const titleColor = kind === "challenge" ? "#FF55FF" : "#FFFF55";
  const titleText = title ?? (kind === "challenge" ? "אתגר הושלם!" : kind === "goal" ? "מטרה הושגה!" : "הישג חדש!");
  const frameImg = { task: "Task", goal: "Goal", challenge: "Challenge" }[kind];
  const u = 6 * scale; // one Minecraft GUI pixel

  const justify = side === "right" ? "flex-end" : side === "left" ? "flex-start" : "center";
  return (
    <AbsoluteFill style={{ alignItems: justify, justifyContent: "flex-start", padding: `${top}px 60px` }}>
      <div
        style={{
          translate: `0 ${y}px`, direction: "rtl", display: "flex", alignItems: "center", gap: 6 * u,
          minWidth: 160 * u, padding: `${4 * u}px ${6 * u}px ${4 * u}px ${8 * u}px`,
          background: "#212121", position: "relative", overflow: "hidden",
          // classic GUI bevel: light outer ring, black inner ring
          boxShadow: `0 0 0 ${u}px #000, inset 0 0 0 ${u}px #555, inset ${u}px ${u}px 0 ${u}px #3a3a3a, 0 ${3 * u}px ${6 * u}px rgba(0,0,0,.45)`,
          imageRendering: "pixelated",
        }}
      >
        <div style={{ position: "relative", width: 26 * u, height: 26 * u, flexShrink: 0 }}>
          <Img src={staticFile(`japan/Advancement_${frameImg}_Frame_Obtained.png`)}
            style={{ position: "absolute", inset: 0, width: "100%", height: "100%", imageRendering: "pixelated" }} />
          <Img src={staticFile(`japan/${icon}`)}
            style={{ position: "absolute", left: "17%", top: "17%", width: "66%", height: "66%",
              imageRendering: "pixelated", scale: String(iconS) }} />
        </div>
        <div style={{ fontFamily, lineHeight: 1.15 }}>
          <div style={{ fontWeight: 900, fontSize: 13 * u, color: titleColor, textShadow: mcShadow(u, kind === "challenge" ? "#3F153F" : "#3F3F15") }}>
            {titleText}
          </div>
          <div style={{ fontWeight: 800, fontSize: 11 * u, color: "#fff", textShadow: mcShadow(u, "#3F3F3F"), whiteSpace: "nowrap" }}>
            {text}
          </div>
        </div>
        <div style={{ position: "absolute", top: 0, bottom: 0, width: 40 * u, left: `${shine}%`, rotate: "20deg",
          background: "linear-gradient(90deg, transparent, rgba(255,255,255,.18), transparent)" }} />
      </div>
    </AbsoluteFill>
  );
};
