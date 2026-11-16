// Boot, step navigation, legend/provenance, guided tour and map synchronisation.
import { api } from "./api.js";
import * as M from "./map.js";
import * as D from "./draw.js";
import * as P from "./panels.js";
import { wireHud, endForStalePlan } from "./ar.js";
import { $, el, badge, toast, announce } from "./dom.js";
import { state, update, subscribe, invalidate } from "./state.js";
import { mark, marks } from "./perf.js";
import { loadScript } from "./loading.js";

const C = window.RaizCore;
const RENDER = { explore: P.explore, zones: P.zones, evidence: P.evidence, compare: P.compare, plan: P.plan, future: P.future, report: P.report };

const raiz = {
  species: {},
  pendingMeta: null,
  planInputs: { budget: 25000, density: 400, spc: 3, germ: 0.3, est: 0.4, capcost: 0.6, deliv: 180, maint: 120, monit: 1500, halflife: null },
  go, selectScenario, drawZones, drawFuture, toggle3d, goToArea, ensureDraw, renderLegend: () => renderLegend(),
  state, // read-only handle for diagnostics and browser tests
  perf: marks,
};
window.raiz = raiz;
let territory = null, territoryLoading = null;
async function ensureTerritory() {
  if (!territoryLoading) territoryLoading = import("./territory.js").then(({ createTerritory }) => {
    territory = createTerritory(M.getMap(), { onError: toast, setBuildings: M.setBuildings, setHillshade: M.setHillshade,
      setMaterials: M.setTerritoryMaterials, fitRegion: bounds => M.fitBounds(bounds, 35), onChange: renderLegend });
    raiz.territory = territory;
    return territory;
  }).catch(error => { territoryLoading = null; throw error; });
  return territoryLoading;
}

let drawingReady = null;
async function ensureDraw() {
  if (!drawingReady) drawingReady = loadScript("https://cdn.jsdelivr.net/npm/terra-draw@1.38.0/dist/terra-draw.umd.js")
    .then(() => loadScript("https://cdn.jsdelivr.net/npm/terra-draw-maplibre-gl-adapter@1.4.1/dist/terra-draw-maplibre-gl-adapter.umd.js"))
    .then(() => D.initDraw(M.getMap(), { onChange: onDrawChange, onWarn: toast }))
    .catch(error => { drawingReady = null; throw error; });
  return drawingReady;
}

// ------------------------------------------------------------------ navigation
function go(step) {
  const avail = C.stepAvailability(state);
  if (!avail[step].open) { toast(avail[step].reason); return; }
  if (state.step === "zones" && step !== "zones") D.setMode("select");
  if (state.step === "future" && step !== "future") P.closeViews();
  // The before/after radar belongs to the comparison; leaving it restores an uncluttered map.
  if (state.step === "compare" && step !== "compare" && state.imagery.rtc) { state.imagery.rtc = null; M.setImagery("rtc", null); }
  update({ step });
  if (step === "zones") ensureDraw().catch(error => toast(error.message));
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
  P.clearCharts();
  $("panel-title").textContent = P.TITLES[state.step];
  $("panel-title").tabIndex = -1;
  let content;
  try { content = RENDER[state.step](); }
  catch (e) { content = [el("p", { class: "errline" }, `This step could not be shown: ${e.message}`)]; console.error(e); }
  $("panel-body").replaceChildren(...(state.terrain3d && territory ? [territory.controls] : []), ...content);
  renderSteps();
  renderLegend();
}
P.setRerender(() => { renderPanel(); });

// ------------------------------------------------------------------ legend and provenance
function renderLegend() {
  const items = [];
  // Swatches use the colours actually painted on the map (2D and 3D).
  const SW = {
    nisar: "linear-gradient(90deg,#1e9e3a,#c040b0,#f0f0f0)", rtc: "linear-gradient(90deg,#1b1b1b,#7a7a7a,#e8e8e8)",
    hls: "linear-gradient(90deg,#8a7a5a,#5f8a3c,#d8d0bc)", imerg: "linear-gradient(90deg,#9ad1f5,#2a6fdb,#7b2cbf)",
  };
  for (const [key, date] of Object.entries(state.imagery)) {
    if (!date) continue;
    const info = M.LAYER_INFO[key];
    if (key === "dswx") {
      items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#0000ff" }), el("div", {}, el("strong", {}, "Open water"), " ", badge(info.cls), el("div", { class: "src" }, `${date} · ${info.src}`))));
      items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#b4d5f4" }), el("div", {}, el("strong", {}, "Partial water, ponding"))));
      items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:rgba(175,175,175,.5)" }), el("div", {}, "Cloud: unknown, not dry")));
      continue;
    }
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: `background:${SW[key] || "#888"}` }),
      el("div", {}, el("strong", {}, info.title), " ", badge(info.cls), el("div", { class: "src" },
        `${date} UTC · ${info.src}${key === "nisar" || key === "rtc" ? " · colours are radar channels, not land classes" : ""}`))));
  }
  if (state.overlays.waterways) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:repeating-linear-gradient(90deg,#2a6fb0 0 6px,transparent 6px 9px)" }),
    el("div", {}, "Quebradas (dashed) and rivers ", badge("observed"), el("div", { class: "src" }, "OpenStreetMap waterways"))));
  const territorialMaterials = state.terrain3d && territory?.options.materials;
  const P = territorialMaterials ? { ...M.PALETTE, park: "#a5ae76", motorway: "#62676a", trunk: "#62676a", secondary: "#62676a" } : M.PALETTE;
  items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:linear-gradient(90deg,#dfc8a6,#c39a92,#8daac1)" }),
    el("div", {}, "Buildings by height ", badge("observed"), el("div", { class: "src" }, "Overture Maps footprints (OSM, Google Open Buildings, Microsoft ML). Light grey: height not mapped, drawn 3 m in 3D."))));
  items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: `background:${P.park}` }), el("div", {}, "Parks and grass", el("div", { class: "src" }, "OpenStreetMap; wood darker green, sand beige"))));
  items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: `background:linear-gradient(90deg,${P.motorway} 0 33%,${P.trunk} 33% 66%,${P.secondary} 66%)` }),
    el("div", {}, "Roads: motorway, trunk/primary, secondary", el("div", { class: "src" }, territorialMaterials ? "Mapped streets grey; paths earth-toned (OpenStreetMap)" : "Streets white with grey edge; paths brown dashed (OpenStreetMap)"))));
  if (state.twinView) {
    const sp = state.scenario ? state.scenario.species : [];
    const showTrees = ["after", "huayco_trees"].includes(state.twinView);
    for (const s of sp) if (showTrees && s.model && s.model.crown_color) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: `background:${s.model.crown_color}` }), el("div", {}, `${s.common_name} tree (3D model)`)));
    if (state.twinView === "before") items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#2f7fd8" }), el("div", {}, "Observed ponding (3D water)")));
    if (state.twinView.startsWith("huayco")) {
      const flood = state.flowPath && state.flowPath.properties && state.flowPath.properties.kind === "flood";
      items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: `background:${flood ? "#2f7fd8" : "#7b5a3a"}` }), el("div", {}, flood ? "Flood along the river " : "Huayco front ", badge("illustrative"))));
    }
  }
  if (state.dataset || state.drawn.length) {
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#e2a33b" }), el("div", {}, "Candidate zone",
      state.datasetKind === "demo" ? badge("fixture") : null)));
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#e2654f" }), el("div", {}, "No-go zone")));
  }
  if (state.suggestion) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#1b6fa8" }), el("div", {}, "Boundary proposal (not applied)")));
  if (state.plan && state.plan.drone.nodes.length && state.step === "future" && state.futureStage === 0 && !state.twinView) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#f4d35e;border-radius:50%" }), el("div", {}, "Proposed seed deposition point (not executed)")));
  if (state.scene && state.step === "future" && !state.twinView) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:#4f8a3a;border-radius:50%" }),
    el("div", {}, "Future vegetation ", badge(state.scene.inference.mode === "actual_inference" ? "ai_generated" : "fixture"), el("div", { class: "src" }, state.scene.labels.marker))));
  if (state.overview && state.overview.landscape) {
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:linear-gradient(90deg,#c0392b 0 33%,#e67e22 33% 66%,#2a6fb0 66%)" }),
      el("div", {}, "Quebradas by basin type: debris flow, debris flood, flood ", badge("derived"), el("div", { class: "src" }, "Melton ruggedness (Wilford et al. 2004) on Copernicus DEM; grey = unknown"))));
    items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:linear-gradient(90deg,#a0703f,#6b4423)" }),
      el("div", {}, "Steep and very steep slopes (> 30 %, > 60 %) ", badge("derived"), el("div", { class: "src" }, "FAO slope classes, Copernicus DEM"))));
  }
  if (state.overview && state.overview.nisar && state.overview.nisar.status === "ready") items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:linear-gradient(90deg,#1f78ff 0 50%,#142878 50%)" }),
    el("div", {}, "Ponding observed by NISAR: new, persistent dark ", badge("derived"), el("div", { class: "src" }, `NISAR L2 GCOV ${state.overview.nisar.result.event.date} vs dry baseline`))));
  if (state.terrain3d || state.overlays.hillshade) items.push(el("div", { class: "li" }, el("span", { class: "swatch", style: "background:linear-gradient(90deg,#d9b98a,#b8875a,#8c5a32,#4a2e17)" }),
    el("div", {}, state.terrain3d ? "3D surface: DEM relief with mapped cover " : "Relief shaded from elevation ", badge("derived"), el("div", { class: "src" },
      "Copernicus DEM GLO-30 (surface model)" + (state.terrain3d ? (M.getExaggeration() === 1 ? ", true relief" : `, relief exaggerated ×${M.getExaggeration()}`) : "")))));
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
  if (!state.scene || state.step !== "future" || state.twinView) { M.setData("future", null); M.setData("nodes", null); return; }
  const stage = state.scene.stages[state.futureStage];
  const vis = C.visiblePlacements(state.scene.placements, stage).filter((p) => p.lon !== null && p.lon !== undefined);
  M.setData("future", { type: "FeatureCollection", features: vis.map((p) => ({ type: "Feature", geometry: { type: "Point", coordinates: [p.lon, p.lat] }, properties: {} })) });
  M.setData("nodes", state.futureStage === 0 && state.plan ? { type: "FeatureCollection", features: state.plan.drone.nodes.map((n) => ({ type: "Feature", geometry: { type: "Point", coordinates: [n.lon, n.lat] }, properties: {} })) } : null);
  renderLegend();
}

function toggle3d(force) {
  const on = force === undefined ? !state.terrain3d : force;
  const ready = on ? ensureTerritory() : null;
  update({ terrain3d: M.setTerrain(on) });
  $("btn-3d").setAttribute("aria-pressed", String(on));
  $("relief").hidden = !on;
  if (on) ready.then(t => {
    if (!state.terrain3d) return;
    t.setActive(true); $("panel-body").prepend(t.controls); renderLegend();
  }).catch(error => { toast(error.message); toggle3d(false); });
  else { territory?.setActive(false); territory?.controls.remove(); M.setHillshade(state.overlays.hillshade); }
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

/** Navigation never waits for an external catalog; stale requests are cancelled. */
async function goToArea(fa) {
  mark("area.go", fa.name);
  P.resetLoads();
  const map = M.getMap();
  map.jumpTo({ center: [fa.lon, fa.lat], zoom: fa.zoom });
  update({ focusArea: fa, rain: null, acquisitions: null, dates: {}, coverage: {},
    compare: { before: null, after: null, blend: 1, which: "after" } });
  for (const key of Object.keys(M.LAYER_INFO)) { state.imagery[key] = null; M.setImagery(key, null); }
  renderPanel();
  mark("area.ready", fa.name);
}

// ------------------------------------------------------------------ scenarios
async function selectScenario(id) {
  P.resetLoads();
  invalidate("scenario");
  D.clear();
  update({ scenarioId: id, scenario: await api(`/api/scenarios/${encodeURIComponent(id)}`), acquisitions: null, rain: null,
    dates: {}, coverage: {}, compare: { before: null, after: null, blend: 1, which: "after" }, imagery: { hls: null, nisar: null, rtc: null, imerg: null } });
  for (const k of Object.keys(M.LAYER_INFO)) M.setImagery(k, null);
  M.setData("zones", null); M.setData("nodes", null); M.setData("future", null); M.setData("suggestion", null);
  const s = state.scenario.summary;
  $("brand-place").textContent = s.primary ? "Piura" : "Carabayllo, Lima";
  const [w, so, e, n] = s.region_bbox;
  M.setData("region", { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: [[w, so], [e, so], [e, n], [w, n], [w, so]] } }] });
  M.setRegionMask(null);
  if (s.region_boundary) {
    // Exact department boundary: outline it and dim everything outside (zones outside are refused by the API).
    api(`/api/region/${encodeURIComponent(id)}/boundary`).then((b) => { if (state.scenarioId === id) M.setRegionMask(b); })
      .catch(() => toast("The department boundary could not be loaded; the region box is shown instead."));
  }
  const fa = (s.focus_areas || [])[0];
  update({ focusArea: fa || null });
  if (fa) M.getMap().jumpTo({ center: [fa.lon, fa.lat], zoom: fa.zoom }); else M.flyTo([s.locator_lon, s.locator_lat], 11);
  renderPanel();
  mark("data.scenario_ready");
}

// ------------------------------------------------------------------ guided tour
const TOUR = [
  ["Piura on real data", "Start with streets, buildings and land cover. Load radar, surface water or rainfall only when needed. The legend identifies each visible layer, its source and observation date."],
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
  mark("boot.start");
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
    if (state.scene) { P.openAR(); return; }
    const avail = C.stepAvailability(state);
    toast(avail.future.open ? "Generate the future scenario first; AR shows it on the printed target." : `AR needs a future scenario. ${avail.future.reason}`);
    if (avail.future.open) go("future");
  });
  wireHud();
  subscribe(() => renderStatus());
  api("/api/health").then(health => { update({ health }); mark("api.health"); }).catch(() => toast("The API is not reachable."));
  let scenarios;
  try { scenarios = await api("/api/scenarios"); } catch (e) { toast(`Could not load the study areas: ${e.message}`); return; }
  update({ scenarios });
  mark("api.scenarios");
  const primary = scenarios.find((s) => s.primary) || scenarios[0];
  M.on("error", (msg) => { if (/tiles\.openfreemap|basemap/i.test(msg)) toast("The basemap is unavailable right now; data layers still work."); });
  M.on("zoneClick", (p) => p && toast(`${p.label}: ${p.role === "no_go" ? "no-go zone" : "candidate zone"}`));
  const first = (primary.focus_areas || [])[0];
  // Open directly on the study area (no fly-in from a continental zoom, which fetched every zoom level).
  await M.initMap("map", { center: first ? [first.lon, first.lat] : [primary.locator_lon, primary.locator_lat], zoom: first ? first.zoom : 9, region: primary.region_bbox });
  mark("map.load");
  M.getMap().once("idle", () => mark("map.first_idle"));
  await selectScenario(primary.scenario_id);
  tour(false);
}

boot();
