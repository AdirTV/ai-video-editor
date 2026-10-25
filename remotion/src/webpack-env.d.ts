// webpack's require.context, used to pick up optional local files (projects, brand.json).
type WebpackContext = { keys(): string[]; (key: string): Record<string, unknown> };
declare const require: { context(dir: string, deep: boolean, match: RegExp): WebpackContext };
