import type { Cap } from "./Captions";

const Y = "#FFD84D", PINK = "#FF7BA6", BLUE = "#6FC8FF", BROWN = "#E2B07A";

// Timeline seconds from forced alignment of the script against the voiceover.
export const siftCaps: Cap[] = [
  { start: 0.04, end: 0.91, text: "עומדים להוסיף" },
  { start: 0.91, end: 1.59, text: "מימד חדש", hl: { מימד: Y, חדש: Y } },
  { start: 1.59, end: 2.33, text: "למיינקראפט?!" },
  { start: 2.33, end: 2.87, text: "למימד הזה" },
  { start: 2.87, end: 3.23, text: "קוראים" },
  { start: 3.23, end: 3.8, text: "THE SIFT", hl: { THE: PINK, SIFT: PINK } },
  { start: 3.8, end: 4.34, text: "והוא מגיע" },
  { start: 4.34, end: 5.08, text: "למיינקראפט הרגיל" },
  // 5.08–6.40: "אלפיים עשרים ושבע" is carried by the big "2027" graphic
  { start: 6.4, end: 6.92, text: "כבר הראו לנו" },
  { start: 6.92, end: 7.23, text: "הצצה" },
  { start: 7.23, end: 8.29, text: "עם צמחייה ורודה", hl: { ורודה: PINK } },
  { start: 8.29, end: 9.48, text: "והיצור הכחול הזה", hl: { הכחול: BLUE } },
  { start: 9.48, end: 10.1, text: "שנראה קצת" },
  { start: 10.1, end: 10.76, text: "כמו ארנב", hl: { ארנב: BROWN } },
  { start: 10.76, end: 11.2, text: "עברתי על" },
  { start: 11.2, end: 11.88, text: "המימד החדש" },
  { start: 11.88, end: 12.71, text: "ועל שאר ההכרזות", hl: { ההכרזות: BLUE } },
  { start: 12.71, end: 13.43, text: "בסרטון המלא", hl: { המלא: Y } },
  { start: 13.43, end: 13.95, text: "אז תלחצו" },
  { start: 13.95, end: 14.35, text: "כאן למטה" },
  { start: 14.35, end: 15.217, text: "כדי לצפות בו" },
];
