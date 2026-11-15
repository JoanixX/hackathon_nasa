// Visual check of the 3D twin over real relief (Copernicus DEM) at true and exaggerated scale.
// Usage: node tests/js/relief_check.mjs [baseUrl]
import { mkdir } from "node:fs/promises";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const BASE = process.argv[2] || "http://localhost:8765";
await mkdir(".local/qa/ui", { recursive: true });
const browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--use-gl=angle", "--use-angle=swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
await page.addInitScript(() => { try { localStorage.setItem("raiz-tour", "done"); } catch (_) {} });
await page.goto(BASE);
await page.waitForFunction(() => window.raiz && window.raiz.state.imagery.nisar, null, { timeout: 120000 }).catch(() => {});
await page.screenshot({ path: ".local/qa/ui/r0-explore.png", timeout: 120000 });
// Andean foothills east of Piura (Canchaque area): real relief within the study region.
await page.evaluate(async () => { const M = await import("/app/map.js"); M.getMap().jumpTo({ center: [-79.62, -5.38], zoom: 11.6, bearing: -25 }); });
await page.click("#btn-3d");
await new Promise((r) => setTimeout(r, 15000));
await page.screenshot({ path: ".local/qa/ui/r1-relief-x1.png", timeout: 180000 });
await page.click("#relief [data-ex='3']");
await new Promise((r) => setTimeout(r, 8000));
await page.screenshot({ path: ".local/qa/ui/r2-relief-x3.png", timeout: 180000 });
// Piura city in 3D: OSM building footprints extruded over the DEM terrain.
await page.click("#relief [data-ex='1']");
await page.evaluate(async () => { const M = await import("/app/map.js"); M.getMap().jumpTo({ center: [-80.6305, -5.1962], zoom: 16, pitch: 60, bearing: 30 }); });
await new Promise((r) => setTimeout(r, 15000));
await page.screenshot({ path: ".local/qa/ui/r3-city-3d.png", timeout: 180000 });
console.log("legend:", (await page.locator("#legend").innerText()).replace(/\n/g, " | "));
await browser.close();
