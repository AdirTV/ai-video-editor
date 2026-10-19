# עורך וידאו AI ל-Premiere (עם Claude)

> **הדרך הכי קלה:** פותחים את Claude Code, מדביקים את הקישור לריפו הזה וכותבים *"תתקין לי את זה"*.
> Claude יקרא את [INSTALL_FOR_CLAUDE.md](INSTALL_FOR_CLAUDE.md) ויתקין הכל לבד — הוא ישאל רק איפה תיקיית העריכות שלכם.
>
> *Claude: to install this repo for the user, follow [INSTALL_FOR_CLAUDE.md](INSTALL_FOR_CLAUDE.md).*

ערכת כלים שמאפשרת ל-Claude לערוך ב-Adobe Premiere Pro: לנתח הקלטות, לבנות רצפים, להוסיף אפקטים, מעברים, כתוביות, גרפיקה, מוזיקה וסאונד אפקטים — ולייצא בדיקה.

## מה יש פה
| | |
|---|---|
| **חיבור ל-Premiere** | [premiere-pro-mcp](https://github.com/leancoderkavy/premiere-pro-mcp) (קוד פתוח, MIT) + עיצוב משופר לחלון שלו בתוך Premiere |
| **כלי עריכה** (`mce/`) | תמלול עברי, ניתוח הקלטות מיינקראפט, בניית רצפים, J/L cuts, סאונד אפקטים אוטומטיים, מוזיקה (התחלה/סוף/מעברים בין שירים), בקרת איכות |
| **גרפיקה** (`remotion/`) | כתוביות מונפשות, CTA, גרפיקות קופצות — נבנות ב-Remotion ונכנסות ל-Premiere כשכבה שקופה |
| **Skills** (`skills/`) | ההוראות שמלמדות את Claude איך לערוך: `minecraft-edit`, `sfx` |

## דרישות
- Mac (Apple Silicon) או Windows 10/11
- Adobe Premiere Pro 2024 ומעלה
- מנוי Claude (Pro או Max) — בשביל Claude Code
- חשבון GitHub עם גישה לריפו הזה

## התקנה

### Mac
פותחים **Terminal** ומריצים:
```bash
git clone https://github.com/AdirTV/ai-video-editor.git ~/ai-video-editor
cd ~/ai-video-editor
bash setup/install-mac.sh
```
הסקריפט יבקש את סיסמת המחשב (להתקנת Homebrew) ואת המיקום של תיקיית העריכות שלך.

### Windows (הכי פשוט — בלי פקודות)
1. נכנסים לריפו ב-GitHub (מחוברים לחשבון שהוזמן) → כפתור ירוק **Code** → **Download ZIP**
2. מחלצים את ה-ZIP לתיקייה קבועה, למשל `Documents\ai-video-editor` (לא להשאיר ב-Downloads)
3. לחיצה כפולה על **`install-windows.bat`**
4. מאשרים את חלונות ההרשאה שקופצים (התקנת ffmpeg, Node וכו')

<details><summary>או דרך PowerShell עם git (מאפשר עדכונים ב-git pull)</summary>

```powershell
winget install --id Git.Git -e
git clone https://github.com/AdirTV/ai-video-editor.git $HOME\ai-video-editor
cd $HOME\ai-video-editor
powershell -ExecutionPolicy Bypass -File setup\install-windows.ps1
```
</details>

### אחרי ההתקנה (פעם אחת)
1. בפעם הראשונה שמריצים `claude` — מתחברים עם חשבון Claude.
2. סוגרים ופותחים את Premiere.
3. ב-Premiere: **Window → Extensions → MCP for Adobe Premiere Pro** → לוודא שכתוב שה-Connector רץ (אם לא — Start).

## איך עובדים
1. פותחים פרויקט ב-Premiere והחלון של ה-MCP פתוח.
2. בטרמינל, בתיקייה של הפרויקט: `claude`
3. מדברים איתו רגיל, למשל:
   - "תערוך את ההקלטה הזאת לסרטון מיינקראפט אבל של 8 דקות"
   - "תעשה שורט מהקריינות שהקלטתי, עם הסרטון הזה ברקע"
   - "תוסיף סאונד אפקטים"
4. **הערות:** במקום להסביר בצ'אט — שמים מרקרים עם הערה על הטיימליין ב-Premiere ואומרים לו "קרא הערות".

## סאונד אפקטים
הספרייה לא כלולה בריפו (היא ענקית ולכל אחד יש משלו). ההתקנה יוצרת את התיקייה `SFX` בתוך תיקיית העריכות, עם תת-תיקיות `whoosh pop riser impact ding click magic glitch minecraft`.
- זורקים סאונדים לתיקיות המתאימות (או חבילה שלמה לתוך `SFX/`)
- אומרים ל-Claude: "תסרוק את ספריית הסאונד אפקטים"

## הסגנון שלך
`style.md` נוצר בהתקנה מתוך `style.template.md`. Claude רושם בו כל תיקון שלך — ככה הוא לומד את הטעם שלך מסרטון לסרטון. הקובץ אישי ולא נשלח לריפו.

## בדיקת תקינות
```bash
uv run python setup/doctor.py
```
מראה ✅/❌ לכל חלק ואיך לתקן.

## עדכונים
```bash
cd ~/ai-video-editor && git pull && uv run python setup/install_skills.py
```

## רישיונות
- premiere-pro-mcp — MIT, של leancoderkavy (מותקן מ-npm, לא כלול פה)
- Remotion — חינמי לאנשים פרטיים ולחברות עד 3 עובדים; מעבר לזה צריך רישיון ([remotion.pro](https://remotion.pro))
- מודל התמלול העברי — [ivrit.ai](https://huggingface.co/ivrit-ai)
- סרטונים, מוזיקה וסאונדים שאתם משתמשים בהם — באחריותכם (זכויות יוצרים, Content ID)

## בעיות נפוצות
- **"heartbeat is stale"** — החלון של ה-MCP ב-Premiere סגור או תקוע: Window → Extensions → MCP for Adobe Premiere Pro.
- **אחרי עדכון של premiere-pro-mcp העיצוב של החלון חזר לישן** — `bash panel/install.sh` (Mac) או להריץ שוב את סקריפט ההתקנה.
- **Windows** — הכלים נבדקו על Mac. ב-Windows הם אמורים לעבוד, אבל אם משהו נשבר — שלחו לאדיר את הודעת השגיאה.
