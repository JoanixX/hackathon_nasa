// One renderer per workflow step. Each returns the panel content for the current state.
import { api, post, runJob } from "./api.js";
import * as M from "./map.js";
import * as D from "./draw.js";
import * as Ch from "./charts.js";
import { startAR } from "./ar.js";
import { $, el, badge, toast, statusLine, explain } from "./dom.js";
import { state, update, invalidate, focusBox, focusPoint } from "./state.js";

const C = window.RaizCore;
export const TITLES = { explore: "Explore", zones: "Zones", evidence: "Terrain and radar", compare: "After the rains",
  plan: "Planting plan", future: "Future scenario", report: "Planning draft" };
export const LABELS = { explore: "Explore", zones: "Zones", evidence: "Evidence", compare: "After rain", plan: "Plan", future: "Future", report: "Report" };

let rerender = () => {};
export function setRerender(fn) { rerender = fn; }
const today = () => new Date().toISOString().slice(0, 10);
const daysAgo = (n) => new Date(Date.now() - n * 864e5).toISOString().slice(0, 10);

// ------------------------------------------------------------------ data loaders
export async function loadAcquisitions() {
  const b = focusBox();
  if (!b) return;
  try {
    const q = new URLSearchParams({ west: b[0], south: b[1], east: b[2], north: b[3], start: "2025-10-01", end: today() });
    const acq = await api(`/api/sources/acquisitions?${q}`);
    const nisarAll = acq.datasets.nisar_gcov.map((d) => d.date);
    const rtcAll = acq.datasets.opera_rtc.map((d) => d.date);
    // Keep only dates whose imagery actually covers this area (catalog footprints are larger than the data).
    const p = focusPoint();
    const covered = async (layer, dates, min) => {
      if (!dates.length) return { dates: [], cov: {} };
      const q = new URLSearchParams({ layer, lon: p[0], lat: p[1], dates: dates.slice(-60).join(",") });
      const r = await api(`/api/sources/coverage?${q}`);
      const cov = Object.fromEntries(r.coverage.map((c) => [c.date, c.valid_fraction]));
      return { dates: dates.filter((d) => (cov[d] || 0) >= min), cov };
    };
    // NISAR first (shown on load), then the rainy-season Sentinel-1 dates (January–May 2026).
    const n = await covered("nisar_gcov", nisarAll, 0.3);
    update({ acquisitions: acq, dates: { ...state.dates, nisar: n.dates }, coverage: { ...state.coverage, ...n.cov } });
    if (!state.imagery.nisar && n.dates.length) {
      // Show real radar first: the NISAR date covering most of this area (latest on ties).
      const best = n.dates.slice().sort((a, b) => (n.cov[b] || 0) - (n.cov[a] || 0) || b.localeCompare(a))[0];
      setLayer("nisar", best);
    } else if (["explore", "evidence", "compare"].includes(state.step)) rerender();
    const r = await covered("opera_rtc", rtcAll.filter((d) => d >= "2026-01-01" && d <= "2026-05-31").slice(-45), 0.3);
    update({ dates: { ...state.dates, rtc: r.dates }, coverage: { ...state.coverage, ...r.cov } });
  } catch (e) {
    update({ acquisitions: { error: e.message } });
  }
  if (["explore", "evidence", "compare"].includes(state.step)) rerender();
}

export async function loadHlsDates() {
  const p = focusPoint();
  if (!p) return;
  try {
    const q = new URLSearchParams({ layer: "hls_s30", lon: p[0], lat: p[1], start: daysAgo(60), end: daysAgo(1) });
    const r = await api(`/api/sources/dates?${q}`);
    update({ dates: { ...state.dates, hls: r.dates.map((d) => d.date).reverse() } });
  } catch (e) {
    update({ dates: { ...state.dates, hls: [], hlsError: e.message } });
  }
  if (state.step === "explore") rerender();
}

export function setLayer(key, date) {
  state.imagery[key] = date;
  M.setImagery(key, date, key === "imerg" ? 0.7 : key === "hls" ? 0.95 : 0.75);
  rerender();
}

// ------------------------------------------------------------------ 1. Explore
export function explore() {
  const s = state.scenario;
  const body = [];
  body.push(el("p", { class: "lead" },
    "Find where root-forming vegetation could reduce erosion and huaico risk. Look at the terrain and the radar, then draw the zones you want to assess."));
  const areas = el("fieldset", { class: "block" }, el("legend", { class: "sr-only" }, "Study area"), el("h2", { text: "Study area" }));
  for (const sc of state.scenarios) {
    const input = el("input", { type: "radio", name: "area", value: sc.scenario_id, checked: sc.scenario_id === state.scenarioId });
    input.addEventListener("change", () => window.raiz.selectScenario(sc.scenario_id));
    areas.append(el("label", { class: "choice" }, input, el("span", {},
      el("span", { class: "t" }, sc.primary ? "Piura (primary)" : "Carabayllo, Lima (secondary)"),
      el("span", { class: "d" }, sc.intervention_case))));
  }
  body.push(areas);
  if (s) body.push(el("p", { class: "note" }, s.summary.hazard_mechanism_note));

  const layers = el("div", { class: "block" }, el("h2", { text: "Map layers" }),
    el("p", { class: "note" }, "Every layer shows real observations on the dates listed. Pick a date to show it; the legend keeps the source and date."));
  layers.append(layerRow("nisar", "NISAR radar (GCOV)", state.dates.nisar, "Acquisition dates from the ASF catalog whose imagery covers this area. Areas without data stay transparent."));
  layers.append(layerRow("rtc", "Sentinel-1 radar (OPERA RTC)", state.dates.rtc, "January–June 2026, covering the rainy season, when NISAR had not yet observed Piura."));
  layers.append(layerRow("hls", "Optical context (HLS, 30 m)", state.dates.hls, "Dates in the last 60 days with pixels over this area; clouds may remain."));
  const rainDate = el("input", { type: "date", value: state.imagery.imerg || "", min: "2000-06-01", max: today(), "aria-label": "Rain rate date" });
  rainDate.addEventListener("change", () => setLayer("imerg", rainDate.value || null));
  layers.append(el("div", { class: "row" }, el("label", { text: "Rain rate (GPM IMERG, about 10 km)" }), rainDate,
    el("button", { class: "btn quiet", type: "button", onclick: () => setLayer("imerg", null) }, "Hide")));
  body.push(layers);
  body.push(el("div", { class: "block" }, el("button", { class: "btn primary", type: "button", onclick: () => window.raiz.go("zones") }, "Draw zones to assess")));
  return body;
}

function layerRow(key, title, dates, hint) {
  const info = M.LAYER_INFO[key];
  const sel = el("select", { "aria-label": `${title} date` });
  sel.append(el("option", { value: "" }, dates === undefined ? "Loading dates…" : dates && dates.length ? "Off" : "No dates available"));
  for (const d of (dates || []).slice().reverse()) {
    const c = state.coverage && state.coverage[d];
    sel.append(el("option", { value: d, selected: d === state.imagery[key] }, c !== undefined && c < 0.9 ? `${d} (covers about ${Math.round(c * 100)}% of the area)` : d));
  }
  sel.disabled = !dates || !dates.length;
  sel.addEventListener("change", () => setLayer(key, sel.value || null));
  return el("div", { class: "block" }, el("h3", {}, title, " ", badge(info.cls)), el("p", { class: "note" }, hint), sel, explain(info.explain));
}

// ------------------------------------------------------------------ 2. Zones
export function zones() {
  const body = [el("p", { class: "lead" },
    "Click on the map to place vertices; click the first vertex or double-click to close the zone. Choose Edit to drag vertices or the whole zone; right-click a vertex to delete it.")];
  const st = statusLine();
  body.push(el("div", { class: "row" },
    el("button", { class: "btn primary", type: "button", onclick: () => { D.setMode("polygon"); st.set("Drawing: click to add vertices, click the first vertex to close."); } }, "Draw a zone"),
    el("button", { class: "btn", type: "button", onclick: () => { D.setMode("select"); st.set("Editing: select a zone to move or delete vertices."); } }, "Edit"),
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
    loadAcquisitions();
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
  const feats = state.dataset.sectors.features;
  const body = [el("p", { class: "lead" }, "How steep are the zones, and which radar observations exist for them?")];
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
  try { update({ rain: await api(`/api/sources/rainfall?lat=${p[1]}&lon=${p[0]}&start=2026-01-01&end=2026-05-31`) }); }
  catch (e) { update({ rain: { error: e.message } }); }
  if (state.step === "compare") rerender();
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
  body.push(el("div", { class: "block" }, el("button", { class: "btn primary", type: "button", onclick: () => computePlan(st) }, "Compute the plan"), st));
  if (state.plan) body.push(planResults());
  return body;
}

async function computePlan(st) {
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
      el("button", { type: "button", "aria-pressed": String(state.futureStage === i), onclick: () => { update({ futureStage: i }); window.raiz.drawFuture(); } }, t))),
    el("p", {}, s.stages[state.futureStage].caption),
    el("p", { class: "note" }, s.uncertainty_note),
    el("p", { class: "note" }, `${s.labels.marker}. ${s.frame.terrain}`),
    state.plan.budget.allocations.some((a) => a.capsules > 0 && a.funded_fraction < 1)
      ? el("p", { class: "warnline" }, "The budget funds only part of a zone. That part is drawn as the zone's core: the planting location inside the zone is not optimized.")
      : null));
  body.push(el("div", { class: "block" }, el("h2", { text: "See it in 3D or AR" }),
    el("div", { class: "row" },
      el("button", { class: "btn", type: "button", onclick: () => window.raiz.toggle3d(true) }, "3D terrain view"),
      el("button", { class: "btn primary", type: "button", onclick: () => startAR(state.scene) }, "Start camera AR")),
    el("ol", { class: "note" },
      el("li", {}, "Print the target or show it on a second screen: ", el("a", { href: "/assets/ar/target.png", target: "_blank", rel: "noopener" }, "open the AR target"), "."),
      el("li", {}, "Press Start camera AR and allow the camera."),
      el("li", {}, "Point the camera at the whole target. The terrain, zones and vegetation appear on it; tap a zone to inspect it.")),
    el("p", { class: "note" }, "The 3D terrain view is the georeferenced twin on the map. Camera AR registers the same scene to the printed target at tabletop scale; it is not survey-grade geolocation.")));
  body.push(el("div", { class: "row" }, el("button", { class: "btn", type: "button", onclick: () => window.raiz.go("report") }, "Write the planning draft")));
  return body;
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
  if (state.report) body.push(reportDom(state.report));
  return body;
}

async function makeReport(st) {
  const res = await runJob({ kind: "report", path: "/api/reports", bound: true, currentPlan: () => state.plan && state.plan.plan_version,
    body: { plan_version: state.plan.plan_version, scene_job_id: state.scene && state.sceneJob ? state.sceneJob.job_id : null }, onStatus: (m, k) => st.set(m, k) });
  if (res && (res.state === "ready" || res.state === "partial") && res.result) { update({ report: res.result }); rerender(); }
}

function reportDom(r, print = false) {
  const root = el("div", {});
  root.append(el("p", { class: print ? "watermark" : "warnline" }, r.status_label), el("h2", {}, r.title),
    el("p", { class: "note" }, `Report ${r.report_version}; plan ${r.plan_version}; AI narrative: ${r.ai_status.replaceAll("_", " ")}; created ${r.created_at} UTC.`));
  const titles = { scope: "Scope", summary: "Summary", quantities: "Planned quantities", scene: "Future scenario", field_checks: "Field checks", monitoring: "Monitoring", risks: "Risks", limitations: "Limitations" };
  for (const k of Object.keys(titles)) {
    if (!r.sections[k]) continue;
    root.append(el("h3", {}, titles[k]), el("ul", {}, ...r.sections[k].map((s) => el("li", {}, s.text, " ", el("span", { class: "badge b-unknown" }, s.authorship.replaceAll("_", " "))))));
  }
  const t = el("table", {}, el("tr", {}, ...["Zone", "Area (ha)", "Slope (%)", "Lat", "Lon", "Seeds", "Established", "Cost"].map((h) => el("th", {}, h))));
  for (const s of r.tables.sectors) t.append(el("tr", {}, ...[s.sector_name, s.area_ha, s.slope_percent ?? "Unknown", s.lat, s.lon, s.seeds_released, s.expected_established, s.cost].map((v) => el("td", {}, String(v)))));
  root.append(el("h3", {}, "Zones"), t, el("p", { class: "note" }, "Not an approved technical dossier. No institution has reviewed or endorsed it."));
  return root;
}

function printReport() {
  $("print-area").replaceChildren(reportDom(state.report, true));
  window.print();
}
