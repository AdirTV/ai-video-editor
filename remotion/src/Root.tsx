import { Composition } from "remotion";
import { CTA } from "./CTA";
import { BigText } from "./sift/BigText";
import { Captions } from "./sift/Captions";
import { Morph } from "./sift/Morph";
import { siftCaps } from "./sift/caps";
import { Alarm } from "./ice/Alarm";
import { Frost } from "./ice/Frost";
import { LightMeter } from "./ice/LightMeter";
import { Sticker } from "./ice/Sticker";
import { YouDied } from "./ice/YouDied";
import { YouTubeCard } from "./ice/YouTubeCard";
import { Advancement } from "./japan/Advancement";
import { RouteMap } from "./japan/RouteMap";
import { SpeedrunTimer } from "./japan/SpeedrunTimer";

// duration from a "seconds" prop
const bySeconds = ({ props }: { props: { seconds?: number } }) => ({ durationInFrames: Math.ceil((props.seconds ?? 1) * 60) });

const FPS = 60;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition id="CTA" component={CTA} durationInFrames={108} fps={FPS} width={1080} height={1920}
        defaultProps={{ label: "לסרטון המלא", accent: "#FFD84D" }} />
      <Composition id="SiftCaptions" component={Captions} durationInFrames={913} fps={FPS} width={1080} height={1920}
        defaultProps={{ caps: siftCaps }} />
      <Composition id="Captions" component={Captions} fps={FPS} width={1080} height={1920}
        durationInFrames={60} defaultProps={{ caps: siftCaps, top: 980, size: 118, seconds: 1 }}
        calculateMetadata={({ props }) => ({ durationInFrames: Math.ceil((props.seconds ?? 1) * FPS) })} />
      <Composition id="Pop2027" component={BigText} durationInFrames={78} fps={FPS} width={1080} height={1920}
        defaultProps={{ text: "2027", color: "#FFD84D" }} />
      <Composition id="BlubToRabbit" component={Morph} durationInFrames={60} fps={FPS} width={1080} height={1920}
        defaultProps={{ from: "blub.png", to: "rabbit.png", swapAt: 23 }} />
      <Composition id="Frost" component={Frost} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ grow: 1.2, tint: 0.22, seconds: 2 }} calculateMetadata={bySeconds} />
      <Composition id="YouDied" component={YouDied} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 1.6 }} calculateMetadata={bySeconds} />
      <Composition id="LightMeter" component={LightMeter} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ label: "רמת אור", warn: "חזק מדי!", fill: 0.9, seconds: 1.6 }} calculateMetadata={bySeconds} />
      <Composition id="Alarm" component={Alarm} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ text: "זהירות!", seconds: 1.2 }} calculateMetadata={bySeconds} />
      <Composition id="Sticker" component={Sticker} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ text: "חדש!", bg: "#6FC8FF", seconds: 1.2 }} calculateMetadata={bySeconds} />
      <Composition id="YouTubeCard" component={YouTubeCard} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 4.58, thumb: "ice/thumb.png", title: "כל הדברים החדשים במיינקראפט לייב 2026!",
          channel: "אדיר טיוי", meta: "הועלה עכשיו", tapAt: 2.43 }} calculateMetadata={bySeconds} />
      <Composition id="Advancement" component={Advancement} fps={FPS} width={1920} height={1080} durationInFrames={60}
        defaultProps={{ seconds: 3, text: "הגעת לחנות מיינקראפט ביפן", icon: "Emerald.png", frame: "challenge" as const, scale: 1 }}
        calculateMetadata={bySeconds} />
      <Composition id="AdvancementV" component={Advancement} fps={FPS} width={1080} height={1920} durationInFrames={60}
        defaultProps={{ seconds: 3, text: "נסעת במונורייל", icon: "Minecart.png", frame: "task" as const, scale: 0.8, top: 260, side: "center" as const }}
        calculateMetadata={bySeconds} />
      <Composition id="RouteMap" component={RouteMap} fps={FPS} width={1920} height={1080} durationInFrames={60}
        defaultProps={{ seconds: 5, size: 900, stops: [
          { x: 0.15, y: 0.2, label: "המלון" }, { x: 0.35, y: 0.45, label: "מטרו", icon: "Minecart.png" },
          { x: 0.62, y: 0.55, label: "מונורייל", icon: "Minecart.png" }, { x: 0.82, y: 0.82, label: "חנות מיינקראפט" } ] }}
        calculateMetadata={bySeconds} />
      <Composition id="SpeedrunTimer" component={SpeedrunTimer} fps={FPS} width={1920} height={1080} durationInFrames={60}
        defaultProps={{ seconds: 6, from: 0, to: 3083, scale: 0.9, splits: [
          { label: "יציאה מהמלון", at: 0 }, { label: "לוסון", at: 134 }, { label: "מטרו", at: 422 },
          { label: "מונורייל", at: 1125 }, { label: "אודאיבה", at: 2563 }, { label: "דייברסיטי", at: 2903 },
          { label: "חנות מיינקראפט", at: 3083 } ] }}
        calculateMetadata={bySeconds} />
    </>
  );
};
