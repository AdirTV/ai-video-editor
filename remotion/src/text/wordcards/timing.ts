// Turns WordCards props into absolute timings: each card's base/keyword/script line is matched to the
// first unused transcript word(s) that spell it, in order, so the cards land on the voice without hand-typed seconds.
// Pure TS (no JSX) so calculateMetadata can run it before the component renders.

export type TWord = { word: string; start: number; end: number };
export type TSegment = { words?: TWord[] };

export const PARTS = ["base", "keyword", "script"] as const;
export type Part = (typeof PARTS)[number];

export type CardIn = {
  base?: string;
  keyword?: string;
  script?: string;
  baseAt?: number;
  keywordAt?: number;
  scriptAt?: number;
  start?: number;
  end?: number;
};

export type Resolved = { start: number; end: number; at: Partial<Record<Part, number>> };

// Strip punctuation, niqqud and case so "מיינקראפט," matches "מיינקראפט".
export const norm = (s: string) =>
  s.normalize("NFKD").replace(/[֑-ׇ]/g, "").replace(/[^\p{L}\p{N}]+/gu, "").toLowerCase();

export const flatten = (segs: TSegment[]): TWord[] => segs.flatMap((s) => s.words ?? []);

// Index of the transcript word where `text` begins (matching all its words in a row), from `from` on.
const find = (words: TWord[], text: string, from: number): number => {
  const want = text.split(/\s+/).map(norm).filter(Boolean);
  if (!want.length) return -1;
  for (let i = from; i <= words.length - want.length; i++)
    if (want.every((w, k) => norm(words[i + k].word) === w)) return i;
  // ASR splits/joins words differently from what you typed: fall back to the first word alone
  for (let i = from; i < words.length; i++) if (norm(words[i].word) === want[0]) return i;
  return -1;
};

const LEAD = 0.12; // card cut lands a beat before its first word
const TAIL = 0.6; // last card holds this long after its last word

export const resolve = (cards: CardIn[], words: TWord[], offset = 0): { cards: Resolved[]; missing: string[] } => {
  const missing: string[] = [];
  let cursor = 0;
  const firstPass = cards.map((c, ci) => {
    const at: Partial<Record<Part, number>> = {};
    let lastEnd: number | undefined;
    for (const p of PARTS) {
      const text = c[p];
      if (!text) continue;
      const fixed = c[`${p}At` as const];
      if (fixed !== undefined) {
        at[p] = fixed;
        continue;
      }
      const i = words.length ? find(words, text, cursor) : -1;
      if (i < 0) {
        if (words.length) missing.push(`card ${ci + 1} ${p} "${text}"`);
        continue;
      }
      at[p] = words[i].start - offset;
      const n = text.split(/\s+/).filter(Boolean).length;
      lastEnd = words[Math.min(words.length - 1, i + n - 1)].end - offset;
      cursor = i + 1;
    }
    return { c, at, lastEnd };
  });

  const out: Resolved[] = [];
  let prevEnd = 0;
  firstPass.forEach(({ c, at, lastEnd }, i) => {
    const known = Object.values(at).filter((v): v is number => v !== undefined);
    const start = c.start ?? (known.length ? Math.max(prevEnd, Math.min(...known) - LEAD) : prevEnd);
    // unmatched lines without a time: stagger them after the card cut
    PARTS.filter((p) => c[p] && at[p] === undefined).forEach((p, k) => (at[p] = start + 0.15 + k * 0.35));
    const next = firstPass[i + 1];
    const nextKnown = next ? Object.values(next.at).filter((v): v is number => v !== undefined) : [];
    const end =
      c.end ??
      next?.c.start ??
      (nextKnown.length ? Math.min(...nextKnown) - LEAD : Math.max(start + 1, (lastEnd ?? Math.max(...Object.values(at).map(Number))) + TAIL));
    out.push({ start, end: Math.max(end, start + 0.2), at });
    prevEnd = out[out.length - 1].end;
  });
  return { cards: out, missing };
};
