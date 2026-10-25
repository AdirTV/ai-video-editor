// Text direction from the text itself: Hebrew/Arabic → rtl, everything else → ltr.
// Components use this instead of a fixed direction so the same graphic works in any language.
export type Lang = "he" | "en";
export const dir = (text: string | undefined): "rtl" | "ltr" =>
  /[֐-׿؀-ۿ]/.test(text ?? "") ? "rtl" : "ltr";
export const pick = (lang: Lang | undefined, he: string, en: string) => (lang === "en" ? en : he);

// Strip punctuation, niqqud and case so "מיינקראפט," matches "מיינקראפט" (transcript matching, caption highlights).
export const norm = (s: string) =>
  s.normalize("NFKD").replace(/[\u0591-\u05C7]/g, "").replace(/[^\p{L}\p{N}]+/gu, "").toLowerCase();
