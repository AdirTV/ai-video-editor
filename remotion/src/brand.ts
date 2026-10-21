import defaults from "../../brand.example.json";

// The creator's look: channel name, colours, caption style, logo. Lives in brand.json at the repo root
// (personal, gitignored; brand.example.json is the shared start). Components fall back to it when a
// prop isn't passed. `logo` is a file under remotion/public/, e.g. "brand/logo.png".
type Brand = typeof defaults;
const ctx = require.context("../..", false, /^\.\/brand\.json$/);
// the gallery renders with the neutral defaults, whoever runs it
const gallery = typeof process !== "undefined" && process.env?.REMOTION_GALLERY;
const local: Partial<Brand> = ctx.keys().length && !gallery ? (ctx(ctx.keys()[0]).default ?? ctx(ctx.keys()[0])) : {};
export const brand: Brand = { ...defaults, ...local };
