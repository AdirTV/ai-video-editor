import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { HEEBO } from "../fonts";
import { clamp, fadeOut } from "../pop";
import { dir } from "../lang";
import type { Props } from "../schemas";

const fontFamily = HEEBO;

// Minecraft's item hover tooltip (dark panel, purple gradient border) used as a price tag.
// Lines appear one by one; a line with `count` rolls its number up from 0 (e.g. the yen price).

export const ItemTooltip: React.FC<Props<"ItemTooltip">> = ({
  lines, top = 1180, scale = 1, tilt = -3,
}) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const u = 7 * scale;
  const pop = spring({ frame: f, fps, config: { damping: 10, stiffness: 200 } });
  const out = fadeOut(f, 8, durationInFrames);

  return (
    <AbsoluteFill style={{ alignItems: "center", paddingTop: top, opacity: out }}>
      <div style={{ scale: `${pop}`, rotate: `${tilt}deg`, background: "rgba(16,0,16,.94)", padding: `${3 * u}px ${6 * u}px ${4 * u}px`,
        // the two-tone purple border of the vanilla tooltip
        boxShadow: `inset 0 0 0 ${u}px rgba(16,0,16,.94), inset 0 0 0 ${2 * u}px #5000ff, 0 0 0 ${u}px rgba(16,0,16,.94), 0 ${2 * u}px ${5 * u}px rgba(0,0,0,.5)`,
        borderImage: "linear-gradient(#5000ff, #28007f) 1" }}>
        {lines.map((l, i) => {
          const t0 = (l.at ?? i * 0.35) * fps;
          const s = spring({ frame: f - t0, fps, config: { damping: 12, stiffness: 220 } });
          const n = l.count != null ? Math.round(l.count * interpolate(f - t0, [0, fps * 0.7], [0, 1], clamp)) : null;
          const text = n != null ? `${l.prefix ?? ""}${n.toLocaleString("en-US")}${l.suffix ?? ""}` : l.text;
          return (
            <div key={i} style={{ fontFamily, fontWeight: i ? 800 : 900, fontSize: (i ? 13 : 16) * u, lineHeight: 1.25,
              color: l.color ?? (i ? "#AAAAAA" : "#FFFFFF"), direction: dir(l.text || text), textAlign: "center",
              textShadow: `${u * 0.9}px ${u * 0.9}px 0 #3f3f3f`, opacity: s, translate: `0 ${(1 - s) * 2 * u}px`, whiteSpace: "nowrap" }}>
              {text}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
