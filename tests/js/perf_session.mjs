// Local performance regression session; no AI requests. One cold browser context per startup sample.
import { mkdir, writeFile } from "node:fs/promises";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const BASE = process.argv[2] || "http://localhost:8765";
const OUT = ".local/qa/performance";
await mkdir(OUT, { recursive: true });
const browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--use-gl=angle", "--use-angle=swiftshader"] });
const result = { started_utc: new Date().toISOString(), base: BASE, startups: [], checks: [], visits: [] };
const check = (name, ok, detail) => { result.checks.push({ name, ok: !!ok, detail }); console.log(ok ? "PASS" : "FAIL", name, detail || ""); };
const idle = async page => page.evaluate(() => import("/app/map.js").then(M => new Promise(resolve => {
  const map = M.getMap(); const done = () => { clearTimeout(timer); map.off("idle", done); resolve(true); };
  const timer = setTimeout(() => { map.off("idle", done); resolve(false); }, 20000);
  if (map.loaded()) done(); else map.once("idle", done);
})));
let page, ctx;
try {
  for (let i = 0; i < 3; i++) {
    ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } }); page = await ctx.newPage();
    const requests = [], errors = [];
    page.on("request", req => requests.push(req.url())); page.on("pageerror", error => errors.push(String(error)));
    await page.addInitScript(() => localStorage.setItem("raiz-tour", "done"));
    await page.goto(BASE + "/?perf", { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForFunction(() => window.raiz?.perf.some(mark => mark.name === "map.first_idle"), null, { timeout: 45000 });
    await page.waitForTimeout(300);
    const marks = await page.evaluate(() => window.raiz.perf);
    const heavy = requests.filter(url => /\/api\/(terrain|tiles|sources)\//.test(url));
    check("startup_" + i + "_no_heavy_data", heavy.length === 0, heavy);
    check("startup_" + i + "_no_js_errors", errors.length === 0, errors);
    result.startups.push({ first_idle_ms: marks.find(m => m.name === "map.first_idle").ms, requests: requests.length, marks });
    if (i < 2) await ctx.close();
  }
  await page.screenshot({ path: OUT + "/default-map.png" });
  const areas = await page.evaluate(() => window.raiz.state.scenario.summary.focus_areas);
  for (const area of areas) {
    const start = Date.now(); await page.getByRole("button", { name: area.name, exact: true }).click();
    const ready = await idle(page);
    result.visits.push({ name: area.name, ms: Date.now() - start, idle: ready });
    check("visit_" + area.name, ready && await page.evaluate(name => window.raiz.state.focusArea.name === name, area.name));
  }
  await page.getByRole("button", { name: "Terrain shading", exact: true }).click();
  check("shade_enabled", await page.evaluate(() => import("/app/map.js").then(M => M.getMap().getLayoutProperty("hillshade", "visibility") === "visible")));
  await page.getByRole("button", { name: "Terrain shading", exact: true }).click();
  check("shade_disabled", await page.evaluate(() => import("/app/map.js").then(M => M.getMap().getLayoutProperty("hillshade", "visibility") === "none")));
  await page.getByRole("button", { name: "Highlight waterways", exact: true }).click();
  check("waterways_enabled", await page.evaluate(() => import("/app/map.js").then(M => M.getMap().getLayoutProperty("quebradas", "visibility") === "visible")));
  await page.getByRole("button", { name: "Highlight waterways", exact: true }).click();
  await page.locator("#steps button", { hasText: "Zones" }).click();
  await page.evaluate(() => window.raiz.ensureDraw());
  for (let n = 4; n <= 8; n++) {
    await page.selectOption("#vertex-count", String(n)); await page.getByRole("button", { name: "Place the vertices", exact: true }).click();
    await page.evaluate(async n => { const D = await import("/app/draw.js"); D.placeVertices(Array.from({length:n}, (_,i) => [-80.632 + .004*Math.cos(i*2*Math.PI/n), -5.195 + .004*Math.sin(i*2*Math.PI/n)])); }, n);
    check("draw_" + n + "_vertices", await page.evaluate(n => window.raiz.state.drawn.at(-1)?.geometry.coordinates[0].length === n+1, n));
    await page.getByRole("button", {name:"Delete all",exact:true}).click();
  }
  await page.click("#btn-3d"); await idle(page);
  check("3d_terrain_and_coloured_buildings", await page.evaluate(() => import("/app/map.js").then(M => {
    const map=M.getMap(); return !!map.getTerrain() && !!map.getLayer("buildings-3d") && JSON.stringify(map.getPaintProperty("buildings-3d", "fill-extrusion-color")) === JSON.stringify(M.BUILDING_COLOR);
  })));
  await page.screenshot({path:OUT+"/piura-3d.png",timeout:45000});
  await page.click("#btn-3d");
  await page.setViewportSize({width:390,height:844});
  check("mobile_no_horizontal_overflow", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
} finally {
  result.finished_utc = new Date().toISOString();
  await writeFile(OUT + "/session.json", JSON.stringify(result,null,2));
  await browser.close();
}
console.log(JSON.stringify({first_idle_ms:result.startups.map(s=>s.first_idle_ms),visits:result.visits}));
if (result.checks.some(c=>!c.ok)) process.exitCode=1;
