// Text direction from the text itself: Hebrew/Arabic → rtl, everything else → ltr.
// Components use this instead of a fixed direction so the same graphic works in any language.
export type Lang = "he" | "en";
export const dir = (text: string | undefined): "rtl" | "ltr" =>
  /[֐-׿؀-ۿ]/.test(text ?? "") ? "rtl" : "ltr";
export const pick = (lang: Lang | undefined, he: string, en: string) => (lang === "en" ? en : he);
