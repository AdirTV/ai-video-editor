import { loadFont } from "@remotion/google-fonts/Rubik";
import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

const { fontFamily } = loadFont("normal", { weights: ["500", "700", "900"], subsets: ["hebrew", "latin"] });
const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// "The full video is up": the thumbnail on a YouTube-style watch page (dark mode + ambient glow),
// card springs in, slow push, then a finger tap on the video at `tapAt` seconds.
export const YouTubeCard: React.FC<{
  seconds?: number; thumb: string; title: string; channel: string; meta: string; tapAt: number;
}> = ({ thumb, title, channel, meta, tapAt }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const src = staticFile(thumb);
  const enter = interpolate(frame, [0, 16], [0, 1], { ...clamp, easing: Easing.out(Easing.back(1.6)) });
  const push = interpolate(frame, [0, durationInFrames], [1, 1.05], clamp);
  const out = interpolate(frame, [durationInFrames - 6, durationInFrames], [1, 0], clamp);
  const tf = tapAt * fps;
  const press = interpolate(frame, [tf - 4, tf, tf + 6], [1, 0.95, 1], clamp);
  const ripple = interpolate(frame, [tf, tf + 18], [0, 1], clamp);
  const finger = interpolate(frame, [tf - 18, tf - 2], [0, 1], { ...clamp, easing: Easing.out(Easing.quad) });
  const prog = interpolate(frame, [tf, durationInFrames], [0, 0.12], clamp);
  const W = 1000, H = Math.round((W * 941) / 1672), X = 40, Y = 250;
  return (
    <AbsoluteFill style={{ background: "#0f0f0f", opacity: out, fontFamily }}>
      {/* ambient mode glow */}
      <Img src={src} style={{ position: "absolute", left: -200, top: Y - 260, width: 1480, height: H + 520,
        objectFit: "cover", filter: "blur(90px) saturate(1.6)", opacity: 0.55 }} />
      <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(15,15,15,0) 0%, rgba(15,15,15,0) 45%, #0f0f0f 70%)" }} />
      {/* top bar */}
      <div style={{ position: "absolute", top: 120, left: 40, right: 40, display: "flex", alignItems: "center", gap: 14,
        opacity: enter }}>
        <svg viewBox="0 0 28 20" width={78}><rect width={28} height={20} rx={5} fill="#ff0033" /><path d="M11 5.5 L19 10 L11 14.5Z" fill="#fff" /></svg>
        <span style={{ color: "#fff", fontWeight: 700, fontSize: 52, letterSpacing: -2 }}>YouTube</span>
      </div>
      <div style={{ position: "absolute", left: 0, top: 0, width: 1080, scale: push * (0.82 + 0.18 * enter),
        transformOrigin: "540px 600px", opacity: enter }}>
        {/* player */}
        <div style={{ position: "absolute", left: X, top: Y, width: W, height: H, borderRadius: 26, overflow: "hidden",
          scale: press, boxShadow: "0 30px 80px rgba(0,0,0,.6)" }}>
          <Img src={src} style={{ width: W, height: H, objectFit: "cover" }} />
          <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 10, background: "rgba(255,255,255,.3)" }}>
            <div style={{ width: `${prog * 100}%`, height: "100%", background: "#ff0033" }} />
          </div>
          <div style={{ position: "absolute", top: 22, right: 22, background: "#ff0033", color: "#fff", fontWeight: 900,
            fontSize: 44, padding: "4px 22px 8px", borderRadius: 12, direction: "rtl" }}>חדש!</div>
          {/* tap ripple */}
          <div style={{ position: "absolute", left: W / 2 - 160, top: H / 2 - 160, width: 320, height: 320, borderRadius: "50%",
            background: "rgba(255,255,255,.35)", scale: ripple * 1.6, opacity: ripple > 0 ? 1 - ripple : 0 }} />
          {/* play button */}
          <svg viewBox="0 0 68 48" width={170} style={{ position: "absolute", left: W / 2 - 85, top: H / 2 - 60,
            opacity: interpolate(frame, [tf, tf + 10], [1, 0], clamp), filter: "drop-shadow(0 6px 14px rgba(0,0,0,.5))" }}>
            <path d="M66.5 7.7c-.8-2.9-3-5.2-5.9-6C55.4.3 34 .3 34 .3S12.6.3 7.4 1.7c-2.9.8-5.1 3.1-5.9 6C.1 13 .1 24 .1 24s0 11 1.4 16.3c.8 2.9 3 5.2 5.9 6C12.6 47.7 34 47.7 34 47.7s21.4 0 26.6-1.4c2.9-.8 5.1-3.1 5.9-6C67.9 35 67.9 24 67.9 24s0-11-1.4-16.3z" fill="#ff0033" />
            <path d="M45 24 27 14v20z" fill="#fff" />
          </svg>
        </div>
        {/* title + channel */}
        <div style={{ position: "absolute", left: X + 10, right: X + 10, top: Y + H + 34, direction: "rtl", color: "#f1f1f1" }}>
          <div style={{ fontSize: 52, fontWeight: 700, lineHeight: 1.25 }}>{title}</div>
          <div style={{ fontSize: 34, color: "#aaa", marginTop: 12, fontWeight: 500 }}>{meta}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 22, marginTop: 30 }}>
            <div style={{ width: 92, height: 92, borderRadius: "50%", background: "linear-gradient(135deg,#ff3b3b,#8b0000)",
              border: "4px solid #333" }} />
            <span style={{ fontSize: 42, fontWeight: 700 }}>{channel}</span>
            <div style={{ marginRight: "auto", background: "#f1f1f1", color: "#0f0f0f", fontSize: 38, fontWeight: 700,
              padding: "14px 36px 18px", borderRadius: 60 }}>הרשמה</div>
          </div>
        </div>
      </div>
      {/* finger */}
      <div style={{ position: "absolute", left: 560, top: Y + H / 2 + 40 + (1 - finger) * 260, fontSize: 170, opacity: finger,
        scale: press, filter: "drop-shadow(0 10px 10px rgba(0,0,0,.5))" }}>👆</div>
    </AbsoluteFill>
  );
};
