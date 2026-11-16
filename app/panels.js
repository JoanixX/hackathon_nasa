// One renderer per workflow step. Each returns the panel content for the current state.
import { api, post, runJob, evidence as evidenceJob } from "./api.js";
import * as M from "./map.js";
import * as D from "./draw.js";
import * as Ch from "./charts.js";
import { startAR } from "./ar.js";
import { $, el, badge, toast, statusLine, explain } from "./dom.js";
import { state, update, invalidate, focusBox, focusPoint } from "./state.js";
import { mark } from "./perf.js";
import { createLoadScope } from "./loading.js";
import * as T from "./twin.js";
import { nisarCard, nisarWater, runNisar } from "./nisar.js";
import { createTimeline, GROWTH_MONTHS } from "./timeline.js";
import { overviewBlock } from "./overview.js";
import { showDialog } from "./workflow.js";

let timeline = null; // the one active timeline (growth + event) shared by the 3D views, controls and export
export function disposeTimeline() { if (timeline) timeline.dispose(); timeline = null; }

const C = window.RaizCore;
export const TITLES = { explore: "Explore", zones: "Zones", evidence: "Terrain and radar", compare: "After the rains",
  plan: "Planting plan", future: "Future scenario", report: "Planning draft" };
export const LABELS = { explore: "Explore", zones: "Zones", evidence: "Evidence", compare: "After rain", plan: "Plan", future: "Future", report: "Report" };

let rerender = () => {};
export function setRerender(fn) { rerender = fn; }
export function clearCharts() { Ch.destroyAll(); }
const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);

// ------------------------------------------------------------------ data loaders
const loads = createLoadScope();
export function resetLoads() { loads.reset(); viewSequence += 1; state.layerLoading = {}; state.layerErrors = {}; }

export async function loadAcquisitions() {
  if (state.acquisitions && !state.acquisitions.error) return state.acquisitions;
  const b = focusBox();
  if (!b) return null;
  const q = new URLSearchParams({ west: b[0], south: b[1], east: b[2], north: b[3], start: "2025-10-01", end: today() });
  return loads.run("catalog", async signal => {
    try { return await api("/api/sources/acquisitions?" + q, { signal }); }
    catch (error) { if (error.name === "AbortError") throw error; return { error: error.message }; }
  }, acq => { update({ acquisitions: acq }); mark("data.acquisitions"); rerender(); });
}

/** Date probes are requested explicitly for one layer, never for all layers at startup. */
export async function loadLayerDates(key) {
  if (state.layerLoading[key] || state.dates[key] !== undefined) return;
  state.layerLoading[key] = true; delete state.layerErrors[key]; rerender();
  const p = focusPoint();
  const result = await loads.run("dates:" + key, async signal => {
    try {
      if (key === "hls") {
        const q = new URLSearchParams({ layer: "hls_s30", lon: p[0], lat: p[1], start: daysAgo(30), end: daysAgo(1) });
        const r = await api("/api/sources/dates?" + q, { signal });
        return { dates: r.dates.map(d => d.date), cov: {}, note: freshness(r) + (r.probe_errors ? ` ${r.probe_errors} date(s) could not be checked.` : "") };
      }
      let dates;
      const layer = { nisar: "nisar_gcov", rtc: "opera_rtc", dswx: "dswx" }[key];
      if (!layer) throw new Error("Unknown layer");
      if (key === "dswx") {
        dates = [];
        for (let t = Date.UTC(2026, 1, 1); t <= Date.UTC(2026, 2, 31); t += 864e5) dates.push(new Date(t).toISOString().slice(0, 10));
      } else {
        const acq = await loadAcquisitions();
        if (signal.aborted || !acq) return { dates: [], cov: {} };
        if (acq.error) throw new Error(acq.error);
        dates = acq.datasets[layer].map(d => d.date);
        if (key === "rtc") dates = dates.filter(d => d >= "2026-01-01" && d <= "2026-05-31");
      }
      if (!dates.length) return { dates: [], cov: {} };
      // API budget is 60 dates. Do not silently discard dates at a different limit.
      dates = dates.slice(-60);
      const q = new URLSearchParams({ layer, lon: p[0], lat: p[1], dates: dates.join(",") });
      const r = await api("/api/sources/coverage?" + q, { signal });
      const cov = Object.fromEntries(r.coverage.map(c => [c.date, c.valid_fraction]));
      return { dates: dates.filter(d => cov[d] >= 0.3), cov, note: freshness(r) + (r.probe_errors ? ` ${r.probe_errors} date(s) could not be checked.` : "") };
    } catch (error) { if (error.name === "AbortError") throw error; return { error: error.message }; }
  }, result => {
    state.layerLoading[key] = false;
    if (result.error) state.layerErrors[key] = result.error;
    else { state.dates[key] = result.dates; state.coverage[key] = result.cov; state.layerNotes[key] = (result.note || "").trim(); }
    mark("data." + key + ".dates", result.error || String(result.dates.length));
    rerender();
  });
  return result;
}

export const loadHlsDates = () => loadLayerDates("hls");

export function setLayer(key, date) {
  state.imagery[key] = date;
  if (date) { mark(`layer.${key}.set`, date); M.getMap().once("idle", () => mark(`layer.${key}.idle`, date)); }
  M.setImagery(key, date, key === "dswx" ? 1 : key === "imerg" ? 0.7 : key === "hls" ? 0.95 : 0.75);
  rerender();
}

// ------------------------------------------------------------------ 1. Explore
export function explore() {
  const s = state.scenario;
  const body = [];
  body.push(el("p", { class: "lead" },
    "Find potential planting sites around rainwater ponding, using up to three candidate plant types with low irrigation and fertilizer needs. Inspect evidence and field conditions before choosing a site."));
  const areas = el("div", { class: "block" }, el("h2", { text: "Piura" }),
    el("p", { class: "note" }, "Jump to a priority area. Data and dates follow the area you choose."));
  const row = el("div", { class: "row" });
  for (const fa of (s ? s.summary.focus_areas : [])) {
    row.append(el("button", { class: "btn", type: "button", "aria-pressed": String(state.focusArea && state.focusArea.name === fa.name),
      onclick: () => window.raiz.goToArea(fa) }, fa.name));
  }
  areas.append(row);
  body.push(areas);
  if (s) body.push(overviewBlock(rerender));
  if (s) body.push(el("p", { class: "note" }, s.summary.hazard_mechanism_note));

  const layers = el("div", { class: "block" }, el("h2", { text: "Map layers" }),
    el("p", { class: "note" }, "Every layer shows real observations on the dates listed. Pick a date to show it; the legend keeps the source and date."));
  layers.append(layerRow("nisar", "NISAR radar (GCOV)", state.dates.nisar, "Acquisition dates from the ASF catalog whose imagery covers this area. Areas without data stay transparent."));
  layers.append(layerRow("rtc", "Sentinel-1 radar (OPERA RTC)", state.dates.rtc, "Complementary C-band radar. Verify the returned dates and coverage for this local window."));
  layers.append(layerRow("dswx", "Surface water and ponding (DSWx-HLS)", state.dates.dswx, "Rainy-season dates with water observations here. Ponding (light blue) marks candidate low-irrigation planting sites to check in the field."));
  layers.append(layerRow("hls", "Optical context (HLS, 30 m)", state.dates.hls, "Dates in the last 30 days with pixels over this area; clouds may remain."));
  const rainDate = el("input", { type: "date", value: state.imagery.imerg || "", min: "2000-06-01", max: today(), "aria-label": "Rain rate date" });
  rainDate.addEventListener("change", () => setLayer("imerg", rainDate.value || null));
  layers.append(el("div", { class: "row" }, el("label", { text: "Rain rate (GPM IMERG, about 10 km)" }), rainDate,
    el("button", { class: "btn quiet", type: "button", onclick: () => setLayer("imerg", null) }, "Hide")));
  const controls = el("div", { class: "row" });
  for (const [key, title] of [["hillshade", "Terrain shading"], ["waterways", "Highlight waterways"]]) {
    if (key === "hillshade" && state.terrain3d) continue; // territorial controls own shading while in 3D
    controls.append(el("button", { class: "btn", type: "button", "aria-pressed": String(state.overlays[key]), onclick: () => {
      state.overlays[key] = !state.overlays[key];
      if (key === "hillshade") M.setHillshade(state.overlays[key]); else M.setVisibility(["quebradas", "rivers"], state.overlays[key]);
      rerender();
    } }, title));
  }
  layers.append(controls);
  body.push(layers);
  body.push(el("div", { class: "block" }, el("button", { class: "btn primary", type: "button", onclick: () => window.raiz.go("zones") }, "Draw zones to assess")));
  return body;
}

function layerRow(key, title, dates, hint) {
  const info = M.LAYER_INFO[key];
  const sel = el("select", { "aria-label": `${title} date` });
  sel.append(el("option", { value: "" }, "Off"));
  for (const d of (dates || []).slice().reverse()) {
    const c = state.coverage[key] && state.coverage[key][d];
    sel.append(el("option", { value: d, selected: d === state.imagery[key] }, c !== undefined && c < 0.9 ? `${d} (covers about ${Math.round(c * 100)}% of the area)` : d));
  }
  sel.disabled = !dates || !dates.length;
  sel.addEventListener("change", () => setLayer(key, sel.value || null));
  return el("div", { class: "block" }, el("h3", {}, title, " ", badge(info.cls)), el("p", { class: "note" }, hint),
    dates === undefined ? el("button", { class: "btn", type: "button", disabled: !!state.layerLoading[key], onclick: () => loadLayerDates(key) }, state.layerLoading[key] ? "Checking dates…" : "Load available dates") : null,
    state.layerErrors[key] ? el("p", { class: "errline" }, state.layerErrors[key]) : null,
    state.layerNotes[key] ? el("p", { class: "warnline" }, state.layerNotes[key]) : null,
    dates && !dates.length ? el("p", { class: "note" }, "No dates with coverage found in the checked period.") : null,
    sel, explain(info.explain));
}

// ------------------------------------------------------------------ 2. Zones
export function zones() {
  const body = [el("p", { class: "lead" },
    "Choose how many vertices the zone will have (4 to 8), then click on the map to place them. The zone closes itself on the last vertex. Select a zone to drag its vertices; the count stays fixed.")];
  const st = statusLine();
  const nSel = el("select", { "aria-label": "Number of vertices", id: "vertex-count" });
  for (let n = D.MIN_VERTICES; n <= D.MAX_VERTICES; n++) nSel.append(el("option", { value: String(n), selected: n === (window.raiz.vertexCount || 6) }, `${n} vertices`));
  nSel.addEventListener("change", () => { window.raiz.vertexCount = Number(nSel.value); });
  const startBtn = el("button", { class: "btn primary", type: "button", onclick: async () => {
    try { await window.raiz.ensureDraw(); } catch (e) { st.set(e.message, "error"); return; }
    const n = Number(nSel.value);
    window.raiz.vertexCount = n;
    D.startPlacing(n, (k, total, done) => st.set(done ? `Zone closed with ${total} vertices.` : `Place vertex ${k + 1} of ${total} (Esc cancels).`, done ? "ok" : "info"));
  } }, "Place the vertices");
  body.push(el("div", { class: "row" }, nSel, startBtn,
    el("button", { class: "btn quiet", type: "button", onclick: () => { D.clear(); update({ suggestion: null }); M.setData("suggestion", null); } }, "Delete all")), st);

  const list = el("div", { class: "block" }, el("h2", { text: `Drawn zones (${state.drawn.length})` }));
  if (!state.drawn.length) list.append(el("p", { class: "note" }, "No zone yet. Zones must lie inside the study region (dashed outline)."));
  state.drawn.forEach((z, i) => list.append(zoneItem(z, i)));
  body.push(list);

  if (state.suggestion) body.push(suggestionBlock());

  const confirm = statusLine();
  body.push(el("div", { class: "block" },
    el("button", { class: "btn primary", type: "button", disabled: !state.drawn.length, onclick: () => confirmZones(confirm) }, "Confirm zones and measure terrain"),
    confirm,
    el("p", { class: "note" }, "Confirming measures area and slope from the Copernicus DEM. Overlapping or self-crossing zones are rejected with the reason.")));

  if (state.dataset) body.push(zoneSummary());

  const imp = el("input", { type: "file", accept: ".geojson,.json,application/geo+json", class: "sr-only", id: "zone-file" });
  imp.addEventListener("change", (ev) => importFile(ev, confirm));
  body.push(el("details", { class: "block" }, el("summary", { text: "Other ways to add zones" }),
    el("div", { class: "row" }, el("label", { class: "btn", for: "zone-file" }, "Import GeoJSON"), imp,
      el("button", { class: "btn quiet", type: "button", onclick: loadDemo }, "Load demo sectors (synthetic)")),
    el("p", { class: "note" }, "Imported files keep their attributes after validation; legacy keys (nombre, hectareas, pendiente…) are translated. Demo sectors are synthetic and labeled as such.")));
  return body;
}

function zoneItem(z, i) {
  const name = el("input", { value: z.name, "aria-label": `Name of zone ${i + 1}`, maxlength: "120" });
  name.addEventListener("change", () => { z.name = name.value; invalidate("dataset"); });
  const role = el("select", { "aria-label": `Role of zone ${i + 1}` },
    el("option", { value: "candidate", selected: z.role === "candidate" }, "Candidate for planting"),
    el("option", { value: "no_go", selected: z.role === "no_go" }, "No-go (exclude)"));
  role.addEventListener("change", () => { z.role = role.value; invalidate("dataset"); window.raiz.drawZones(); });
  const area = el("span", { class: "note" }, z.refinement && z.refinement.accepted ? "Assisted boundary accepted" : "Drawn by you");
  return el("div", { class: `zone-item ${z.role}` },
    el("div", {}, name, role, area),
    el("div", { class: "row" },
      el("button", { class: "btn", type: "button", title: "Propose a boundary from terrain and imagery; nothing changes until you accept it", onclick: () => suggest(z) }, "Suggest boundary"),
      el("button", { class: "btn quiet", type: "button", "aria-label": `Delete zone ${i + 1}`, onclick: () => D.remove(z.id) }, "Delete")));
}

async function suggest(z) {
  toast("Computing a boundary proposal from the DEM and imagery…");
  try {
    const r = await post("/api/zones/suggest", { geometry: z.geometry, optical_date: state.imagery.hls || (state.dates.hls || [])[0] || null });
    M.setData("suggestion", { type: "FeatureCollection", features: [{ type: "Feature", geometry: r.suggested_geometry, properties: {} }] });
    update({ suggestion: { zoneId: z.id, ...r } });
    rerender();
  } catch (e) { toast(`No proposal: ${e.message}`); }
}

function suggestionBlock() {
  const s = state.suggestion;
  const m = s.metrics;
  return el("div", { class: "block" },
    el("h2", {}, "Boundary proposal ", el("span", { class: "badge b-derived" }, "proposal")),
    el("p", { class: "note" }, s.method),
    el("dl", { class: "kv" },
      el("dt", {}, "Your zone"), el("dd", {}, `${m.user_area_ha} ha`),
      el("dt", {}, "Proposal"), el("dd", {}, `${m.suggested_area_ha} ha`),
      el("dt", {}, "Overlap (IoU)"), el("dd", {}, String(m.iou)),
      el("dt", {}, "Largest shift"), el("dd", {}, `${m.max_boundary_shift_m} m`),
      el("dt", {}, "Sources"), el("dd", {}, s.sources.map((x) => x.layer + (x.date ? ` (${x.date})` : "")).join("; "))),
    el("p", { class: "note" }, s.note),
    el("div", { class: "row" },
      el("button", { class: "btn primary", type: "button", onclick: acceptSuggestion }, "Use the proposal"),
      el("button", { class: "btn", type: "button", onclick: () => { update({ suggestion: null }); M.setData("suggestion", null); } }, "Keep my zone")));
}

function acceptSuggestion() {
  const s = state.suggestion;
  const z = state.drawn.find((d) => d.id === s.zoneId);
  const meta = { name: z ? z.name : "", role: z ? z.role : "candidate", original_geometry: z ? z.original_geometry || z.geometry : s.user_geometry,
    refinement: { accepted: true, method: s.method, sources: s.sources, metrics: s.metrics, created_at: s.created_at } };
  window.raiz.pendingMeta = meta;
  D.replaceGeometry(s.zoneId, s.suggested_geometry);
  update({ suggestion: null });
  M.setData("suggestion", null);
  rerender();
  toast("Proposal applied. You can still edit its vertices.");
}

async function confirmZones(st) {
  st.set("Validating zones and reading the DEM…");
  try {
    const out = await post("/api/zones", { scenario_id: state.scenarioId, zones: state.drawn.map((z) => ({
      name: z.name, geometry: z.geometry, role: z.role, original_geometry: z.original_geometry || null, refinement: z.refinement || null })) });
    invalidate("dataset");
    update({ dataset: out, datasetKind: "user" });
    window.raiz.drawZones();
    rerender();
    toast(`${out.sectors.features.length} zone(s) confirmed with DEM slope.`);
    resetLoads();
    update({ acquisitions: null, dates: {}, coverage: {} });
  } catch (e) { st.set(e.message, "error"); }
}

async function importFile(ev, st) {
  const f = ev.target.files[0];
  ev.target.value = "";
  if (!f) return;
  if (f.size > 5 * 1024 * 1024) { st.set("The file exceeds 5 MB.", "error"); return; }
  try {
    const out = await post("/api/gis/normalize", { scenario_id: state.scenarioId, source_label: f.name, geojson: JSON.parse(await f.text()) });
    invalidate("dataset");
    update({ dataset: out, datasetKind: "import" });
    window.raiz.drawZones(true);
    rerender();
    toast(`Imported ${out.sectors.features.length} zone(s); ${out.rejected.length} rejected. ${out.warnings.join(" ")}`);
  } catch (e) { st.set(`Import failed; nothing changed. ${e.message}`, "error"); }
}

function loadDemo() {
  invalidate("dataset");
  const s = state.scenario;
  update({ dataset: { scenario_id: s.summary.scenario_id, dataset_version: s.summary.dataset_version, data_mode: "synthetic_fixture", sectors: s.sectors }, datasetKind: "demo" });
  window.raiz.drawZones(true);
  rerender();
  toast("Demo sectors loaded. They are synthetic polygons, not surveyed boundaries.");
}

function zoneSummary() {
  const feats = state.dataset.sectors.features;
  const t = el("table", {}, el("tr", {}, ...["Zone", "Area", "Slope (median)", "Elevation"].map((h) => el("th", {}, h))));
  for (const f of feats) {
    const p = f.properties, tr = p.terrain;
    t.append(el("tr", {}, el("td", {}, p.sector_name), el("td", { class: "num" }, C.quantityText(p.area_ha)),
      el("td", { class: "num" }, C.quantityText(p.slope_percent)),
      el("td", { class: "num" }, tr ? `${tr.elevation_m_min}–${tr.elevation_m_max} m` : "Unknown")));
  }
  return el("div", { class: "block" }, el("h2", {}, "Confirmed zones ", state.datasetKind === "demo" ? badge("fixture") : badge("derived")), t,
    el("div", { class: "row" }, el("button", { class: "btn primary", type: "button", onclick: () => window.raiz.go("evidence") }, "See terrain and radar evidence")));
}

// ------------------------------------------------------------------ 3. Evidence
export function evidence() {
  if (!state.acquisitions) loadAcquisitions();
  const feats = state.dataset.sectors.features;
  const body = [el("p", { class: "lead" }, "Where did NISAR observe rainwater ponding in your zones, and how steep are they?")];
  // NISAR is the primary evidence: it starts automatically for confirmed real zones (cached per area).
  if (state.dataset && state.datasetKind !== "demo" && !state.nisar) runNisar(rerender);
  body.push(nisarCard(rerender));
  body.push(hydrologyBlock());
  const withTerrain = feats.filter((f) => f.properties.terrain).map((f) => ({ name: f.properties.sector_name, terrain: f.properties.terrain }));
  const tb = el("div", { class: "block" }, el("h2", {}, "Slope ", badge("derived")));
  if (withTerrain.length) {
    const cv = el("canvas", { role: "img", "aria-label": "Share of each zone by slope class" });
    tb.append(el("div", { class: "chart" }, cv));
    requestAnimationFrame(() => Ch.slopeChart(cv, withTerrain));
    tb.append(el("p", { class: "note" }, withTerrain[0].terrain.note, " Source: Copernicus DEM GLO-30, 30 m."));
  } else tb.append(el("p", { class: "note" }, "No DEM statistics for these zones (demo sectors carry placeholder slopes). Draw and confirm real zones to measure slope."));
  body.push(tb);

  const ob = el("div", { class: "block" }, el("h2", {}, "Radar observations ", badge("observed")));
  const acq = state.acquisitions;
  if (!acq) ob.append(el("p", { class: "note" }, "Loading the ASF catalog…"));
  else if (acq.error) ob.append(el("p", { class: "errline" }, `Catalog unavailable: ${acq.error}`));
  else {
    for (const [key, label] of [["nisar_gcov", "NISAR GCOV (L-band)"], ["opera_rtc", "Sentinel-1 OPERA RTC (C-band)"]]) {
      const list = acq.datasets[key];
      ob.append(el("p", {}, el("strong", {}, label), `: ${list.length} acquisition day(s)` + (list.length ? ` from ${list[0].date} to ${list[list.length - 1].date}` : "")));
    }
    ob.append(el("p", { class: "note" }, acq.note));
    const last = (state.dates.nisar || []).slice(-1)[0];
    if (last) ob.append(el("button", { class: "btn", type: "button", onclick: () => setLayer("nisar", last) }, `Show NISAR on ${last}`));
  }
  body.push(ob);
  body.push(el("div", { class: "block" }, el("h2", { text: "Backscatter values (dB)" }),
    el("p", { class: "note" }, "Map imagery from GIBS is a colour rendering, so values are not read from it. Numeric backscatter per zone needs a downloaded NISAR product, which requires Earthdata Login on the server."),
    state.health && state.health.earthdata_configured
      ? el("button", { class: "btn", type: "button", onclick: () => window.raiz.go("compare") }, "Continue to the rain comparison")
      : el("p", { class: "warnline" }, "Earthdata Login is not configured: numeric backscatter is unavailable.")));
  body.push(el("div", { class: "row" }, el("button", { class: "btn primary", type: "button", onclick: () => window.raiz.go("compare") }, "Compare before and after the rains")));
  return body;
}

// ------------------------------------------------------------------ 4. Compare (post-rainfall)
export function compare() {
  if (!state.acquisitions) loadAcquisitions();
  if (state.dates.rtc === undefined && !state.layerLoading.rtc && !state.layerErrors.rtc) loadLayerDates("rtc");
  const body = [el("p", { class: "lead" },
    "Did the 2026 rains change the surface? NISAR began observing Piura in June 2026, so the rainy season is compared with Sentinel-1 radar on its real acquisition dates.")];
  const rb = el("div", { class: "block" }, el("h2", {}, "Rain, January to May 2026 ", badge("modeled")));
  if (!state.rain) { rb.append(el("p", { class: "note" }, "Loading NASA POWER rainfall…")); loadRain(); }
  else if (state.rain.error) rb.append(el("p", { class: "errline" }, `Rainfall unavailable: ${state.rain.error}`));
  else {
    const peaks = C.rainPeaks(state.rain.days, 3);
    const cv = el("canvas", { role: "img", "aria-label": "Daily rainfall with radar acquisition days" });
    rb.append(el("div", { class: "chart" }, cv));
    requestAnimationFrame(() => Ch.rainChart(cv, state.rain, state.acquisitions && !state.acquisitions.error ? state.acquisitions : null, peaks.map((p) => p.date)));
    rb.append(el("p", { class: "note" }, `Wettest days: ${peaks.map((p) => `${p.date} (${p.mm} mm)`).join(", ")}. ${state.rain.note}`));
    const rtc = state.dates.rtc || [];
    if (peaks.length && rtc.length && !state.compare.before) {
      const br = C.bracketDates(rtc, peaks[0].date);
      state.compare.before = br.before; state.compare.after = br.after;
    }
  }
  body.push(rb);

  const rtc = state.dates.rtc || [];
  const cb = el("div", { class: "block" }, el("h2", {}, "Radar before and after ", badge("observed")));
  if (!rtc.length) cb.append(el("p", { class: "note" }, state.acquisitions ? "No Sentinel-1 RTC acquisitions listed for this area." : "Loading acquisition dates…"));
  else {
    const mk = (which) => {
      const s = el("select", { "aria-label": which === "before" ? "Date before the rain" : "Date after the rain" });
      for (const d of rtc) s.append(el("option", { value: d, selected: d === state.compare[which] }, d));
      s.addEventListener("change", () => { state.compare[which] = s.value; showCompare(); });
      return s;
    };
    cb.append(el("div", { class: "compare-dates" }, el("label", {}, "Before", mk("before")), el("label", {}, "After", mk("after"))));
    const seg = el("div", { class: "seg", role: "group", "aria-label": "Show" });
    for (const [w, t] of [["before", "Before"], ["after", "After"]]) {
      seg.append(el("button", { type: "button", "aria-pressed": String(state.compare.which === w), onclick: () => { state.compare.which = w; showCompare(); rerender(); } }, t));
    }
    const blend = el("input", { type: "range", min: "0", max: "100", value: String(Math.round(state.compare.blend * 100)), "aria-label": "Blend the after image over the before image" });
    blend.addEventListener("input", () => { state.compare.blend = blend.value / 100; M.setImageryOpacity("rtc", state.compare.blend); });
    cb.append(el("div", { class: "row" }, seg, el("button", { class: "btn", type: "button", onclick: showCompare }, "Show on map")),
      el("label", { text: "Blend after over before" }), blend);
    cb.append(explain("Brighter after the rain can mean wetter soil, rougher surfaces or new vegetation; darker can mean smoother or standing water. Only dates on the same orbit track and direction are directly comparable; the 30 m pixels do not locate individual features."));
  }
  body.push(cb);

  const nis = state.dates.nisar || [];
  body.push(el("div", { class: "block" }, el("h2", {}, "Dry season with NISAR ", badge("observed")),
    nis.length ? el("div", { class: "row" },
      el("button", { class: "btn", type: "button", onclick: () => setLayer("nisar", nis[0]) }, `First (${nis[0]})`),
      el("button", { class: "btn", type: "button", onclick: () => setLayer("nisar", nis[nis.length - 1]) }, `Latest (${nis[nis.length - 1]})`))
      : el("p", { class: "note" }, "No NISAR acquisitions listed for this area.")));
  body.push(el("div", { class: "row" }, el("button", { class: "btn primary", type: "button", disabled: !state.dataset, onclick: () => window.raiz.go("plan") }, "Plan the planting")));
  return body;
}

async function loadRain() {
  const p = focusPoint();
  return loads.run("rain", async signal => {
    try { return await api(`/api/sources/rainfall?lat=${p[1]}&lon=${p[0]}&start=2026-01-01&end=2026-05-31`, { signal }); }
    catch (e) { if (e.name === "AbortError") throw e; return { error: e.message }; }
  }, rain => { update({ rain }); if (state.step === "compare") rerender(); });
}

function showCompare() {
  // The "before" date is drawn underneath and the "after" date on top with the chosen blend.
  const { before, after, which } = state.compare;
  M.setImagery("rtc", which === "before" ? before : after, which === "before" ? 1 : state.compare.blend);
  state.imagery.rtc = which === "before" ? before : after;
  rerender();
}

// ------------------------------------------------------------------ 5. Plan
export function plan() {
  const feats = state.dataset.sectors.features.filter((f) => !f.properties.exclusion_reason);
  const species = state.scenario.species;
  const body = [el("p", { class: "lead" }, "Choose a candidate species per zone and a budget. Seeds, germinated seedlings and established plants are counted separately.")];
  const sp = el("div", { class: "block" }, el("h2", { text: "Species per zone" }));
  for (const f of feats) {
    const p = f.properties;
    const s = el("select", { id: `sp-${p.sector_id}`, "aria-label": `Species for ${p.sector_name}` }, el("option", { value: "" }, "None (zone excluded from the plan)"));
    for (const x of species) s.append(el("option", { value: x.species_id, selected: (window.raiz.species[p.sector_id] || p.species_candidate) === x.species_id },
      `${x.common_name} — ${x.supplied_taxon || "taxon unspecified"}`));
    s.addEventListener("change", () => { window.raiz.species[p.sector_id] = s.value; invalidate("plan_inputs"); });
    sp.append(el("label", { for: s.id }, p.sector_name), s);
  }
  sp.append(el("p", { class: "note" }, "Species are source candidates awaiting specialist review, not prescriptions."));
  body.push(sp);
  const v = window.raiz.planInputs;
  const num = (key, label, attrs) => {
    const i = el("input", { type: "number", value: String(v[key]), ...attrs });
    i.addEventListener("change", () => { v[key] = i.value === "" ? null : Number(i.value); invalidate("plan_inputs"); });
    return el("div", {}, el("label", { text: label }), i);
  };
  body.push(el("div", { class: "block" }, el("h2", { text: "Budget" }), num("budget", "Municipal budget (PEN)", { min: "0", step: "100" }),
    el("details", {}, el("summary", {}, "Assumptions ", badge("illustrative")),
      num("density", "Target density (plants per ha)", { min: "0" }), num("spc", "Seeds per capsule", { min: "1" }),
      num("germ", "Germination fraction (0–1)", { min: "0.01", max: "1", step: "0.01" }), num("est", "Establishment fraction of germinated (0–1)", { min: "0.01", max: "1", step: "0.01" }),
      num("capcost", "Capsule cost (PEN)", { min: "0", step: "0.05" }), num("deliv", "Delivery cost per ha (PEN)", { min: "0" }),
      num("maint", "Maintenance cost per ha (PEN)", { min: "0" }), num("monit", "Fixed monitoring cost (PEN)", { min: "0" }),
      num("halflife", "Establishment half-life for delay scenarios (days; empty = not estimated)", { min: "1" }),
      el("p", { class: "note" }, "Replace these placeholders with specialist values; results are planning quantities, not predictions."))));
  const st = statusLine();
  const ready = state.nisar && state.nisar.status === "ready";
  body.push(el("div", { class: "block" }, el("h2", {}, "Evidence for this plan"),
    ready ? el("p", { class: "note" }, `NISAR-informed: zones are candidates only where NISAR observed new surface water on ${state.nisar.result.event.date} (evidence ${state.nisar.result.evidence_version}).`)
      : el("p", { class: "warnline" }, state.datasetKind === "demo" ? "Demo zones have no NISAR evidence: the plan is manual and labelled as such."
        : "NISAR evidence is not ready, so a NISAR-informed plan is blocked. Open the Evidence step to run it, or compute a plan explicitly labelled manual.")));
  body.push(el("div", { class: "block" },
    el("div", { class: "row" },
      el("button", { class: "btn primary", type: "button", disabled: !ready, onclick: () => computePlan(st, "nisar") }, "Compute the NISAR-informed plan"),
      el("button", { class: "btn", type: "button", onclick: () => computePlan(st, "manual") }, "Manual plan (not NISAR-informed)")), st));
  if (state.plan) body.push(planResults());
  return body;
}

async function computePlan(st, evidenceMode = "nisar") {
  const v = window.raiz.planInputs;
  const species = {};
  for (const f of state.dataset.sectors.features) {
    const s = window.raiz.species[f.properties.sector_id];
    if (s) species[f.properties.sector_id] = s;
  }
  const req = {
    scenario_id: state.scenarioId, dataset_version: state.dataset.dataset_version, mode: "budget", budget_pen: v.budget,
    species_by_sector: species,
    assumptions: { target_density_plants_per_ha: v.density, seeds_per_capsule: v.spc, germination_fraction: v.germ, establishment_fraction: v.est,
      capsule_cost_pen: v.capcost, delivery_cost_per_ha_pen: v.deliv, maintenance_cost_per_ha_pen: v.maint, monitoring_fixed_cost_pen: v.monit, max_slope_percent: 100 },
    establishment_half_life_days: v.halflife || null,
    evidence_mode: evidenceMode,
    nisar_run_id: evidenceMode === "nisar" && state.nisar && state.nisar.result ? state.nisar.result.run_id : null,
  };
  if (state.datasetKind !== "demo") req.imported_dataset_version = state.dataset.dataset_version;
  st.set("Computing…");
  try {
    const p = await post("/api/plans", req);
    invalidate("plan");
    update({ plan: p });
    M.setData("nodes", { type: "FeatureCollection", features: p.drone.nodes.map((n) => ({ type: "Feature", geometry: { type: "Point", coordinates: [n.lon, n.lat] }, properties: {} })) });
    rerender();
    toast(`Plan version ${p.plan_version} computed.`);
  } catch (e) { st.set(e.message, "error"); }
}

function planResults() {
  const b = state.plan.budget, t = b.totals;
  const names = Object.fromEntries(state.dataset.sectors.features.map((f) => [f.properties.sector_id, f.properties.sector_name]));
  const tbl = el("table", {}, el("tr", {}, ...["Zone", "Status", "Seeds", "Established", "Cost"].map((h) => el("th", {}, h))));
  for (const a of b.allocations) {
    const e = state.plan.eligibility.find((x) => x.sector_id === a.sector_id);
    tbl.append(el("tr", { title: e ? e.reasons.join(" ") : "" }, el("td", {}, names[a.sector_id] || a.sector_id), el("td", {}, e ? e.status.replaceAll("_", " ") : ""),
      el("td", { class: "num" }, C.formatCount(a.seeds_released)), el("td", { class: "num" }, C.formatCount(a.expected_established)), el("td", { class: "num" }, C.formatPEN(a.total_cost_cents))));
  }
  const cv = el("canvas", { role: "img", "aria-label": "Seeds, germination and establishment" });
  requestAnimationFrame(() => Ch.planChart(cv, t));
  const out = el("div", { class: "block" }, el("h2", {}, "Result ", badge("modeled")),
    b.feasible ? null : el("p", { class: "errline" }, b.infeasibility_reason),
    el("p", {}, `Total ${C.formatPEN(b.total_cost_cents)} of ${C.formatPEN(b.budget_cents)}; ${C.formatCount(t.capsules)} capsules on ${state.plan.drone.nodes.length} proposed drone deposition points (not executed).`),
    tbl, el("div", { class: "chart" }, cv), el("p", { class: "note" }, b.note));
  if (state.plan.establishment.status === "sensitivity_scenario") {
    const dc = el("canvas", { role: "img", "aria-label": "Establishment by planting delay" });
    requestAnimationFrame(() => Ch.delayChart(dc, state.plan.establishment));
    out.append(el("h3", {}, "Planting delay ", badge("illustrative")), el("div", { class: "chart" }, dc), el("p", { class: "note" }, state.plan.establishment.note));
  } else out.append(el("p", { class: "note" }, "Delay scenarios: not estimated (enter a half-life to run a sensitivity scenario)."));
  out.append(el("div", { class: "row" }, el("button", { class: "btn primary", type: "button", onclick: () => window.raiz.go("future") }, "Build the future scenario")));
  return out;
}

// ------------------------------------------------------------------ 6. Future scenario, 3D twin and AR
export function future() {
  const body = [el("p", { class: "lead" },
    "The AI proposes how the planted vegetation could look at 3, 6 and 12 months. It is a scenario under your assumptions, shown on the real terrain, not a forecast.")];
  const st = statusLine();
  body.push(el("div", { class: "block" }, el("button", { class: "btn primary", type: "button", onclick: () => generateScene(st) }, state.scene ? "Generate again" : "Generate the future scenario"), st));
  if (!state.scene) return body;
  const s = state.scene;
  body.push(el("div", { class: "block" },
    el("h2", {}, s.title, " ", badge(s.inference.mode === "actual_inference" ? "ai_generated" : "fixture")),
    el("p", { class: "note" }, `${s.inference.provider} / ${s.inference.model}; validated before assembly; plan ${s.plan_version}.`),
    el("div", { class: "seg", role: "group", "aria-label": "Time horizon" }, ...["Seeds", "3 months", "6 months", "12 months"].map((t, i) =>
      el("button", { type: "button", "aria-pressed": String(state.futureStage === i), onclick: () => { closeViews(); update({ futureStage: i }); window.raiz.drawFuture(); } }, t))),
    el("p", {}, s.stages[state.futureStage].caption),
    el("p", { class: "note" }, s.uncertainty_note),
    el("p", { class: "note" }, `${s.labels.marker}. ${s.frame.terrain}`),
    state.plan.budget.allocations.some((a) => a.capsules > 0 && a.funded_fraction < 1)
      ? el("p", { class: "warnline" }, "The budget funds only part of a zone. That part is drawn as the zone's core: the planting location inside the zone is not optimized.")
      : null));
  body.push(twinViews());
  body.push(el("div", { class: "block" }, el("h2", { text: "See it in 3D or AR" }),
    el("div", { class: "row" },
      el("button", { class: "btn", type: "button", onclick: () => window.raiz.toggle3d(true) }, "3D terrain view"),
      el("button", { class: "btn primary", type: "button", onclick: () => openAR() }, "Start camera AR")),
    el("ol", { class: "note" },
      el("li", {}, "Print the target or show it on a second screen: ", el("a", { href: "/assets/ar/target.png", target: "_blank", rel: "noopener" }, "open the AR target"), "."),
      el("li", {}, "Press Start camera AR and allow the camera."),
      el("li", {}, "Point the camera at the whole target. The terrain, zones and vegetation appear on it; tap a zone to inspect it.")),
    el("p", { class: "note" }, "The 3D terrain view is the georeferenced twin on the map. Camera AR registers the same scene to the printed target at tabletop scale; it is not survey-grade geolocation.")));
  body.push(el("div", { class: "row" }, el("button", { class: "btn", type: "button", onclick: () => window.raiz.go("report") }, "Write the planning draft")));
  return body;
}

// ------------------------------------------------------------------ 3D before/after views
const VIEWS = [
  ["before", "Before: ponding after rain"],
  ["after", "After: planted trees"],
  ["huayco_trees", "Huayco with the trees"],
  ["huayco_none", "Huayco without the trees"],
];

function plannedZones() {
  const funded = new Set((state.plan ? state.plan.budget.allocations : []).filter((a) => a.capsules > 0).map((a) => a.sector_id));
  return state.dataset ? state.dataset.sectors.features.filter((f) => funded.has(f.properties.sector_id)) : [];
}

/** " Last valid copy from N h ago" when the provider failed and a cached result was served. */
export function freshness(r) {
  const c = r && r.cache;
  if (!c || !c.stale) return "";
  const h = c.age_s / 3600;
  return " Last valid copy from " + (h < 1 ? Math.max(1, Math.round(c.age_s / 60)) + " min" : h < 48 ? Math.round(h) + " h" : Math.round(h / 24) + " days") + " ago: the provider did not answer now.";
}

let viewSequence = 0;
export function closeViews() { viewSequence += 1; state.twinView = null; disposeTimeline(); T.clearAll(); }
function ensurePonding() {
  // NISAR-observed water first (the required evidence); DSWx-HLS optical only when no NISAR result exists.
  const nw = nisarWater();
  if (nw) return Promise.resolve({ ...nw, water: nw.features.length, cloud_fraction: 0, nisar: true });
  if (state.ponding) return Promise.resolve(state.ponding);
  const b = focusBox();
  return loads.run("ponding", async signal => {
    const candidates = ["2026-02-12", "2026-02-27", "2026-03-14", "2026-02-09", "2026-01-13"];
    const results = await Promise.all(candidates.map(async date => {
      const q = new URLSearchParams({ west: b[0], south: b[1], east: b[2], north: b[3], date });
      try { const r = await evidenceJob("/api/sources/ponding?" + q, { signal }); return { ...r, water: r.pixel_counts.open_water + r.pixel_counts.partial_water }; }
      catch (e) { if (e.name === "AbortError") throw e; return null; }
    }));
    const valid = results.filter(Boolean).sort((a, b) => b.water - a.water);
    if (!valid.length) throw new Error("Water evidence is unavailable; ponding is unknown.");
    return valid[0];
  }, best => { state.ponding = best; mark("data.ponding", best.date); });
}

function ensurePath() {
  if (state.flowPath) return Promise.resolve(state.flowPath);
  const initialStart = state.huaycoStart;
  const z = plannedZones()[0] || (state.dataset && state.dataset.sectors.features[0]);
  const box = z ? M.bboxOf({ features: [z] }) : focusBox();
  return loads.run("flow:" + JSON.stringify(initialStart), async signal => {
    let start = initialStart;
    if (!start) throw new Error("Choose the huayco start on a highlighted quebrada first.");
    const path = await api(`/api/terrain/flowpath?lon=${start[0]}&lat=${start[1]}&max_km=6`, { signal });
    if (path.geometry.coordinates.length < 2) throw new Error("No downhill path can be drawn from this start point.");
    return { start, path };
  }, result => {
    if (state.huaycoStart === initialStart) { state.huaycoStart = result.start; state.flowPath = result.path; }
  }).then(result => result && result.path);
}

export async function showView(view, st, { record = false } = {}) {
  const sequence = ++viewSequence;
  const current = () => sequence === viewSequence;
  const speciesById = Object.fromEntries(state.scenario.species.map((s) => [s.species_id, s]));
  state.twinView = view;
  if (window.raiz.renderLegend) window.raiz.renderLegend();
  disposeTimeline(); // one render loop at a time: a new view replaces the previous timeline
  T.clearAll();
  M.setData("future", null); M.setData("nodes", null);
  if (!state.terrain3d) await window.raiz.toggle3d(true);
  const run = async () => {
    if (view === "before" || view === "after") {
      const bounds = state.scene.frame.bbox_lonlat || M.bboxOf({ features: plannedZones() });
      if (bounds) M.fitBounds(bounds, 70, false);
      M.getMap().jumpTo({ pitch: 60 });
    }
    if (view === "before") {
      st.set("Loading observed ponding…");
      const p = await ensurePonding();
      if (!current()) return;
      T.setWater(p ? { type: "FeatureCollection", features: p.features } : null);
      if (p && p.nisar) st.set(`NISAR-observed surface water on ${p.date}: ${p.features.length} water bodies (new and persistent classes; 20 m radar grid). Water thickness in 3D is illustrative.`, "ok");
      else st.set(p && p.water ? `Observed surface water and ponding on ${p.date}: ${p.features.length} water bodies (cloud ${Math.round(p.cloud_fraction * 100)}% of the area, unknown).${p.tiles_failed ? ` ${p.tiles_failed} image tile(s) did not load: those parts are unknown.` : ""}${freshness(p)}`
        : "No surface water observed on the available dates for this area.", "ok");
      await new Promise((r) => setTimeout(r, record ? 6000 : 0));
    } else if (view === "after") {
      // Growth on the timeline: month 0 = seeds, then saplings to the mature form (illustrative curve).
      startTimeline({ placements: state.scene.placements, speciesById, path: null, zones: [], withTrees: true }, st);
      st.set(`Plantation growth from seeding (month 0) to ${GROWTH_MONTHS} months; one 3D tree per marker, species shapes from the plan. Growth curve is illustrative.`, "ok");
    } else {
      if (!state.huaycoStart || !state.ravine || state.ravine.decision !== "accepted") {
        st.set("Choose the huayco start on a highlighted quebrada first: the start must be inside a mapped ravine corridor.", "error");
        return;
      }
      st.set("Tracing the quebrada downhill on the DEM…");
      const path = await ensurePath();
      if (!current() || !path) return;
      const withTrees = view === "huayco_trees";
      const zones = plannedZones();
      // Same camera framing (path + planted zones) for both views so they are comparable.
      const b = M.bboxOf({ features: [path, ...zones] });
      if (b) M.fitBounds(b, 120);
      T.setPath(path);
      await new Promise((r) => setTimeout(r, 1300));
      if (!current()) return;
      startTimeline({ placements: state.scene.placements, speciesById, path, zones, withTrees }, st, (s) => {
        if (s.eventProg >= 1) st.set(withTrees
          ? (s.hit >= 0 ? `After ${s.months} months of growth the front reaches the planted zone and stops within about ${T.ASSUMED_STOP_CELLS * 30} m (illustrative assumption, not a modeled effect).`
            : "The downhill path does not cross a planted zone, so the trees do not meet the flow here.")
          : `Without trees the front runs the whole ${Math.round(path.properties.length_m)} m path (${path.properties.drop_m} m drop) and spreads at the bottom.`, "ok");
      });
    }
  };
  if (!record) { try { return await run(); } catch (error) { if (current()) st.set(error.message, "error"); return; } }
  st.set("Recording video…");
  let url;
  const label = (state.scene.inference.mode === "fixture" ? "FIXTURE — " : "Illustrative — ") + view.replaceAll("_", " ");
  try {
    if (view === "before") url = await T.recordVideo(run, 30, label);
    else {
      await run();
      if (!timeline) throw new Error("The timeline could not start for this view.");
      timeline.pause();
      st.set("Exporting the timeline frame by frame…");
      url = await T.recordTimeline(timeline, { fps: 12, label, caption: (s) => `plantation ${s.months} months` + (s.eventProg > 0 ? ` · huayco ${Math.round(s.eventProg * 100)}%` : "") });
    }
  }
  catch (error) { mark("video.failed", error.message + " " + JSON.stringify(T.recordingStats)); st.set(error.message, "error"); return; }
  mark("video.ready", JSON.stringify(T.recordingStats));
  const a = document.createElement("a");
  a.href = url; a.download = `raiz-${view}.webm`; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
  st.set("Video saved (WebM).", "ok");
}

/** Camera AR with the real place: map snapshot draped on the DEM, observed ponding, huayco path, species shapes. */
export async function openAR() {
  const s = state.scene;
  if (!s) return;
  const extras = { species: (state.scenario && state.scenario.species) || [], ponding: state.ponding || null, path: state.flowPath || null };
  try {
    // Bounded wait: the AR must start even if the map never settles (slow tiles, software WebGL).
    if (state.textureOn && s.frame.bbox_lonlat) extras.texture = await Promise.race([M.snapshot(s.frame.bbox_lonlat, 1024, s.frame.target_aspect),
      new Promise((r) => setTimeout(() => r(null), 8000))]);
    mark("ar.snapshot", extras.texture ? "ok" : "timeout");
  } catch (e) { toast("The map snapshot for AR failed; the relief is shown without it."); }
  return startAR(s, extras);
}

/** Huayco start: the API decides (accepted / rejected / insufficient); eligible natural corridors are highlighted. */
function chooseRavineStart(st) {
  st.set("Click on a highlighted quebrada where the huayco starts.");
  const z = plannedZones()[0] || (state.dataset && state.dataset.sectors.features[0]);
  if (z) {
    const b = M.bboxOf({ features: [z] });
    api(`/api/terrain/ravine?lon=${(b[0] + b[2]) / 2}&lat=${(b[1] + b[3]) / 2}`).then((r) => M.setCorridors(r.eligible_corridors)).catch(() => {});
  }
  M.getMap().once("click", async (e) => {
    const lon = e.lngLat.lng, lat = e.lngLat.lat;
    st.set("Checking the point against mapped ravines and the DEM…");
    try {
      const r = await api(`/api/terrain/ravine?lon=${lon}&lat=${lat}`);
      state.ravine = r;
      M.setCorridors(r.eligible_corridors);
      if (r.decision === "accepted") {
        state.huaycoStart = [lon, lat]; state.flowPath = null; viewSequence += 1;
        const c = r.catchment || {};
        const area = c.basin_area_km2 ?? c.basin_area_km2_lower_bound;
        st.set(`${r.message} ${r.corridor && r.corridor.name ? r.corridor.name + ". " : ""}Upslope basin ${area} km²`
          + (c.melton_ratio !== null && c.melton_ratio !== undefined ? `, Melton ratio ${c.melton_ratio} (${c.class.replaceAll("_", " ")}, Wilford et al. 2004).` : ". Melton ratio not computed (basin beyond the analysis window)."), "ok");
      } else {
        state.huaycoStart = null; state.flowPath = null;
        st.set(`${r.message} ${r.reason}`, "error");
      }
    } catch (err) { st.set(err.message, "error"); }
  });
}

/** DEM hydrology per zone: wetness index, closed depressions (ponding potential) and upslope area. */
function hydrologyBlock() {
  const box = el("div", { class: "block" }, el("h2", {}, "Terrain hydrology ", badge("derived")));
  const feats = state.dataset ? state.dataset.sectors.features.filter((f) => !f.properties.exclusion_reason) : [];
  state.hydro = state.hydro || {};
  for (const f of feats) {
    const sid = f.properties.sector_id;
    const h = state.hydro[sid];
    if (h === undefined) {
      state.hydro[sid] = null;
      post("/api/zones/hydrology", { geometry: f.geometry }).then((r) => { state.hydro[sid] = r; rerender(); })
        .catch((e) => { state.hydro[sid] = { error: e.message }; rerender(); });
    }
    if (!h) { box.append(el("p", { class: "note" }, `${f.properties.sector_name}: computing…`)); continue; }
    if (h.error) { box.append(el("p", { class: "errline" }, `${f.properties.sector_name}: ${h.error}`)); continue; }
    const d = h.depressions;
    box.append(el("p", {}, el("strong", {}, f.properties.sector_name), `: wetness index (TWI) median ${h.twi.median}, p90 ${h.twi.p90}; `
      + `closed depressions ${d.area_ha} ha, deepest ${d.max_depth_m} m${d.within_dem_uncertainty ? " (within the DEM vertical uncertainty of 4 m)" : ""}, `
      + `${d.stored_volume_m3} m³ fill volume; largest upslope area ${h.max_upslope_area_km2} km².`));
  }
  box.append(el("p", { class: "note" }, "Copernicus DEM GLO-30 (surface model). TWI = ln(a/tan slope), Beven and Kirkby (1979), relative; depressions by priority-flood, Barnes et al. (2014)."));
  return box;
}

/** Start (or replace) the shared timeline and drive the controls from its clock. */
function startTimeline(opts, st, onState) {
  disposeTimeline();
  timeline = createTimeline(opts);
  timeline.onTick((s) => { updateTimelineUI(s); if (onState) onState(s); });
  timeline.seek(0);
  timeline.play();
}

function updateTimelineUI(s) {
  const r = document.getElementById("tl-range"), lab = document.getElementById("tl-label"), pb = document.getElementById("tl-play");
  if (r) r.value = String(s.t);
  if (lab) lab.textContent = `Plantation age ${s.months} months` + (s.eventProg > 0 ? ` · huayco ${Math.round(s.eventProg * 100)}%` : "") + ` · ${s.t.toFixed(1)} / ${s.total.toFixed(1)} s`;
  if (pb && timeline) pb.textContent = timeline.playing ? "Pause" : "Play";
  if (r && timeline) r.max = String(timeline.total);
}

function timelineControls() {
  const range = el("input", { id: "tl-range", type: "range", min: "0", max: String(timeline ? timeline.total : 20), step: "0.05", value: String(timeline ? timeline.time : 0), "aria-label": "Timeline position" });
  range.addEventListener("input", () => { if (!timeline) return; timeline.pause(); timeline.seek(Number(range.value)); });
  const play = el("button", { id: "tl-play", class: "btn", type: "button", onclick: () => { if (!timeline) return; timeline.playing ? timeline.pause() : timeline.play(); updateTimelineUI(timeline.stateAt(timeline.time)); } }, "Play");
  const restart = el("button", { class: "btn", type: "button", onclick: () => timeline && timeline.restart() }, "Restart");
  const speed = el("select", { "aria-label": "Playback speed" }, ...[0.5, 1, 2, 4].map((v) => el("option", { value: String(v), selected: v === 1 }, `${v}×`)));
  speed.addEventListener("change", () => timeline && timeline.setSpeed(Number(speed.value)));
  return el("div", { class: "timeline" }, el("div", { class: "row" }, play, restart, speed), range, el("p", { id: "tl-label", class: "note", "aria-live": "polite" }, "Open a growth or huayco view to start the timeline."));
}

function twinViews() {
  const st = statusLine();
  // Each view loads only its own evidence when opened.
  const seg = el("div", { class: "seg wrap", role: "group", "aria-label": "3D view" });
  for (const [k, t] of VIEWS) {
    const b = el("button", { type: "button", "aria-pressed": String(state.twinView === k) }, t);
    b.addEventListener("click", () => { [...seg.children].forEach((x) => x.setAttribute("aria-pressed", String(x === b))); showView(k, st); });
    seg.append(b);
  }
  const startBtn = el("button", { class: "btn", type: "button", title: "Click a highlighted quebrada where the huayco starts", onclick: () => chooseRavineStart(st) }, "Choose the huayco start");
  return el("div", { class: "block" }, el("h2", {}, "Before and after in 3D ", badge("illustrative")),
    el("p", { class: "note" }, "Ponding comes from NISAR radar water evidence (OPERA DSWx-HLS optical only when no NISAR result exists). Trees are 3D models of the planned species. The huayco starts only on an accepted mapped ravine and follows the real downhill path of the terrain; how far the flow goes is illustrative, not a debris-flow model."),
    seg,
    timelineControls(),
    el("div", { class: "row" }, startBtn,
      el("button", { class: "btn", type: "button", onclick: () => showView(state.twinView || "huayco_none", st, { record: true }) }, "Record this view as video")),
    st);
}

async function generateScene(st) {
  const res = await runJob({ kind: "scene", path: "/api/scenes", body: { plan_version: state.plan.plan_version }, bound: true,
    currentPlan: () => state.plan && state.plan.plan_version, onStatus: (m, k) => st.set(m, k), timeoutMs: 300000 });
  if (res && res.state === "ready" && res.result) {
    const errs = C.validateScene(res.result, state.plan.plan_version);
    if (errs.length) { st.set(`Scene rejected by validation: ${errs.join(" ")}`, "error"); return; }
    update({ scene: res.result, sceneJob: res });
    rerender();
    window.raiz.drawFuture();
  }
}

// ------------------------------------------------------------------ 7. Report
export function report() {
  const body = [el("p", { class: "lead" }, "A draft for specialist review, with sources, dates and who wrote each statement.")];
  const st = statusLine();
  body.push(el("div", { class: "row" },
    el("button", { class: "btn primary", type: "button", onclick: () => makeReport(st) }, "Generate the draft"),
    el("button", { class: "btn", type: "button", disabled: !state.report, onclick: printReport }, "Print or save as PDF")), st);
  if (state.report) body.push(el("button",{class:"btn detail-launch",type:"button","aria-label":"Open complete report",onclick:()=>showDialog("Municipal planning draft",reportDom(state.report))},"Open complete report"));
  return body;
}

async function makeReport(st) {
  const version=state.plan.plan_version;st.set("Preparing the municipal draft…","loading");
  const started=performance.now();
  try {
    const draft=await post("/api/reports/preview",{plan_version:version,scene_job_id:state.scene&&state.sceneJob?state.sceneJob.job_id:null});
    if(state.plan?.plan_version!==version)return;
    mark("report.ready",`${Math.round(performance.now()-started)} ms · deterministic`);
    update({report:draft});rerender();
  }catch(error){st.set(error.message,"error");}
}

function reportDom(r, print = false) {
  const root = el("div", {});
  root.append(el("p", { class: print ? "watermark" : "warnline" }, r.status_label), el("h2", {}, r.title),
    el("p", { class: "note" }, `Report ${r.report_version}; plan ${r.plan_version}; AI narrative: ${r.ai_status.replaceAll("_", " ")}; created ${r.created_at} UTC.`));
  const label=k=>k.replaceAll("_"," ").replace(/^./,c=>c.toUpperCase());
  for (const [k,statements] of Object.entries(r.sections)) {
    root.append(el("h3", {}, label(k)), el("ul", {}, ...statements.map((s) => el("li", {}, s.text, " ", el("span", { class: "badge b-unknown" }, s.authorship.replaceAll("_", " ")),
      s.source_ids?.length?el("small",{},` Sources: ${s.source_ids.join(", ")}`):""))));
  }
  for(const [key,rows]of Object.entries(r.tables)) {
    if(!rows.length)continue;
    const columns=Array.from(new Set(rows.flatMap(row=>Object.keys(row))));
    const table=el("table",{},el("thead",{},el("tr",{},...columns.map(c=>el("th",{scope:"col"},label(c))))));
    table.append(el("tbody",{},...rows.map(row=>el("tr",{},...columns.map(c=>{
      const value=row[c]??"Unknown";
      return el("td",{},c==="url"&&String(value).startsWith("https://")?el("a",{href:value,target:"_blank",rel:"noopener"},"Official source"):typeof value==="object"?JSON.stringify(value):String(value));
    })))));
    root.append(el("h3",{},label(key)),table);
  }
  root.append(el("p", { class: "note" }, "Not an approved technical dossier. No institution has reviewed or endorsed it."));
  return root;
}

function printReport() {
  $("print-area").replaceChildren(reportDom(state.report, true));
  window.print();
}
