# Motion recipes (learned from downloaded editor project files)

Pulled out of 6 Premiere projects (`text`, `minecraft`, `black wood introo`, `invideo`, `project file` = "Gojo and Toji")
and 4 After Effects projects (`text pop`, Mr Beast `effect 2` / `effect 3`), 2026-10-21. Numbers are the editor's real
keyframes. Times are seconds from the clip's start; positions are in frame units (0.5 = centre, 1.0 = bottom/right edge).

Constant across everything: **every Transform has Shutter Angle 360 (motion blur on)**. Fast moves only read as
smooth because of the blur. In Remotion that means faking blur on fast frames (or keeping the moves short).

## Entrances (the clip/image/sticker itself)

**Slide in + jelly land** (the most used recipe; images, cut-outs, stickers, text):
- Position from off-screen (y 2.2–3.1, or x 3.2) → 0.5 over **0.65 s**, ease out ~67%, ease in ~78% (hard brake).
- Starting 0.38 s in (just as it lands), Anchor Point wobble on the motion axis: 0.5 → **+3.3%** (0.2 s) → **−2.1%**
  (0.3 s) → 0.5 (0.45 s). It's the overshoot after landing, done with the anchor so position stays clean.
- Optional squash on landing: Scale Height 100 → 90 → 100 → 97 → 100 over 0.95 s.
- Variants on top of the same slide: **spin-in** Rotation −360 → 5 → 0 (0.87 s, then 0.55 s);
  **3D swing** Basic 3D Swivel or Tilt 16 → −8 → 2 → 0 (0.6 / 0.3 / 0.45 s); **sticker look** Roughen Edges
  (Edge Type 2, Border 100) + Drop Shadow; **pixel reveal** Mosaic blocks animated big → small; **flash** Tint 10 keys.

**Unfold spin** (title cards): Scale Height 1 → 100 (0.7 s) + Rotation 360 → 0 (1.28 s) + Skew 2.4 → 0 + anchor wobble.

## Text (Essential Graphics text + VR Glow on almost every line)

Glow is always the same: **VR Glow, radius 60, brightness 0.7, saturation 1, luma threshold 0.5**.

- **Stretch in**: Scale Width 0.1 → 100 over 0.6 s (height stays 100). Most common text in.
- **Slam**: Scale Width 0.1 → 100 → **103** → 100 in 0.23 s + Rotation 2.6 → 0 (0.5 s) + a vertical settle
  0.528 → 0.489 → 0.503 → 0.499 → 0.5 (keys at 0, 0.1, 0.23, 0.4, 0.57, 0.7, 0.9 s).
- **Punch**: Scale 75 → 110/115 → 100 in 0.12 s (Width overshoots more than Height). For a beat/word hit.
- **Grow in**: Scale Height 0.1 → 100 in 0.4 s and Width 0.1 → 100 in 0.6 s (height first, then width).
- **Exit = fall**: Position y 0.5 → 1.53 over 0.85 s, ease in 100% (starts slow, leaves fast). Text never fades
  out, it drops off screen.
- From AE `text pop`: per-letter overshoot pop (`1 − cos(t·2·2π)/e^{7t}`), Deep Glow and CC Light Sweep.
  → already built as Remotion `TextPop`.
- **Documentary cold open** (narrated horror/story openers): full-screen cards cut on the voice, each = small bold
  base line + huge condensed keyword (blur-in, blurred giant echo behind, glow if coloured) + handwritten line,
  slow push-in, grain + vignette; a cream card for the "normal" beat, then "ואז" alone on black, then red/mono +
  RGB-split glitch for the danger. → Remotion `WordCards`: type only the words, timings come from `transcript.json`.

## Camera moves (on an Adjustment Layer above everything)

**Impact shake + zoom-out** (on a hit, a cut or a reveal):
- Scale 150 → 100 over 0.37 s, while
- Position x jitters ±0.5–0.7% with decaying keys (0, 0.02, 0.05, 0.1, 0.17, 0.27, 0.73 s), and
- Rotation −1.5 → 1.125 → −0.75 → 0.6 → −0.3 → 0 (each swing ~half the previous).
- **Then 4 × Mirror (angles 0/90/180/270 at the frame edges, centres at 0.898/0.102 of the frame) + a final
  Transform** so the zoom/shake shows mirrored picture at the edges instead of black. That's the trick that lets
  them shake hard without edge gaps.

**Flash shake** (the start of a new section):
- Tint 60 → 0 (1.45 s), Gaussian Blur 20 → 0 (0.67 s), Scale 105 → 100 (0.95 s),
- 13-key shake every ~0.05 s for 0.625 s: Rotation 2.2, −1.45, 0.95, −0.6, 0.35, −0.25, 0.15, −0.1 … 0;
  Position x ±1.3% decaying the same way.

**Handheld**: baked wiggle on Motion/Transform Position (and Rotation), ~1000+ keys on a long adjustment layer.

Other tools in the projects: Ultra Key (green-screen fight clouds, effects), Gaussian Blur on adjustment layers
behind text, Mister Horse "Overshoot Position & Rotate" presets, Color Emboss + Tint for a stamped look.

## Mr Beast "ELIMINATED" (AE `effect 2`)

Freeze-ish moment on a person: the frame goes grey/darker (Tint), the person is cut out (Keylight / Picsart
background remover clip), light rays behind them (CC Light Sweep), a big red **X** follows them, "ELIMINATED" in
white with Deep Glow, Venetian Blinds as the transition in, Animation Composer pop on the text.
`effect 3` = text attached to a person with the Motion Tracker (+ Motion Tile).

## How to use these here

- Remotion graphics: use the curves above instead of generic easing (slide 0.65 s hard-brake + anchor wobble,
  slam with 103% overshoot, fall-out exit, decaying shake where each swing is ~0.6× the previous).
- Premiere builds: the impact shake / flash shake are adjustment-layer recipes; add Mirror ×4 when zooming or shaking.
