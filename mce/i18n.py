"""Messages in Hebrew and English. The language comes from the content when known
(e.g. the transcript), else from ~/.mce/config.json "language", else English.

  from .i18n import t, set_lang
  set_lang("he"); t("black", s=1.2, e=1.5)
"""
import re

from .config import LANGUAGE

_lang = LANGUAGE if LANGUAGE in ("he", "en") else "en"

MSG = {
    # qa
    "black": ("🔴 מסך שחור {s:.2f}–{e:.2f}s", "🔴 Black frames {s:.2f}–{e:.2f}s"),
    "frame_gap": ("🔴 חור של {n} פריימים ב-V{t} ב-{at:.2f}s (פריים שחור בקאט)",
                  "🔴 {n}-frame gap on V{t} at {at:.2f}s (black frame at a cut)"),
    "black_half": ("🔴 חצי {half} של המסך שחור {s:.2f}–{e:.2f}s — גרפיקה/בי-רול נגמרים מוקדם מדי?",
                   "🔴 Black {half} half {s:.2f}–{e:.2f}s — a graphic or b-roll ends too early?"),
    "past_v1": ("🔴 {name} (V{t}) נגמר ב-{e:.2f}s אחרי סוף התמונה הבסיסית ({v1:.2f}s) — שאר המסך שחור",
                "🔴 {name} (V{t}) ends at {e:.2f}s, after the base picture ({v1:.2f}s) — the rest of the frame goes black"),
    "freeze": ("🟡 תמונה קפואה {s:.2f}–{e:.2f}s (בסדר אם זה מכוון)", "🟡 Frozen picture {s:.2f}–{e:.2f}s (fine if intended)"),
    "lufs": ("{mark} עוצמה כוללת {i:.1f} LUFS (יעד יוטיוב {target:.0f})", "{mark} Integrated loudness {i:.1f} LUFS (YouTube target {target:.0f})"),
    "peak": ("{mark} שיא {p:.1f} dBTP (מקסימום {max:.0f})", "{mark} True peak {p:.1f} dBTP (max {max:.0f})"),
    "lufs_fix": ("   → לתקן: לשנות את vo_lufs ב-{d:+.1f} dB ולבנות מחדש", "   → fix: change vo_lufs by {d:+.1f} dB and push again"),
    "silence": ("🟡 שקט מוחלט {s:.2f}–{e:.2f}s", "🟡 Dead air {s:.2f}–{e:.2f}s"),
    "v1_gap": ("🔴 חור ב-V1 בין {a:.2f} ל-{b:.2f}s", "🔴 Gap on V1 between {a:.2f} and {b:.2f}s"),
    "short_clip": ("🟡 קליפ קצר מאוד ({d:.2f}s) ב-V{t}: {name} @ {start:.2f}", "🟡 Very short clip ({d:.2f}s) on V{t}: {name} @ {start:.2f}"),
    "overlap": ("🟡 שתי גרפיקות חופפות: {a} ו-{b} @ {t:.2f}", "🟡 Two graphics overlap: {a} and {b} @ {t:.2f}"),
    "no_issues": ("✅ לא נמצאו בעיות", "✅ No issues found"),
    # notes
    "no_notes": ("אין הערות חדשות על הרצף.", "No new notes on the sequence."),
    "empty_note": ("(בלי טקסט)", "(no text)"),
    # music
    "m_natural": ("הסוף הטבעי של השיר ({end:.2f}s) נוחת על סוף הסרטון; מתחיל על תחילת תיבה ({s:.2f}s בשיר)",
                  "The song's own ending ({end:.2f}s) lands on the video's last frame; starts on a bar line ({s:.2f}s into the song)"),
    "m_drop": ("הדרופ ב-{d:.2f}s של השיר נוחת בדיוק ב-{hit:.2f}s בסרטון; השיר מתחיל על תחילת תיבה ({s:.2f}s בשיר){late}",
               "The drop at {d:.2f}s of the song lands exactly at {hit:.2f}s in the video; starts on a bar line ({s:.2f}s into the song){late}"),
    "m_late": (", {delay:.2f}s אחרי תחילת הסרטון", ", {delay:.2f}s after the video starts"),
    "m_energy": ("הקטע הכי אנרגטי בלי הפסקה (אנרגיה ממוצעת {e:.2f}); מתחיל על תחילת תיבה, אחרי {first:.2f}s של פתיחה שקטה",
                 "Most energetic stretch without a break (mean energy {e:.2f}); starts on a bar line, after {first:.2f}s of quiet intro"),
    "m_enters": ("השיר 'נכנס' ({t:.2f}s בשיר) בדיוק בסוף המעבר", "The song 'gets going' ({t:.2f}s into it) right as the crossfade ends"),
    "m_song": ("שיר {n} ({file}): {a:.2f}–{b:.2f}s, מהשנייה {off:.2f} בשיר", "Song {n} ({file}): {a:.2f}–{b:.2f}s, from {off:.2f}s into the song"),
    "m_xfade": (", נכנס בקרוס-פייד של {x:.2f}s", ", crossfading in over {x:.2f}s"),
    # timeline reasons / flags
    "r_excited": ("קול מתלהב", "excited voice"), "r_laugh": ("צחוק", "laugh"), "r_scream": ("צעקה", "scream"),
    "r_gasp": ("התנשפות", "gasp"), "r_explosion": ("פיצוץ", "explosion"), "r_game": ("פיק סאונד משחק", "game sound spike"),
    "r_health": ("ירידת חיים {a:.0f}→{b:.0f}", "health drop {a:.0f}→{b:.0f}"), "r_death": ("מסך מוות?", "death screen?"),
    "r_low": ("חיים נמוכים", "low health"), "r_clip": ("אמרת 'קליפ'", "you said 'clip'"), "r_hype": ("מילת התלהבות", "hype word"),
    "f_voice": ("🔥קול", "🔥voice"), "f_game": ("💥משחק", "💥game"), "f_laugh": ("😂צחוק", "😂laugh"),
    "f_scream": ("😱צעקה", "😱scream"), "f_explosion": ("💣פיצוץ", "💣boom"), "f_drop": ("💔ירידה", "💔hit"),
    "f_death": ("☠️מוות?", "☠️death?"), "f_menu": ("📦תפריט", "📦menu"), "f_idle": ("💤מת", "💤idle"), "f_clip": ("⭐קליפ", "⭐clip"),
    "tl_title": ("ציר זמן", "Timeline"), "tl_candidates": ("רגעים מועמדים (מדורג)", "Candidate moments (ranked)"),
    "tl_full": ("ציר מלא (שורה = 10 שניות)", "Full timeline (row = 10 s)"),
    "tl_head": ("| זמן | מה נאמר | חיים | סימנים |", "| Time | What was said | Health | Signals |"),
    "tl_hhead": ("| זמן | ציון | למה |", "| Time | Score | Why |"),
    # markers
    "mk_fix": ("🔴 לתקן", "🔴 FIX"), "mk_broll": ("🟡 B-ROLL", "🟡 B-ROLL"), "mk_fx": ("🟣 אפקט", "🟣 FX"),
    "mk_graphic": ("🔵 גרפיקה", "🔵 GRAPHIC"), "mk_highlight": ("🟢 רגע חזק", "🟢 HIGHLIGHT"), "mk_chapter": ("📍 פרק", "📍 CHAPTER"),
    "mk_music": ("🎵 מוזיקה", "🎵 MUSIC"), "mk_note": ("📝", "📝"),
}


def set_lang(lang: str) -> None:
    global _lang
    if lang in ("he", "en"):
        _lang = lang


def lang() -> str:
    return _lang


def guess(text: str) -> str:
    """'he' if the text is mostly Hebrew, else 'en'."""
    heb = len(re.findall(r"[֐-׿]", text))
    lat = len(re.findall(r"[A-Za-z]", text))
    return "he" if heb > lat else "en"


def t(key: str, **kw) -> str:
    he, en = MSG[key]
    return (he if _lang == "he" else en).format(**kw)
