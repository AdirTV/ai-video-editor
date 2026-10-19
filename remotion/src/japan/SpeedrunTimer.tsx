import { loadFont } from "@remotion/google-fonts/Heebo";
import { AbsoluteFill, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { dir } from "../lang";

const { fontFamily } = loadFont("normal", { weights: ["800", "900"], subsets: ["hebrew", "latin"] });
const mc = "MinecraftTen";
const fontFace = `@font-face { font-family: ${mc}; src: url(${staticFile("japan/MinecraftTen.ttf")}); }`;

type Split = { label: string; at: number }; // at = run time in seconds when this split was hit

const fmt = (s: number) => {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60), cs = Math.floor((s * 100) % 100);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${h ? h + ":" : ""}${pad(m)}:${pad(sec)}.${pad(cs)}`;
};

// LiveSplit-style speedrun HUD. The run clock goes from `from` to `to` (real run seconds) over the clip —
// so a 3 s clip can cover 20 real minutes of travel. Splits at or before the clock show their time;
// the split being crossed flashes green.
export const SpeedrunTimer: React.FC<{
  seconds?: number; title?: string; category?: string; splits: Split[]; from: number; to: number;
  scale?: number; corner?: "tl" | "tr";
}> = ({ title = "Minecraft Store", category = "Tokyo Any%", splits, from, to, scale = 1, corner = "tl" }) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = interpolate(f, [0, durationInFrames - 1], [from, to], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const slide = spring({ frame: f, fps, config: { damping: 18, stiffness: 160 } });
  const out = interpolate(f, [durationInFrames - 12, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const u = scale;
  const side = corner === "tl" ? { left: 40 * u } : { right: 40 * u };

  return (
    <AbsoluteFill>
      <style>{fontFace}</style>
      <div style={{ position: "absolute", top: 40 * u, ...side, width: 470 * u, opacity: out,
        translate: `${(corner === "tl" ? -1 : 1) * (1 - slide) * 560 * u}px 0`,
        background: "linear-gradient(#1b1b1bee, #0b0b0bee)", border: `${3 * u}px solid #000`, borderRadius: 8 * u,
        boxShadow: `0 ${8 * u}px ${24 * u}px rgba(0,0,0,.5)`, overflow: "hidden" }}>
        <div style={{ textAlign: "center", padding: `${10 * u}px 0 ${6 * u}px`, borderBottom: `${2 * u}px solid #333` }}>
          <div style={{ fontFamily: mc, fontSize: 30 * u, color: "#fff" }}>{title}</div>
          <div style={{ fontFamily: mc, fontSize: 20 * u, color: "#9be36b" }}>{category}</div>
        </div>
        {splits.map((s, i) => {
          const done = t >= s.at;
          const flash = interpolate(t - s.at, [0, (to - from) * 0.04], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
          return (
            <div key={i} style={{ direction: dir(s.label), display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: `${5 * u}px ${14 * u}px`, background: done && flash > 0 ? `rgba(80,200,90,${0.45 * flash})` : i % 2 ? "#ffffff08" : "transparent" }}>
              <span style={{ fontFamily, fontWeight: 800, fontSize: 24 * u, color: done ? "#fff" : "#888" }}>{s.label}</span>
              <span style={{ fontFamily: mc, fontSize: 22 * u, color: done ? "#6bd66b" : "#555", direction: "ltr" }}>{done ? fmt(s.at) : "-"}</span>
            </div>
          );
        })}
        <div style={{ fontFamily: mc, fontSize: 64 * u, textAlign: dir(splits[0]?.label) === "rtl" ? "left" : "right", padding: `${4 * u}px ${16 * u}px ${8 * u}px`,
          color: "#3fe05a", textShadow: `0 0 ${12 * u}px #2fbf4a88`, fontVariantNumeric: "tabular-nums" }}>
          {fmt(t)}
        </div>
      </div>
    </AbsoluteFill>
  );
};
