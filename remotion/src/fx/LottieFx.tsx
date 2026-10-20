import { Lottie, LottieAnimationData } from "@remotion/lottie";
import { useEffect, useState } from "react";
import { AbsoluteFill, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";

// Noto animated emoji (Google, CC BY 4.0): "😂" -> .../1f602/lottie.json
const notoUrl = (emoji: string) =>
  `https://fonts.gstatic.com/s/e/notoemoji/latest/${[...emoji]
    .map((c) => c.codePointAt(0)!.toString(16))
    .filter((h) => h !== "fe0f")
    .join("_")}/lottie.json`;

const resolve = (src?: string, emoji?: string) => {
  if (emoji) return notoUrl(emoji);
  if (!src) throw new Error("LottieFx needs src or emoji");
  return /^https?:/.test(src) ? src : staticFile(src); // else a file under public/ (e.g. "lottie/fire.json")
};

// A ready-made Lottie animation (LottieFiles JSON or an animated emoji) placed on the frame, popping in/out.
export const LottieFx: React.FC<{
  seconds?: number; src?: string; emoji?: string; size?: number; x?: number; y?: number;
  loop?: boolean; speed?: number; pop?: boolean; rotate?: number;
}> = ({ src, emoji, size = 360, x, y, loop = true, speed = 1, pop = true, rotate = 0 }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const [handle] = useState(() => delayRender("Loading Lottie"));
  const [data, setData] = useState<LottieAnimationData | null>(null);

  useEffect(() => {
    fetch(resolve(src, emoji))
      .then((r) => r.json())
      .then((json) => {
        setData(json);
        continueRender(handle);
      })
      .catch((err) => cancelRender(err));
  }, [handle, src, emoji]);

  if (!data) return null;
  const cx = x ?? width / 2;
  const cy = y ?? height / 2;
  return (
    <AbsoluteFill>
      <div
        style={{
          position: "absolute", left: cx - size / 2, top: cy - size / 2, width: size, height: size,
          rotate: `${rotate}deg`,
          scale: pop ? popScale(frame, durationInFrames, 10, 7) : 1,
          opacity: pop ? popOpacity(frame, durationInFrames, 7) : 1,
        }}
      >
        <Lottie animationData={data} loop={loop} playbackRate={speed} style={{ width: size, height: size }} />
      </div>
    </AbsoluteFill>
  );
};
