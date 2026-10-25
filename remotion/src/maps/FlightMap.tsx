import { AbsoluteFill, Easing, Img, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { HEEBO } from "../fonts";
import { clamp, fadeOut } from "../pop";
import { dir, pick } from "../lang";
import landgrid from "./landgrid.json";
import type { Props } from "../schemas";

const fontFamily = HEEBO;

// Blocky map of Eurasia rasterized from Natural Earth 50m land (scripts/landgrid.mjs), 2° per cell.
const { LON0, LAT0, STEP, grid } = landgrid as { LON0: number; LAT0: number; STEP: number; grid: string[] };
const ROWS = grid.length, COLS = grid[0].length;
const isLand = (c: number, r: number) => r >= 0 && r < ROWS && c >= 0 && c < COLS && grid[r][c] === "#";
const cell = (lon: number, lat: number) => ({ c: (lon - LON0) / STEP, r: (LAT0 - lat) / STEP });

// Pixel world map that pops in, then a dashed flight path draws from `from` to `to`
// with a plane riding the arc and a km counter ticking up.
// Labels and the unit follow `lang` (default he); each label's direction comes from its own text.
export const FlightMap: React.FC<Props<"FlightMap">> = ({
  lang, size = 880, top = 230, km = 9200,
  from = { lon: 35, lat: 31.8, label: pick(lang, "ישראל", "Israel") },
  to = { lon: 139.7, lat: 35.7, label: pick(lang, "יפן", "Japan") },
  unit = pick(lang, "ק״מ", "km"),
}) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const pop = spring({ frame: f, fps, config: { damping: 11, stiffness: 170 } });
  const out = fadeOut(f, 10, durationInFrames);
  const p = interpolate(f, [fps * 0.35, durationInFrames - fps * 0.35], [0, 1], {
    ...clamp, easing: Easing.inOut(Easing.cubic),
  });

  const W = size, H = (size * ROWS) / COLS;
  const px = W / COLS;
  const A = cell(from.lon, from.lat), B = cell(to.lon, to.lat);
  // quadratic arc bowing north
  const ctrl = { c: (A.c + B.c) / 2, r: Math.min(A.r, B.r) - 9 };
  const at = (t: number) => ({
    c: (1 - t) ** 2 * A.c + 2 * (1 - t) * t * ctrl.c + t ** 2 * B.c,
    r: (1 - t) ** 2 * A.r + 2 * (1 - t) * t * ctrl.r + t ** 2 * B.r,
  });
  const pts = Array.from({ length: 41 }, (_, i) => at((i / 40) * p));
  const d = pts.map((q, i) => `${i ? "L" : "M"} ${(q.c + 0.5) * px} ${(q.r + 0.5) * px}`).join(" ");
  const head = at(p), ahead = at(Math.min(p + 0.02, 1));
  const ang = (Math.atan2(ahead.r - head.r, ahead.c - head.c) * 180) / Math.PI;
  const landed = spring({ frame: f - (durationInFrames - fps * 0.35), fps, config: { damping: 8, stiffness: 220 } });

  const Label = ({ q, text, s }: { q: { c: number; r: number }; text: string; s: number }) => (
    <div style={{ position: "absolute", left: (q.c + 0.5) * px, top: (q.r + 0.5) * px + px * 1.4, translate: "-50% 0", scale: `${s}`,
      fontFamily, fontWeight: 900, fontSize: px * 1.35, color: "#fff", direction: dir(text), whiteSpace: "nowrap",
      textShadow: `${px * 0.18}px ${px * 0.18}px 0 #000` }}>{text}</div>
  );

  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: top, opacity: out }}>
      <div style={{ position: "relative", width: W + px * 2, height: H + px * 2, scale: `${pop}`,
        background: "#c9a774", padding: px, boxShadow: `0 0 0 ${px * 0.5}px #7b5a33, 0 ${px}px ${px * 2}px rgba(0,0,0,.45)` }}>
        <svg width={W} height={H} style={{ display: "block", shapeRendering: "crispEdges" }}>
          {Array.from({ length: ROWS }, (_, r) => Array.from({ length: COLS }, (_, c) => {
            const land = isLand(c, r);
            const shade = (c * 7 + r * 13) % 5 === 0;
            // grass lip on land under water, foam on water beside land — reads as blocks, not noise
            const lip = land && !isLand(c, r - 1) && r > 0;
            const foam = !land && (isLand(c - 1, r) || isLand(c + 1, r) || isLand(c, r - 1) || isLand(c, r + 1));
            const fill = land ? (lip ? "#7cc444" : shade ? "#4f8f2b" : "#5fa834") : foam ? "#5a88e6" : shade ? "#3a63c9" : "#4271d6";
            return <rect key={`${r}-${c}`} x={c * px} y={r * px} width={px + 0.5} height={px + 0.5} fill={fill} />;
          }))}
          <path d={d} stroke="#ff3b3b" strokeWidth={px * 0.42} strokeDasharray={`${px * 0.8} ${px * 0.55}`} fill="none" />
        </svg>
        <div style={{ position: "absolute", inset: px }}>
          <Img src={staticFile("mc/Map_Player.png")} style={{ position: "absolute", width: px * 2.2, height: px * 2.2,
            left: (A.c + 0.5) * px, top: (A.r + 0.5) * px, translate: "-50% -50%", imageRendering: "pixelated" }} />
          <Label q={A} text={from.label} s={1} />
          <Img src={staticFile("mc/Map_X.png")} style={{ position: "absolute", width: px * 2.4, height: px * 2.4,
            left: (B.c + 0.5) * px, top: (B.r + 0.5) * px, translate: "-50% -50%", scale: `${landed}`, imageRendering: "pixelated" }} />
          <Label q={B} text={to.label} s={landed} />
          <div style={{ position: "absolute", left: (head.c + 0.5) * px, top: (head.r + 0.5) * px, translate: "-50% -50%",
            rotate: `${ang + 45}deg`, fontSize: px * 2.6, lineHeight: 1, opacity: p < 1 ? 1 : 0 }}>✈️</div>
        </div>
      </div>
      <div style={{ marginTop: px * 1.6, fontFamily, fontWeight: 900, fontSize: px * 2.1, color: "#fff", direction: dir(unit),
        textShadow: `${px * 0.2}px ${px * 0.2}px 0 #000`, scale: `${pop}` }}>
        {Math.round(km * p).toLocaleString("en-US")} {unit}
      </div>
    </AbsoluteFill>
  );
};
