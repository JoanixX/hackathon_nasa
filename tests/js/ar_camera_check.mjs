// Camera-pipeline AR verification with Chromium's fake camera fed by a video of the printed target.
// This exercises getUserMedia -> MindAR image tracking -> targetFound/targetLost -> A-Frame scene.
// It is real registration on recorded frames, NOT a physical-device session (that gate stays separate).
//
// Usage: node tests/js/ar_camera_check.mjs [baseUrl] [y4mPath]
//   PLAYWRIGHT_MODULE may point at a playwright index.mjs when the package is not installed locally.
import { writeFile, mkdir } from "node:fs/promises";
import path from "node:path";

const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
const BASE = process.argv[2] || "http://localhost:8765";
const Y4M = path.resolve(process.argv[3] || ".local/qa/fake-camera.y4m");
const results = { base: BASE, started_utc: new Date().toISOString(), checks: [] };
const check = (name, ok, detail) => { results.checks.push({ name, ok, detail }); console.log(ok ? "PASS" : "FAIL", name, detail ?? ""); };

async function preparePlanAndScene(page) {
  await page.goto(BASE);
  await page.waitForFunction(() => window.__raiz && window.__raiz.state.dataset, null, { timeout: 30000 });
  await page.click("#t-plan");
  await page.click("#btn-plan");
  await page.waitForFunction(() => window.__raiz.state.planVersion, null, { timeout: 30000 });
  await page.click("#t-scene");
  await page.click("#btn-scene");
  await page.waitForFunction(() => window.__raiz.state.scene, null, { timeout: 120000 });
  return page.evaluate(() => ({ plan: window.__raiz.state.planVersion, scene: window.__raiz.state.scene.scene_version,
    mode: window.__raiz.state.scene.inference.mode }));
}

await mkdir(".local/qa", { recursive: true });

// 1) Camera granted: tracking found, lost and found again.
{
  const browser = await chromium.launch({ args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream",
    `--use-file-for-fake-video-capture=${Y4M}`, "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await context.grantPermissions(["camera"], { origin: BASE });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const info = await preparePlanAndScene(page);
  results.scene = info;
  const t0 = Date.now();
  await page.click("#btn-ar");
  try {
    await page.waitForFunction(() => document.body.dataset.arState === "active", null, { timeout: 90000 });
    check("target_found_via_camera", true, `${Date.now() - t0} ms after Start camera AR`);
    await page.screenshot({ path: ".local/qa/ar-active.png" });
  } catch (e) {
    check("target_found_via_camera", false, await page.evaluate(() => document.getElementById("ar-state").innerText));
  }
  try {
    await page.waitForFunction(() => document.body.dataset.arState === "tracking_lost", null, { timeout: 30000 });
    const hidden = await page.evaluate(() => !document.querySelector("#raiz-root").object3D.visible);
    check("tracking_lost_hides_overlay", hidden, "empty-table frames");
    await page.waitForFunction(() => document.body.dataset.arState === "active", null, { timeout: 30000 });
    check("target_reacquired", true);
  } catch (e) {
    check("tracking_loss_cycle", false, String(e).slice(0, 200));
  }
  await page.click('[data-ar-h="3"]');
  const visible = await page.evaluate(() => Number(document.body.dataset.arVisible));
  check("horizon_12_months_shows_vegetation", visible > 0, `${visible} markers`);
  await page.click('[data-ar-h="0"]');
  const atZero = await page.evaluate(() => Number(document.body.dataset.arVisible));
  check("deposition_stage_shows_no_plants", atZero === 0, `${atZero} markers`);
  await page.evaluate(() => document.querySelector(".raiz-zone").emit("click"));
  check("zone_inspection", (await page.evaluate(() => document.getElementById("ar-zone-info").innerText)).includes("expected established"));
  // Changing a plan input invalidates the plan; the AR session must end instead of showing a stale scene.
  await page.click("#btn-ar-exit");
  await page.waitForFunction(() => document.body.dataset.arState === "idle", null, { timeout: 10000 });
  check("exit_releases_camera", await page.evaluate(() => !document.querySelector("#ar-container a-scene") && document.querySelectorAll("video").length === 0));
  check("no_page_errors", errors.length === 0, errors.slice(0, 3).join(" | "));
  await browser.close();
}

// 2) Camera denied: explicit permission-denied state, no fake UI auto-accept.
{
  // "=deny" makes Chromium's fake permission UI reject the request with a real NotAllowedError.
  const browser = await chromium.launch({ args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream=deny", "--enable-unsafe-swiftshader"] });
  const context = await browser.newContext();
  const page = await context.newPage();
  page.on("dialog", (d) => d.dismiss());
  await preparePlanAndScene(page);
  await page.click("#btn-ar");
  try {
    await page.waitForFunction(() => ["permission_denied", "failed"].includes(document.body.dataset.arState), null, { timeout: 30000 });
    const st = await page.evaluate(() => document.body.dataset.arState);
    check("camera_denied_is_reported", st === "permission_denied", st);
  } catch (e) {
    check("camera_denied_is_reported", false, await page.evaluate(() => document.getElementById("ar-state").innerText));
  }
  await browser.close();
}

results.finished_utc = new Date().toISOString();
results.passed = results.checks.every((c) => c.ok);
await writeFile(".local/qa/ar-check.json", JSON.stringify(results, null, 2));
process.exit(results.passed ? 0 : 1);
