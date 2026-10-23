import { loadFont } from "@remotion/google-fonts/Inter";
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";
import { dir } from "../lang";
import type { Props } from "../schemas";

const { fontFamily } = loadFont("normal", { weights: ["600", "800", "900"], subsets: ["latin"] });

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// A live-chat message the streamer reacts to (Twitch-style dark card, coloured username). The message can
// arrive in parts: each part appears at its own second, and a `big` part slams in on its own line with a
// shake — the "(Only u played this game)" punchline landing as she reads it.
export const ChatMessage: React.FC<Props<"ChatMessage">> = ({
  user, userColor = "#BF94FF", parts, top = 900, size = 58, accent = "#9146FF",
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const shown = parts.filter((p) => frame >= Math.round((p.at ?? 0) * fps));
  const small = shown.filter((p) => !p.big);
  const big = shown.filter((p) => p.big);
  // the card shakes for a few frames whenever a big part lands
  const lastBig = big.length ? Math.round((big[big.length - 1].at ?? 0) * fps) : -99;
  const k = frame - lastBig;
  const shake = k >= 0 && k < 14 ? Math.sin(k * 2.3) * interpolate(k, [0, 14], [16, 0], clamp) : 0;
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "flex-start", paddingTop: top }}>
      <div
        style={{
          fontFamily, maxWidth: 960, background: "rgba(24,24,27,0.94)", borderRadius: 22,
          borderLeft: `10px solid ${accent}`, padding: `${size * 0.42}px ${size * 0.55}px`,
          boxShadow: "0 18px 40px rgba(0,0,0,.55)", transformOrigin: "50% 100%",
          scale: popScale(frame, durationInFrames, 10, 8), opacity: popOpacity(frame, durationInFrames, 8),
          translate: `${shake}px ${interpolate(frame, [0, 10], [40, 0], { ...clamp, easing: Easing.out(Easing.cubic) })}px`,
          rotate: `${shake * 0.08}deg`,
        }}
      >
        <div style={{ fontSize: size, lineHeight: 1.25, color: "#EFEFF1", fontWeight: 600, direction: dir(small.map((p) => p.text).join(" ")) }}>
          <span style={{ color: userColor, fontWeight: 800 }}>{user}</span>
          <span style={{ color: "#ADADB8" }}>: </span>
          {small.map((p, i) => <Part key={i} text={p.text} at={p.at ?? 0} />)}
        </div>
        {big.map((p, i) => (
          <Slam key={i} text={p.text} at={p.at ?? 0} size={size * 1.6} color={p.color ?? "#FF8AD8"} />
        ))}
      </div>
    </AbsoluteFill>
  );
};

const Part: React.FC<{ text: string; at: number }> = ({ text, at }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame - at * fps;
  return <span style={{ opacity: interpolate(t, [0, 4], [0, 1], clamp) }}>{text} </span>;
};

const Slam: React.FC<{ text: string; at: number; size: number; color: string }> = ({ text, at, size, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame - at * fps;
  return (
    <div
      style={{
        fontSize: size, fontWeight: 900, color, lineHeight: 1.1, marginTop: size * 0.18, textWrap: "balance",
        scale: interpolate(t, [0, 5, 9], [2.2, 0.92, 1], { ...clamp, easing: Easing.out(Easing.quad) }),
        opacity: interpolate(t, [0, 2], [0, 1], clamp), textShadow: `0 0 ${size * 0.35}px ${color}66`,
      }}
    >
      {text}
    </div>
  );
};
