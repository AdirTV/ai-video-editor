import { loadFont } from "@remotion/google-fonts/Heebo";
import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { dir } from "../lang";
import type { Props } from "../schemas";

const { fontFamily } = loadFont("normal", { weights: ["900"], subsets: ["hebrew", "latin"] });

type Stop = { x: number; y: number; label: string; icon?: string };

// A Minecraft "filled map" item that unfolds, then a dashed route draws stop to stop with the
// player marker riding along it. Coordinates are 0..1 inside the map. `upTo` = how many legs to draw
// (so the same map can come back later in the video showing more of the journey).
export const RouteMap: React.FC<Props<"RouteMap">> = ({
  stops, upTo = stops.length - 1, fromLeg = 0, size = 860,
}) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const open = spring({ frame: f, fps, config: { damping: 14, stiffness: 120 } });
  const out = interpolate(f, [durationInFrames - 14, durationInFrames], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // legs animate one after another between 0.6 s and 85% of the clip
  const legs = upTo - fromLeg;
  const t0 = fps * 0.6, t1 = durationInFrames * 0.85;
  const prog = interpolate(f, [t0, t1], [fromLeg, upTo], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.inOut(Easing.cubic),
  });
  const leg = Math.min(Math.floor(prog), upTo - 1);
  const k = prog - leg;
  const a = stops[leg], b = stops[Math.min(leg + 1, stops.length - 1)];
  const px = a.x + (b.x - a.x) * k, py = a.y + (b.y - a.y) * k;

  const P = (s: Stop) => `${s.x * 100} ${s.y * 100}`;
  let d = "";
  for (let i = 0; i < Math.ceil(prog) && i < stops.length - 1; i++) {
    const end = i < leg ? stops[i + 1] : { x: px, y: py, label: "" };
    d += `M ${P(stops[i])} L ${P(end)} `;
  }

  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", opacity: out }}>
      <div style={{ position: "relative", width: size, height: size, scale: `${open}`, rotate: `${(1 - open) * -25}deg` }}>
        <Img src={staticFile("mc/map_background.png")} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", imageRendering: "pixelated" }} />
        <svg viewBox="0 0 100 100" style={{ position: "absolute", inset: "7%", width: "86%", height: "86%", overflow: "visible" }}>
          <path d={d} stroke="#8B1E1E" strokeWidth={1.4} strokeDasharray="2.4 1.6" fill="none" strokeLinecap="square" />
        </svg>
        <div style={{ position: "absolute", inset: "7%" }}>
          {stops.map((s, i) => {
            const shown = i <= Math.max(prog, fromLeg) + 0.001;
            const pop = spring({ frame: f - (t0 + ((i - fromLeg) / Math.max(legs, 1)) * (t1 - t0)), fps, config: { damping: 9, stiffness: 200 } });
            const isLast = i === stops.length - 1;
            return (
              <div key={i} style={{ position: "absolute", left: `${s.x * 100}%`, top: `${s.y * 100}%`, translate: "-50% -50%",
                display: "flex", flexDirection: "column", alignItems: "center", opacity: shown ? 1 : 0, scale: `${i <= fromLeg ? 1 : pop}` }}>
                <Img src={staticFile(`mc/${s.icon ?? (isLast ? "Map_X.png" : "Map_Marker.png")}`)}
                  style={{ width: size * 0.075, height: size * 0.075, imageRendering: "pixelated" }} />
                <div style={{ fontFamily, fontWeight: 900, fontSize: size * 0.04, color: "#3b2a17", direction: dir(s.label), whiteSpace: "nowrap",
                  background: "rgba(255,248,225,.85)", padding: "0 10px", borderRadius: 6, marginTop: 4 }}>{s.label}</div>
              </div>
            );
          })}
          <Img src={staticFile("mc/Map_Player.png")} style={{ position: "absolute", left: `${px * 100}%`, top: `${py * 100}%`,
            width: size * 0.06, height: size * 0.06, translate: "-50% -50%", imageRendering: "pixelated",
            rotate: `${(Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI + 90}deg` }} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
