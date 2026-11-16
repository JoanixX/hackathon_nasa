// Video export acceptance check: record the 3D map for a few seconds, then decode the WebM in the browser
// (<video>), seek, and confirm it has the expected size, a duration and non-uniform pixels.
// Usage: node tests/js/video_export_check.mjs [baseUrl]   (PLAYWRIGHT_MODULE may point at a playwright index.mjs)
import { mkdir, writeFile } from "node:fs/promises";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const BASE = process.argv[2] || "http://localhost:8765";
const OUT = ".local/qa/video";
await mkdir(OUT, { recursive: true });
const results = { base: BASE, started_utc: new Date().toISOString(), runs: [] };
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--autoplay-policy=no-user-gesture-required"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
await page.addInitScript(() => { try { localStorage.setItem("raiz-tour", "done"); } catch (_) {} });
await page.goto(BASE);
await page.waitForFunction(() => window.raiz && window.raiz.perf && window.raiz.perf.some((m) => m.name === "map.first_idle"), null, { timeout: 120000 });

for (let i = 0; i < 3; i++) {
  const run = await page.evaluate(async () => {
    const M = await import("/app/map.js");
    const T = await import("/app/twin.js");
    const map = M.getMap();
    map.jumpTo({ center: [-80.632, -5.195], zoom: 14, pitch: 55, bearing: -20 });
    await new Promise((r) => (map.loaded() ? r() : map.once("idle", r)));
    const url = await T.recordVideo(async () => {
      map.easeTo({ bearing: 25, duration: 3000 });
      await new Promise((r) => setTimeout(r, 3200));
    }, 30, "QA export");
    const stats = { ...T.recordingStats };
    const blob = await fetch(url).then((r) => r.blob());
    const v = document.createElement("video");
    v.muted = true; v.src = url;
    await new Promise((res, rej) => { v.onloadeddata = res; v.onerror = () => rej(new Error("decode error " + (v.error && v.error.code))); });
    v.currentTime = Number.isFinite(v.duration) ? v.duration / 2 : 1.5;
    await new Promise((r) => { v.onseeked = r; setTimeout(r, 3000); });
    const c = document.createElement("canvas"); c.width = v.videoWidth; c.height = v.videoHeight;
    const g = c.getContext("2d"); g.drawImage(v, 0, 0);
    const d = g.getImageData(0, 0, c.width, c.height - 40).data;
    let lo = 255, hi = 0;
    for (let k = 0; k < d.length; k += 4 * 97) { lo = Math.min(lo, d[k + 1]); hi = Math.max(hi, d[k + 1]); }
    const bytes = new Uint8Array(await blob.arrayBuffer());
    URL.revokeObjectURL(url);
    return { stats, size: blob.size, width: v.videoWidth, height: v.videoHeight, duration: v.duration, pixel_range: hi - lo,
      b64: btoa(String.fromCharCode(...bytes.subarray(0, Math.min(bytes.length, 4)))) };
  }).catch((e) => ({ error: String(e) }));
  results.runs.push(run);
  console.log(JSON.stringify({ ...run, b64: undefined }));
}
const ok = (r) => !r.error && r.size > 1000 && r.width > 0 && r.height > 0 && (r.duration > 1 || r.duration === Infinity) && r.pixel_range > 10;
results.passed = results.runs.length === 3 && results.runs.every(ok) && errors.length === 0;
results.page_errors = errors;
results.finished_utc = new Date().toISOString();
await writeFile(`${OUT}/video-check.json`, JSON.stringify(results, null, 2));
console.log(results.passed ? "PASS video_export (3/3 decoded with picture)" : "FAIL video_export");
await browser.close();
process.exit(results.passed ? 0 : 1);
