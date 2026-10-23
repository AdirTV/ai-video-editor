import { Fragment } from "react";
import { loadFont as loadHeebo } from "@remotion/google-fonts/Heebo";
import { loadFont as loadKarantina } from "@remotion/google-fonts/Karantina";
import { loadFont as loadGveret } from "@remotion/google-fonts/GveretLevin";
import { AbsoluteFill, Audio, Img, interpolate, Sequence, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { brand } from "../brand";
import { dir } from "../lang";
import type { Props } from "../schemas";
import { enterStyle, glow, Glitch, GlitchFilters, Grain, Pool, useEnter, Vignette } from "./wordcards/fx";
import { ZoomTail } from "./wordcards/transition";
import { flatten, resolve, type Resolved, type TSegment } from "./wordcards/timing";

const BASE = loadHeebo("normal", { weights: ["500", "800", "900"], subsets: ["hebrew", "latin"] }).fontFamily;
const BIG = loadKarantina("normal", { weights: ["700"], subsets: ["hebrew", "latin"] }).fontFamily;
const SCRIPT = loadGveret("normal", { weights: ["400"], subsets: ["hebrew", "latin"] }).fontFamily;

type P = Props<"WordCards">;
type CardP = P["cards"][number];
type Theme = NonNullable<CardP["theme"]>;

const THEMES: Record<Theme, { bg?: string; pool?: string; ink: string; grade?: string }> = {
  dark: { bg: "#050505", pool: "38,38,40", ink: "#f4f4f4" },
  cream: { bg: "#ece6d6", ink: "#141414" },
  red: { bg: "radial-gradient(ellipse 75% 70% at 50% 55%, #7a1a10 0%, #2a0604 70%, #120202 100%)", ink: "#f4f4f4" },
  mono: { bg: "#000", pool: "70,70,70", ink: "#f4f4f4", grade: "grayscale(1)" },
  clear: { ink: "#f4f4f4" },
};

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

// Keyword size that keeps the line inside `maxW` (Karantina is narrow: ~0.36 em per letter).
const fit = (text: string, want: number, maxW: number, em = 0.36) => Math.min(want, maxW / Math.max(1, text.length * em));

const Line: React.FC<{ at: number; text: string; family: string; weight: number; size: number; color: string; glowColor?: string; rotate?: number; rise?: number; spacing?: number; dur?: number }> = ({
  at, text, family, weight, size, color, glowColor, rotate = 0, rise = 0, spacing, dur,
}) => {
  const p = useEnter(at, dur);
  if (p <= 0) return null;
  return (
    <div style={{ direction: dir(text), whiteSpace: "nowrap", fontFamily: family, fontWeight: weight, fontSize: size, lineHeight: 1, color, letterSpacing: spacing, textShadow: glowColor ? glow(glowColor) : undefined, rotate: `${rotate}deg`, ...enterStyle(p, rise) }}>
      {text}
    </div>
  );
};

// One card: small base line, huge keyword (optionally glowing, with a blurred echo behind), a handwritten line
// under it, an optional image. `t` values are seconds from the card's start.
const Card: React.FC<{ card: CardP; r: Resolved; len: number }> = ({ card, r, len }) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const t = frame / fps;
  const theme = THEMES[card.theme ?? "dark"];
  const vertical = height > width;
  const u = vertical ? width / 1080 : width / 1920;
  const rel = (p: "base" | "keyword" | "script") => (r.at[p] ?? r.start) - r.start;
  const ink = theme.ink;
  const keyColor = card.keyColor ?? ink;
  const keyGlow = card.glow ?? (card.keyColor !== undefined && card.keyColor !== ink) ? keyColor : undefined;
  const scriptColor = card.scriptColor ?? (card.theme === "cream" ? ink : brand.accent);
  const scriptGlow = card.scriptGlow && scriptColor;
  const center = card.layout === "center" || vertical;
  const tracked = card.layout === "center";

  const push = interpolate(t, [0, len], [0, card.zoom ?? 0.05], clamp);
  const kAt = rel("keyword");
  const glitchOn = !!card.glitch && ((t >= kAt && t < kAt + 0.12) || t >= len - 0.22);

  const keySize = card.keyword ? fit(card.keyword, (tracked ? 130 : 380) * u, width * (vertical ? 0.86 : 0.6), tracked ? 0.75 : 0.36) : 0;
  const baseSize = (tracked ? 34 : card.keyword ? 110 : 170) * u;
  const scriptSize = (card.keyword ? 170 : 240) * u;
  const iconSize = (card.iconSize ?? 260) * u;
  const iconLeft = (card.iconSide ?? "left") === "left";

  const column: React.CSSProperties = center
    ? { position: "absolute", left: 0, right: 0, top: height * (vertical ? 0.3 : 0.34), display: "flex", flexDirection: "column", alignItems: "center", gap: 10 * u }
    : { position: "absolute", top: height * 0.27, right: width * (card.icon && !iconLeft ? 0.26 : 0.14), display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 * u };

  const echoP = useEnter(kAt, 0.4);

  return (
    <AbsoluteFill style={{ background: theme.bg, filter: theme.grade }}>
      {theme.pool ? <Pool color={theme.pool} /> : null}
      {card.theme === "cream" ? <AbsoluteFill style={{ background: "radial-gradient(ellipse 45% 50% at 42% 45%, #f6f1e4 0%, transparent 100%)" }} /> : null}
      <AbsoluteFill>
        <Glitch on={glitchOn} strength={1.2}>
          <AbsoluteFill style={{ transform: `scale(${1 + push})` }}>
            {card.keyword && card.echo !== false && echoP > 0 ? (
              <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", opacity: echoP * (card.theme === "cream" ? 0.12 : 0.16), filter: "blur(10px)" }}>
                <div style={{ direction: dir(card.keyword), whiteSpace: "nowrap", fontFamily: BIG, fontWeight: 700, fontSize: keySize * 2.3, color: card.theme === "cream" ? "#000" : keyColor, transform: `translateX(${(vertical ? 0 : 0.12) * width}px)` }}>
                  {card.keyword}
                </div>
              </div>
            ) : null}
            <div style={column}>
              {card.base ? <Line at={rel("base")} text={card.base} family={BASE} weight={tracked ? 500 : 800} size={baseSize} color={ink} spacing={tracked ? 18 * u : undefined} dur={0.3} /> : null}
              {card.keyword ? (
                <Line at={kAt} text={card.keyword} family={tracked ? BASE : BIG} weight={tracked ? 900 : 700} size={keySize} color={keyColor} glowColor={keyGlow} rise={30 * u} spacing={tracked ? 18 * u : undefined} />
              ) : null}
              {card.script ? (
                <div style={{ marginTop: card.keyword ? -scriptSize * 0.25 : 0, marginRight: center ? 0 : width * 0.08 }}>
                  <Line at={rel("script")} text={card.script} family={SCRIPT} weight={400} size={scriptSize} color={scriptColor} glowColor={scriptGlow || undefined} rotate={-5} />
                </div>
              ) : null}
            </div>
            {card.icon ? <Icon src={card.icon} at={Math.max(0, kAt) + 0.04} size={iconSize} style={vertical ? { left: (width - iconSize) / 2, top: height * 0.62 } : iconLeft ? { left: width * 0.1, top: height * 0.36 } : { right: width * 0.06, top: height * 0.36 }} /> : null}
          </AbsoluteFill>
        </Glitch>
      </AbsoluteFill>
      {card.theme !== "clear" ? <Vignette strength={card.theme === "cream" ? 0.55 : 0.85} color={card.theme === "cream" ? "40,34,24" : "0,0,0"} /> : null}
    </AbsoluteFill>
  );
};

const Icon: React.FC<{ src: string; at: number; size: number; style: React.CSSProperties }> = ({ src, at, size, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const p = useEnter(at, 0.3);
  if (p <= 0) return null;
  const bob = Math.sin((frame / fps - at) * 2.2) * 6;
  return (
    <Img src={staticFile(src)} style={{ position: "absolute", width: size, height: size, objectFit: "contain", ...style, opacity: p, filter: `blur(${(1 - p) * 12}px) drop-shadow(0 10px 18px rgba(0,0,0,0.45))`, transform: `translateY(${bob}px) rotate(${(1 - p) * -12}deg) scale(${0.85 + p * 0.15})` }} />
  );
};

// Documentary-style kinetic word cards on a voiceover: each card = small base line + huge keyword + handwritten line,
// cut on the voice. Timings come from transcript.json (calculateMetadata fills `resolved`), or from explicit *At props.
export const WordCards: React.FC<P> = ({ cards, resolved, audio, offset = 0, grain = true }) => {
  const { fps, width, height } = useVideoConfig();
  const vertical = height > width;
  const rs = resolved ?? resolve(cards, [], 0).cards;
  const clear = cards.every((c) => c.theme === "clear");
  return (
    <AbsoluteFill>
      <GlitchFilters />
      {audio ? <Audio src={staticFile(audio)} startFrom={Math.round(offset * fps)} /> : null}
      {cards.map((c, i) => {
        const r = rs[i];
        const from = Math.round(r.start * fps);
        const dur = Math.max(1, Math.round(r.end * fps) - from);
        const name = `${i + 1}. ${c.keyword ?? c.base ?? c.script ?? ""}`;
        const zoom = (c.transition ?? "zoom") === "zoom" && i < cards.length - 1;
        return (
          <Fragment key={i}>
            <Sequence from={from} durationInFrames={dur} name={name}>
              <Card card={c} r={r} len={dur / fps} />
            </Sequence>
            {zoom ? (
              <ZoomTail cut={(from + dur) / fps} cardStart={from / fps} blend={c.theme === "cream" ? "multiply" : "screen"} origin={vertical || c.layout === "center" ? "50% 42%" : "62% 42%"} name={`${name} → zoom`}>
                <Card card={c} r={r} len={dur / fps} />
              </ZoomTail>
            ) : null}
          </Fragment>
        );
      })}
      {grain && !clear ? <AbsoluteFill style={{ zIndex: 20 }}><Grain /></AbsoluteFill> : null}
    </AbsoluteFill>
  );
};

// Fetches the transcript, resolves every card's timing and sizes the composition to the last card.
export const wordCardsMetadata = (fps: number) => async ({ props }: { props: P }) => {
  let segs: TSegment[] = [];
  if (props.transcript) {
    const res = await fetch(staticFile(props.transcript));
    if (!res.ok) throw new Error(`WordCards: can't read transcript ${props.transcript} (put it under remotion/public/)`);
    segs = await res.json();
  }
  const { cards, missing } = resolve(props.cards, flatten(segs), props.offset ?? 0);
  if (missing.length) console.warn(`WordCards: not found in transcript, staggered instead: ${missing.join("; ")}`);
  const last = cards.length ? cards[cards.length - 1].end : 1;
  return { props: { ...props, resolved: cards }, durationInFrames: Math.ceil((props.seconds ?? last) * fps) };
};
