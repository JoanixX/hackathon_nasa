// Builds the printable AR image target (assets/ar/target.png) and compiles its MindAR
// feature file (assets/ar/target.mind) with the pinned MindAR 1.2.5 compiler in Chromium.
// Usage: node tools/build_ar_target.mjs
import { chromium } from "@playwright/test";
import { writeFile, mkdir } from "node:fs/promises";

const MINDAR = "https://cdn.jsdelivr.net/npm/mind-ar@1.2.5/dist/mindar-image.prod.js";
const WIDTH = 1200;
const HEIGHT = 848; // A-series landscape aspect (height/width ≈ 0.707)

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent("<!doctype html><html><body></body></html>");
await page.addScriptTag({ url: MINDAR, type: "module" }).catch(() => page.addScriptTag({ url: MINDAR }));

const result = await page.evaluate(async ({ WIDTH, HEIGHT }) => {
  // Deterministic PRNG so the target is reproducible.
  let s = 20261114;
  const rnd = () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
  const c = document.createElement("canvas");
  c.width = WIDTH; c.height = HEIGHT;
  const g = c.getContext("2d");
  g.fillStyle = "#f4efe3"; g.fillRect(0, 0, WIDTH, HEIGHT);
  // Topographic-style contour lines (high-frequency, non-repeating features for tracking).
  for (let k = 0; k < 46; k++) {
    g.beginPath();
    const cx = rnd() * WIDTH, cy = rnd() * HEIGHT, r0 = 20 + rnd() * 160;
    for (let a = 0; a <= Math.PI * 2 + 0.01; a += 0.08) {
      const r = r0 * (1 + 0.35 * Math.sin(a * (2 + (k % 5))) + 0.12 * Math.cos(a * 7 + k));
      const x = cx + r * Math.cos(a), y = cy + r * Math.sin(a) * 0.8;
      a === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    g.strokeStyle = ["#1f4e5a", "#6b4f2a", "#2f6b3a", "#8a2d1f"][k % 4];
    g.lineWidth = 1 + rnd() * 3;
    g.stroke();
  }
  // Filled irregular polygons in several tones.
  for (let k = 0; k < 70; k++) {
    g.beginPath();
    const cx = rnd() * WIDTH, cy = rnd() * HEIGHT, n = 3 + Math.floor(rnd() * 5);
    for (let i = 0; i < n; i++) {
      const a = (i / n) * Math.PI * 2 + rnd(), r = 8 + rnd() * 34;
      const x = cx + r * Math.cos(a), y = cy + r * Math.sin(a);
      i === 0 ? g.moveTo(x, y) : g.lineTo(x, y);
    }
    g.closePath();
    g.fillStyle = `hsl(${Math.floor(rnd() * 360)}, ${40 + rnd() * 40}%, ${20 + rnd() * 45}%)`;
    g.fill();
  }
  // Coordinate grid ticks and labels.
  g.strokeStyle = "#20242a"; g.lineWidth = 1;
  for (let x = 0; x <= WIDTH; x += 100) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, 14); g.moveTo(x, HEIGHT); g.lineTo(x, HEIGHT - 14); g.stroke(); }
  for (let y = 0; y <= HEIGHT; y += 100) { g.beginPath(); g.moveTo(0, y); g.lineTo(14, y); g.moveTo(WIDTH, y); g.lineTo(WIDTH - 14, y); g.stroke(); }
  g.fillStyle = "#11161c";
  g.font = "bold 44px sans-serif";
  g.fillText("RAÍZ-SAR AI", 40, 70);
  g.font = "22px sans-serif";
  g.fillText("Tabletop AR target v1 — print at 100% scale", 40, 104);
  g.fillText("Not a map: registration image only", 40, HEIGHT - 36);
  // Asymmetric corner blocks help orientation.
  g.fillRect(WIDTH - 120, 30, 80, 80);
  g.fillStyle = "#f4efe3"; g.fillRect(WIDTH - 100, 50, 26, 26);
  g.fillStyle = "#11161c"; g.fillRect(WIDTH - 90, HEIGHT - 110, 50, 70);
  g.lineWidth = 6; g.strokeRect(3, 3, WIDTH - 6, HEIGHT - 6);

  const png = c.toDataURL("image/png");
  const img = new Image();
  img.src = png;
  await img.decode();
  for (let i = 0; i < 100 && !(window.MINDAR && window.MINDAR.IMAGE); i++) await new Promise((r) => setTimeout(r, 100));
  if (!(window.MINDAR && window.MINDAR.IMAGE && window.MINDAR.IMAGE.Compiler)) return { error: "MindAR compiler not loaded" };
  const compiler = new window.MINDAR.IMAGE.Compiler();
  await compiler.compileImageTargets([img], () => {});
  const data = await compiler.exportData();
  let bin = "";
  const bytes = new Uint8Array(data);
  for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return { png, mind: btoa(bin) };
}, { WIDTH, HEIGHT });

await browser.close();
if (result.error) {
  console.error(result.error);
  process.exit(1);
}
await mkdir("assets/ar", { recursive: true });
await writeFile("assets/ar/target.png", Buffer.from(result.png.split(",")[1], "base64"));
await writeFile("assets/ar/target.mind", Buffer.from(result.mind, "base64"));
console.log("wrote assets/ar/target.png and assets/ar/target.mind",
  Buffer.from(result.mind, "base64").length, "bytes of features");
