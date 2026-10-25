// Caches Noto animated emoji (Google, CC BY 4.0) under public/lottie/noto/<codepoints>.json, so LottieFx renders
// offline and the result can't change under you. LottieFx uses the cache when the file is there, else the pinned URL.
//   npm run emoji                 the emoji used in src/ (emoji="…" / "emoji": "…") plus a few common ones
//   npm run emoji -- 😂 🔥 🙏     just these
import fs from "node:fs";
import path from "node:path";

const VERSION = "17.0"; // keep in sync with NOTO_VERSION in src/fx/LottieFx.tsx
const ROOT = path.resolve(import.meta.dirname, "..");
const OUT = path.join(ROOT, "public", "lottie", "noto");
const code = (e) => [...e].map((c) => c.codePointAt(0).toString(16)).filter((h) => h !== "fe0f").join("_");

const scan = (dir, found) => {
  for (const f of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, f.name);
    if (f.isDirectory()) scan(p, found);
    else if (/\.(tsx?|json)$/.test(f.name))
      for (const m of fs.readFileSync(p, "utf8").matchAll(/["']?emoji["']?\s*[=:]\s*["']([^"']+)["']/g)) found.add(m[1]);
  }
  return found;
};

const wanted = process.argv.length > 2
  ? new Set(process.argv.slice(2))
  : scan(path.join(ROOT, "src"), new Set(["😂", "🔥", "😱", "🙏", "😭", "🤯", "👀", "💀", "❤️", "🎉"]));

fs.mkdirSync(OUT, { recursive: true });
for (const e of wanted) {
  const file = path.join(OUT, `${code(e)}.json`);
  if (fs.existsSync(file)) { console.log("have", e); continue; }
  const res = await fetch(`https://fonts.gstatic.com/s/e/notoemoji/${VERSION}/${code(e)}/lottie.json`);
  if (!res.ok) { console.warn(`no animated Noto emoji for ${e} (${res.status})`); continue; }
  fs.writeFileSync(file, await res.text());
  console.log("got ", e, "->", path.relative(ROOT, file));
}
