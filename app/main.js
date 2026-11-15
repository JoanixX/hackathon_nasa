// Boot, step navigation, legend/provenance, guided tour and map synchronisation.
import { api } from "./api.js";
import * as M from "./map.js";
import * as D from "./draw.js";
import * as P from "./panels.js";
import { wireHud, endForStalePlan } from "./ar.js";
import { $, el, badge, toast, announce } from "./dom.js";
import { state, update, subscribe, invalidate } from "./state.js";

const C = window.RaizCore;
const RENDER = { explore: P.explore, zones: P.zones, evidence: P.evidence, compare: P.compare, plan: P.plan, future: P.future, report: P.report };

const raiz = {
  species: {},
  pendingMeta: null,
  planInputs: { budget: 25000, density: 400, spc: 3, germ: 0.3, est: 0.4, capcost: 0.6, deliv: 180, maint: 120, monit: 1500, halflife: null },
  go, selectScenario, drawZones, drawFuture, toggle3d,
  state, // read-only handle for diagnostics and browser tests
};
window.raiz = raiz;

// ------------------------------------------------------------------ navigation
function go(step) {
  const avail = C.stepAvailability(state);
  if (!avail[step].open) { toast(avail[step].reason); return; }
  if (state.step === "zones" && step !== "zones") D.setMode("select");
  // The before/after radar belongs to the comparison; leaving it restores an uncluttered map.
  if (state.step === "compare" && step !== "compare" && state.imagery.rtc) { state.imagery.rtc = null; M.setImagery("rtc", null); }
  update({ step });
  renderPanel();
  if (step === "future") drawFuture();
  announce(`${P.TITLES[step]} step.`);
  $("panel-title").focus({ preventScroll: true });
}

function renderSteps() {
  const avail = C.stepAvailability(state);
  const ol = $("steps");
  ol.replaceChildren(...C.STEPS.map((s, i) => {
    const b = el("button", { type: "button", "aria-current": state.step === s ? "step" : null, "aria-disabled": avail[s].open ? null : "true",
      title: avail[s].open ? P.TITLES[s] : avail[s].reason, onclick: () => go(s) },
      el("span", { class: "n" }, String(i + 1)), el("span", { class: "label" }, P.LABELS[s]));
    return el("li", {}, b);
  }));
}

function renderPanel() {
  $("panel-title").textContent = P.TITLES[state.step];
  $("panel-title").tabIndex = -1;
  let content;
  try { content = RENDER[state.step](); }
  catch (e) { content = [el("p", { class: "errline" }, `This step could not be shown: ${e.message}`)]; console.error(e); }
  $("panel-body").replaceChildren(...content);
  renderSteps();
  renderLegend();
}
P.setRerender(() => { renderPanel(); });

// ------------------------------------------------------------------ legend and provenance
function renderLegend() {
  const items = [];
  for (const [key, date] of Object.entries(state.imagery)) {
    if (!date) continue;
    const info = M.LAYER_INFO[key];
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: `background:${key === "imerg" ? "#4bb3ae" : key === "hls" ? "#9b8f6e" : "#6db3df"}` }),
      el("div", {}, el("strong", {}, info.title), " ", badge(info.cls), el("div", { class: "src" }, `${date} UTC · ${info.src}`))));
  }
  if (state.dataset || state.drawn.length) {
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#e2a33b" }), el("div", {}, "Candidate zone",
      state.datasetKind === "demo" ? badge("fixture") : null)));
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#e2654f" }), el("div", {}, "No-go zone")));
  }
  if (state.suggestion) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#1b6fa8" }), el("div", {}, "Boundary proposal (not applied)")));
  if (state.plan && state.plan.drone.nodes.length) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#f4d35e;border-radius:50%" }), el("div", {}, "Proposed seed deposition point (not executed)")));
  if (state.scene && state.step === "future") items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#4f8a3a;border-radius:50%" }),
    el("div", {}, "Future vegetation ", badge(state.scene.inference.mode === "actual_inference" ? "ai_generated" : "fixture"), el("div", { class: "src" }, state.scene.labels.marker))));
  items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:linear-gradient(135deg,#fff,#3b3326)" }),
    el("div", {}, state.terrain3d ? "3D terrain " : "Hillshade ", badge("derived"), el("div", { class: "src" },
      "Copernicus DEM GLO-30 (surface model)" + (state.terrain3d ? (M.getExaggeration() === 1 ? ", true relief" : `, relief exaggerated ×${M.getExaggeration()}`) : "")))));
  if (state.terrain3d) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#c9bba3" }),
    el("div", {}, "3D buildings ", badge("observed"), el("div", { class: "src" }, "OpenStreetMap footprints; heights from OSM tags, a default estimate where untagged"))));
  $("legend").replaceChildren(el("h2", {}, "On the map"), ...items);
}

function renderStatus() {
  const h = state.health;
  const pills = [];
  if (h) {
    pills.push(el("span", { class: `pill ${h.ai.mode === "fixture" ? "warn" : h.ai.configured ? "ok" : "bad"}`, title: h.ai.note },
      h.ai.mode === "fixture" ? "AI: demo stand-in" : h.ai.configured ? "AI ready" : "AI not configured"));
    pills.push(el("span", { class: `pill ${h.earthdata_configured ? "ok" : "warn"}`, title: "Needed only to download products for numeric backscatter" },
      h.earthdata_configured ? "Earthdata ready" : "No Earthdata login"));
  }
  pills.push(el("span", { class: `pill ${state.datasetKind === "demo" ? "warn" : state.dataset ? "ok" : ""}` },
    state.datasetKind === "demo" ? "Demo sectors" : state.dataset ? `${state.dataset.sectors.features.length} confirmed zone(s)` : "No zones yet"));
  $("status").replaceChildren(...pills);
}

// ------------------------------------------------------------------ map synchronisation
function drawZones(fit) {
  const feats = (state.dataset ? state.dataset.sectors.features : []).map((f) => ({
    type: "Feature", geometry: f.geometry,
    properties: { role: f.properties.exclusion_reason ? "no_go" : "candidate", label: f.properties.sector_name, id: f.properties.sector_id } }));
  M.setData("zones", { type: "FeatureCollection", features: feats });
  if (fit && feats.length) M.fitBounds(M.bboxOf({ features: feats }));
  renderLegend(); renderStatus(); renderSteps();
}

function drawFuture() {
  if (!state.scene || state.step !== "future") { M.setData("future", null); return; }
  const stage = state.scene.stages[state.futureStage];
  const vis = C.visiblePlacements(state.scene.placements, stage).filter((p) => p.lon !== null && p.lon !== undefined);
  M.setData("future", { type: "FeatureCollection", features: vis.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] }, properties: {} })) });
  M.setData("nodes", state.futureStage === 0 && state.plan ? { type: "FeatureCollection", features: state.plan.drone.nodes.map((n) => ({ type: "Feature", geometry: { type: "Point", coordinates: [n.lon, n.lat] }, properties: {} })) } : null);
  renderLegend();
}

function toggle3d(force) {
  const on = force === undefined ? !state.terrain3d : force;
  update({ terrain3d: M.setTerrain(on) });
  $("btn-3d").setAttribute("aria-pressed", String(on));
  $("relief").hidden = !on;
  renderLegend();
}

function onDrawChange(polys) {
  // Keep names/roles for zones that still exist; new polygons get defaults.
  const prev = new Map(state.drawn.map((z) => [z.id, z]));
  const meta = raiz.pendingMeta;
  raiz.pendingMeta = null;
  const drawn = polys.map((p, i) => {
    const old = prev.get(p.id);
    if (old) return { ...old, geometry: p.geometry };
    if (meta) return { id: p.id, geometry: p.geometry, ...meta };
    return { id: p.id, geometry: p.geometry, name: `Zone ${i + 1}`, role: "candidate", original_geometry: null, refinement: null };
  });
  for (const z of drawn) if (!z.original_geometry) z.original_geometry = z.geometry;
  state.drawn = drawn;
  if (state.datasetKind === "user") { invalidate("dataset"); drawZones(); endForStalePlan(); }
  if (state.step === "zones") renderPanel(); else { renderSteps(); renderStatus(); }
}

// ------------------------------------------------------------------ scenarios
async function selectScenario(id) {
  invalidate("scenario");
  D.clear();
  update({ scenarioId: id, scenario: await api(`/api/scenarios/${encodeURIComponent(id)}`), acquisitions: null, rain: null,
    dates: {}, coverage: {}, compare: { before: null, after: null, blend: 1, which: "after" }, imagery: { hls: null, nisar: null, rtc: null, imerg: null } });
  for (const k of ["hls", "nisar", "rtc", "imerg"]) M.setImagery(k, null);
  M.setData("zones", null); M.setData("nodes", null); M.setData("future", null); M.setData("suggestion", null);
  const s = state.scenario.summary;
  $("brand-place").textContent = s.primary ? "Piura" : "Carabayllo, Lima";
  const [w, so, e, n] = s.region_bbox;
  M.setData("region", { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[w, so], [e, so], [e, n], [w, n], [w, so]] } }] });
  M.flyTo([s.locator_lon, s.locator_lat], 11.5);
  renderPanel();
  await Promise.all([P.loadAcquisitions(), P.loadHlsDates()]);
  renderPanel();
}

// ------------------------------------------------------------------ guided tour
const TOUR = [
  ["Piura on real data", "The map shows Piura with real NISAR radar on its acquisition date, Copernicus terrain shading and an open street basemap. The legend at the bottom right always says where each layer comes from and when it was observed."],
  ["Draw the zones", "In Zones, click on the map to draw the area you want to assess. You can move or delete vertices, and ask for a boundary proposal from terrain and imagery. Nothing changes until you accept it."],
  ["Evidence and the rains", "Evidence measures slope from the DEM and lists the radar observations. After rain compares Sentinel-1 radar before and after the wettest days of 2026, because NISAR started over Piura in June."],
  ["Plan and future", "Plan turns a budget into seeds, germinated seedlings and established plants, kept separate. Future asks the AI for a scenario at 3, 6 and 12 months, shown on the 3D terrain and in camera AR."],
  ["Nothing is invented", "Unknown values stay unknown, demo data is labeled, and generated scenarios are never presented as observations."],
];
function tour(start) {
  let i = 0;
  const show = () => {
    $("tour-count").textContent = `Step ${i + 1} of ${TOUR.length}`;
    $("tour-title").textContent = TOUR[i][0];
    $("tour-text").textContent = TOUR[i][1];
    $("tour-next").textContent = i === TOUR.length - 1 ? "Start exploring" : "Next";
  };
  const close = () => { $("tour").hidden = true; try { localStorage.setItem("raiz-tour", "done"); } catch (_) {} };
  if (!start) { try { if (localStorage.getItem("raiz-tour") === "done") return; } catch (_) {} }
  $("tour").hidden = false; show(); $("tour-next").focus();
  $("tour-next").onclick = () => { if (i < TOUR.length - 1) { i += 1; show(); } else close(); };
  $("tour-skip").onclick = close;
}

// ------------------------------------------------------------------ boot
async function boot() {
  $("panel-toggle").addEventListener("click", () => {
    const p = $("panel"); const c = p.classList.toggle("collapsed");
    $("panel-toggle").setAttribute("aria-expanded", String(!c));
  });
  $("btn-3d").addEventListener("click", () => toggle3d());
  document.querySelectorAll("#relief [data-ex]").forEach((b) => b.addEventListener("click", () => {
    M.setExaggeration(Number(b.dataset.ex));
    document.querySelectorAll("#relief [data-ex]").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    renderLegend();
  }));
  $("btn-help").addEventListener("click", () => tour(true));
  $("btn-ar-quick").addEventListener("click", () => {
    if (state.scene) { import("./ar.js").then((m) => m.startAR(state.scene)); return; }
    const avail = C.stepAvailability(state);
    toast(avail.future.open ? "Generate the future scenario first; AR shows it on the printed target." : `AR needs a future scenario. ${avail.future.reason}`);
    if (avail.future.open) go("future");
  });
  wireHud();
  subscribe(() => renderStatus());
  try { update({ health: await api("/api/health") }); } catch (_) { toast("The API is not reachable."); }
  let scenarios;
  try { scenarios = await api("/api/scenarios"); } catch (e) { toast(`Could not load the study areas: ${e.message}`); return; }
  update({ scenarios });
  const primary = scenarios.find((s) => s.primary) || scenarios[0];
  M.on("error", (msg) => { if (/tiles\.openfreemap|basemap/i.test(msg)) toast("The basemap is unavailable right now; data layers still work."); });
  M.on("zoneClick", (p) => p && toast(`${p.label}: ${p.role === "no_go" ? "no-go zone" : "candidate zone"}`));
  await M.initMap("map", { center: [primary.locator_lon, primary.locator_lat], zoom: 6 });
  try { D.initDraw(M.getMap(), { onChange: onDrawChange, onWarn: toast }); }
  catch (e) { toast(e.message); }
  D.setMode("select");
  await selectScenario(primary.scenario_id);
  tour(false);
}

boot();
