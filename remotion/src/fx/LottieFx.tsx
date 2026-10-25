import { Lottie, LottieAnimationData } from "@remotion/lottie";
import { useEffect, useState } from "react";
import { AbsoluteFill, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { popOpacity, popScale } from "../pop";
import type { Props } from "../schemas";

// Noto animated emoji (Google, CC BY 4.0): "😂" -> 1f602. Pinned version (same files as "latest" when pinned);
// `npm run emoji` caches them in public/lottie/noto/, which is tried first so renders work offline.
const NOTO_VERSION = "17.0"; // keep in sync with scripts/emoji.mjs
const notoCode = (emoji: string) =>
  [...emoji].map((c) => c.codePointAt(0)!.toString(16)).filter((h) => h !== "fe0f").join("_");

const sources = (src?: string, emoji?: string): string[] => {
  if (emoji) {
    const c = notoCode(emoji);
    return [staticFile(`lottie/noto/${c}.json`), `https://fonts.gstatic.com/s/e/notoemoji/${NOTO_VERSION}/${c}/lottie.json`];
  }
  if (!src) throw new Error("LottieFx needs src or emoji");
  return [/^https?:/.test(src) ? src : staticFile(src)]; // else a file under public/ (e.g. "lottie/fire.json")
};

// First source that answers with JSON wins.
const fetchFirst = async (urls: string[]): Promise<LottieAnimationData> => {
  for (const [i, u] of urls.entries()) {
    const r = await fetch(u).catch(() => null);
    if (r?.ok) return r.json();
    if (i === urls.length - 1) throw new Error(`LottieFx: can't load ${u} (${r?.status ?? "network error"})`);
  }
  throw new Error("LottieFx: nothing to load");
};

// A ready-made Lottie animation (LottieFiles JSON or an animated emoji) placed on the frame, popping in/out.
export const LottieFx: React.FC<Props<"LottieFx">> = ({ src, emoji, size = 360, x, y, loop = true, speed = 1, pop = true, rotate = 0 }) => {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const [handle] = useState(() => delayRender("Loading Lottie"));
  const [data, setData] = useState<LottieAnimationData | null>(null);

  useEffect(() => {
    fetchFirst(sources(src, emoji))
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
