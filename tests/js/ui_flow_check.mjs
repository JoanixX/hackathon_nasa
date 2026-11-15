// End-to-end walk through the map-first workflow in headless Chromium, with screenshots per step.
// Checks real behaviour: basemap provider policy, drawing by clicks, server validation, DEM slope,
// rainfall and acquisition charts, plan, AI scene (actual inference when configured) and the 3D twin.
// Usage: node tests/js/ui_flow_check.mjs [baseUrl]   (PLAYWRIGHT_MODULE may point at a playwright index.mjs)
import { mkdir, writeFile } from "node:fs/promises";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const BASE = process.argv[2] || "http://localhost:8765";
const OUT = ".local/qa/ui";
await mkdir(OUT, { recursive: true });
const results = { base: BASE, started_utc: new Date().toISOString(), checks: [] };
const check = (name, ok, detail) => { results.checks.push({ name, ok: !!ok, detail }); console.log(ok ? "PASS" : "FAIL", name, detail ?? ""); };
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch({ args: ["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--use-gl=angle", "--use-angle=swiftshader"] });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [], hosts = new Set();
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
page.on("request", (r) => { try { hosts.add(new URL(r.url()).host); } catch (_) {} });
const ownFailures = [], externalFailures = [];
page.on("response", (r) => {
  if (r.status() < 500) return;
  const u = new URL(r.url());
  (u.origin === new URL(BASE).origin ? ownFailures : externalFailures).push(`${r.status()} ${u.host}${u.pathname.slice(0, 80)}`);
});
await page.addInitScript(() => { try { localStorage.setItem("raiz-tour", "done"); } catch (_) {} });

await page.goto(BASE);
await page.waitForFunction(() => document.querySelector("#panel-body") && document.querySelector("#panel-body").innerText.length > 50, null, { timeout: 60000 });
await page.waitForFunction(() => window.raiz && document.querySelector("#legend").innerText.includes("NISAR"), null, { timeout: 90000 }).catch(() => {});
await wait(4000);
await page.screenshot({ path: `${OUT}/1-explore.png` });
check("explore_shows_nisar_layer", (await page.locator("#legend").innerText()).includes("NISAR"), "real NISAR GCOV shown on load");
check("no_osm_public_tiles", ![...hosts].some((h) => h === "tile.openstreetmap.org"), [...hosts].filter((h) => /tile|openfreemap|gibs/.test(h)).join(", "));
check("no_leaflet_flag", (await page.locator(".leaflet-attribution-flag").count()) === 0);

// Draw a zone with clicks on a slope east of the locator, then close it on the first vertex.
await page.click("text=Draw zones to assess");
await page.waitForSelector("text=Draw a zone");
await page.evaluate(() => { const m = window.raiz && null; return m; });
await page.evaluate(async () => { const M = await import("/app/map.js"); M.getMap().jumpTo({ center: [-80.62, -5.2], zoom: 13 }); });
await wait(2500);
await page.click("text=Draw a zone");
const pts = [[760, 360], [900, 340], [960, 470], [820, 540], [720, 470]];
for (const [x, y] of pts) { await page.mouse.click(x, y); await wait(250); }
await page.mouse.click(pts[0][0], pts[0][1]);
await wait(1200);
const drawn = await page.evaluate(async () => (await import("/app/state.js")).state.drawn.length);
check("zone_drawn_by_clicks", drawn === 1, `${drawn} zone(s)`);
await page.screenshot({ path: `${OUT}/2-zone-drawn.png` });

// Suggest a boundary (proposal only) and keep the user's polygon.
const beforeGeom = await page.evaluate(async () => JSON.stringify((await import("/app/state.js")).state.drawn[0].geometry));
await page.click("text=Suggest boundary");
await page.waitForSelector("button:has-text('Use the proposal')", { timeout: 180000 }).catch(() => {});
const proposal = await page.locator("button:has-text('Use the proposal')").count();
if (!proposal) console.log("toast:", await page.locator("#toast").innerText().catch(() => ""));
check("suggestion_is_proposal", proposal > 0, "proposal shown beside the zone");
const afterGeom = await page.evaluate(async () => JSON.stringify((await import("/app/state.js")).state.drawn[0].geometry));
check("suggestion_not_applied_silently", beforeGeom === afterGeom);
await page.screenshot({ path: `${OUT}/3-suggestion.png` });
if (proposal) await page.click("button:has-text('Keep my zone')");

await page.click("text=Confirm zones and measure terrain");
await page.waitForSelector("text=Confirmed zones", { timeout: 120000 }).catch(() => {});
const zoneText = await page.locator("#panel-body").innerText();
check("zone_confirmed_with_dem_slope", /Confirmed zones/.test(zoneText) && /%/.test(zoneText), zoneText.split("\n").slice(-6).join(" | "));
await page.screenshot({ path: `${OUT}/4-confirmed.png` });

await page.click("text=See terrain and radar evidence");
await page.waitForSelector("#panel-body canvas", { timeout: 30000 }).catch(() => {});
await wait(4000);
const evText = await page.locator("#panel-body").innerText();
check("evidence_slope_chart", (await page.locator("#panel-body canvas").count()) > 0);
check("evidence_lists_acquisitions", /NISAR GCOV \(L-band\): \d+ acquisition/.test(evText), evText.match(/NISAR GCOV[^\n]*/)?.[0]);
await page.screenshot({ path: `${OUT}/5-evidence.png` });

await page.click("text=Compare before and after the rains");
await page.waitForFunction(() => /Wettest days/.test(document.querySelector("#panel-body").innerText), null, { timeout: 90000 }).catch(() => {});
await wait(1500);
const cmp = await page.locator("#panel-body").innerText();
check("rain_chart_real_data", /Wettest days: \d{4}-\d{2}-\d{2}/.test(cmp), cmp.match(/Wettest days[^\n]*/)?.[0]);
await page.click("text=Show on map").catch(() => {});
await wait(3000);
check("rtc_layer_dated", /Sentinel-1 radar[\s\S]*\d{4}-\d{2}-\d{2}/.test(await page.locator("#legend").innerText()));
await page.screenshot({ path: `${OUT}/6-compare.png` });

await page.click("text=Plan the planting");
await page.waitForSelector("text=Species per zone");
const sel = page.locator("#panel-body select").first();
const opts = await sel.locator("option").allTextContents();
await sel.selectOption({ index: Math.min(1, opts.length - 1) });
await page.click("text=Compute the plan");
await page.waitForFunction(() => /Total S\//.test(document.querySelector("#panel-body").innerText), null, { timeout: 60000 }).catch(() => {});
const planText = await page.locator("#panel-body").innerText();
check("plan_computed", /Total S\//.test(planText), planText.match(/Total[^\n]*/)?.[0]);
await page.screenshot({ path: `${OUT}/7-plan.png` });

await page.click("text=Build the future scenario");
await page.click("text=Generate the future scenario");
await page.waitForFunction(() => /validated before assembly/.test(document.querySelector("#panel-body").innerText) || /errline/.test(document.querySelector("#panel-body").innerHTML), null, { timeout: 300000 }).catch(() => {});
const fut = await page.locator("#panel-body").innerText();
check("future_scene_generated", /validated before assembly/.test(fut), fut.match(/(google-gemini|fixture)[^\n]*/)?.[0]);
const pts3 = await page.evaluate(async () => { const s = (await import("/app/state.js")).state; return s.scene ? { n: s.scene.placements.length, grid: !!s.scene.terrain_grid, terrain: s.scene.frame.terrain } : null; });
check("scene_has_dem_terrain", pts3 && pts3.grid, pts3 && pts3.terrain);
await page.screenshot({ path: `${OUT}/8a-future.png` });
await page.locator("#panel-body button", { hasText: "3D terrain view" }).click({ timeout: 15000 }).catch((e) => console.log("3D click:", String(e).slice(0, 200)));
await wait(8000);
// Software WebGL (SwiftShader) can be very slow with 3D terrain; record that instead of crashing.
const shot3d = await page.screenshot({ path: `${OUT}/8-future-3d.png`, timeout: 120000 }).then(() => true).catch(() => false);
check("terrain_3d_rendered_headless", shot3d, shot3d ? "pitched DEM terrain captured" : "frame not produced within 120 s on software WebGL");
const terrainOn = await page.evaluate(async () => !!(await import("/app/map.js")).getMap().getTerrain());
check("terrain_3d_enabled", terrainOn);
await page.locator("button#btn-3d").click().catch(() => {});
await wait(1500);

await page.click("text=Write the planning draft");
await page.click("text=Generate the draft");
await page.waitForSelector("text=Not an approved technical dossier", { timeout: 300000 }).catch(() => {});
check("report_generated", (await page.locator("text=Not an approved technical dossier").count()) > 0);
await page.screenshot({ path: `${OUT}/9-report.png` });

// Phone layout.
await page.setViewportSize({ width: 390, height: 844 });
await wait(1500);
await page.screenshot({ path: `${OUT}/10-phone.png` });
const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
check("phone_no_horizontal_overflow", !overflow);

const jsErrors = errors.filter((e) => !/Failed to load resource/.test(e));
check("no_javascript_errors", jsErrors.length === 0, jsErrors.slice(0, 4).join(" | "));
check("no_api_5xx", ownFailures.length === 0, ownFailures.slice(0, 4).join(" | "));
results.external_5xx = externalFailures.slice(0, 50);
console.log(`external provider 5xx responses: ${externalFailures.length}`, externalFailures.slice(0, 3).join(" | "));
results.hosts = [...hosts].sort();
results.finished_utc = new Date().toISOString();
results.passed = results.checks.every((c) => c.ok);
await writeFile(`${OUT}/ui-check.json`, JSON.stringify(results, null, 2));
await browser.close();
process.exit(results.passed ? 0 : 1);
