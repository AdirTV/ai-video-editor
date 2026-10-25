// Rasterize Natural Earth land (50m) into a coarse grid for the pixel FlightMap -> src/maps/landgrid.json.
// Run from anywhere:  node scripts/landgrid.mjs   (needs the devDependencies topojson-client + world-atlas)
import fs from "node:fs";
import { feature } from "topojson-client";
const ROOT = new URL("..", import.meta.url);
const topo = JSON.parse(fs.readFileSync(new URL("node_modules/world-atlas/land-50m.json", ROOT), "utf8"));
const land = feature(topo, topo.objects.land);
const polys = land.features.flatMap(f => f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates);
const inRing = (x, y, ring) => { let ins = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) ins = !ins; }
  return ins; };
const isLand = (x, y) => polys.some(p => inRing(x, y, p[0]) && !p.slice(1).some(h => inRing(x, y, h)));
const [LON0, LON1, LAT0, LAT1, STEP] = [22, 150, 60, 4, 2];
const cols = (LON1 - LON0) / STEP, rows = (LAT0 - LAT1) / STEP;
const grid = [];
for (let r = 0; r < rows; r++) { let row = "";
  for (let c = 0; c < cols; c++) { let n = 0;
    for (let a = 0; a < 4; a++) for (let b = 0; b < 4; b++)
      n += isLand(LON0 + (c + (a + 0.5) / 4) * STEP, LAT0 - (r + (b + 0.5) / 4) * STEP) ? 1 : 0;
    row += n >= 5 ? "#" : "."; }
  grid.push(row); }
fs.writeFileSync(new URL("src/maps/landgrid.json", ROOT), JSON.stringify({ LON0, LAT0, STEP, grid }));
console.log(grid.join("\n"));
