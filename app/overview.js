// Area overview for the chosen focus area: huayco-relevant quebradas (Melton basin class), steep terrain (FAO slope
// classes), relief, and NISAR-observed ponding — drawn on the map with counters in the panel.
import { api, post } from "./api.js";
import * as M from "./map.js";
import { el, badge } from "./dom.js";
import { state, focusPoint } from "./state.js";
import { mark } from "./perf.js";

const C = window.RaizCore;
export const HAZARD_COLORS = { debris_flow_prone: "#c0392b", debris_flood: "#e67e22", flood: "#2a6fb0", unknown: "#8e8e8e" };
export const PONDING_COLORS = { new_water: "#1f78ff", persistent_low_backscatter: "#142878" };

function areaKey() { return state.focusArea ? state.focusArea.name : "locator"; }

/** Start both analyses for the focus area (each cached server-side; the second visit is immediate). */
export function loadOverview(rerender) {
  const key = areaKey();
  if (state.overview && state.overview.key === key) return;
  const [lon, lat] = focusPoint();
  state.overview = { key, landscape: null, landscapeError: null, nisar: { status: "submitting" } };
  M.setHillshade(true); state.overlays.hillshade = true; // relief visible by default: mountains read brown
  rerender();
  const t0 = performance.now();
  const q = new URLSearchParams({ west: lon - 0.12, south: lat - 0.12, east: lon + 0.12, north: lat + 0.12 });
  api(`/api/landscape?${q}`).then((r) => {
    if (!state.overview || state.overview.key !== key) return;
    state.overview.landscape = r;
    M.setLandscape(r);
    mark("data.landscape", key, performance.now() - t0);
    rerender();
  }).catch((e) => { if (state.overview && state.overview.key === key) { state.overview.landscapeError = e.message; rerender(); } });
  runAreaNisar(key, [lon - 0.06, lat - 0.06, lon + 0.06, lat + 0.06], rerender);
}

async function runAreaNisar(key, aoi, rerender) {
  const set = (v) => { if (state.overview && state.overview.key === key) { state.overview.nisar = v; rerender(); } };
  let st;
  try { st = await post("/api/nisar/water", { aoi, zones: [] }); } catch (e) { set({ status: "error", error: e.message }); return; }
  let attempt = 0;
  while (!C.JOB_TERMINAL.has(st.state)) {
    if (!state.overview || state.overview.key !== key) return;
    set({ status: st.state });
    await new Promise((r) => setTimeout(r, Math.min(8000, C.backoffDelay(attempt++) * 2)));
    try { st = await api(`/api/jobs/${encodeURIComponent(st.job_id)}`); } catch (_) { /* keep polling */ }
  }
  if (st.state === "ready" && st.result) {
    const feats = st.result.features.filter((f) => f.properties.class in PONDING_COLORS);
    M.setPondingMap({ type: "FeatureCollection", features: feats });
    set({ status: "ready", result: st.result, count: { new: feats.filter((f) => f.properties.class === "new_water").length,
      persistent: feats.filter((f) => f.properties.class === "persistent_low_backscatter").length } });
  } else set({ status: "error", error: st.error_message || "NISAR ponding analysis failed." });
}

const n = (v) => (v === null || v === undefined ? "—" : Number(v).toLocaleString("en-US", { maximumFractionDigits: 1 }));

export function overviewBlock(rerender) {
  const box = el("div", { class: "block overview" }, el("h2", {}, "Hazard and water overview ", badge("derived")));
  const o = state.overview && state.overview.key === areaKey() ? state.overview : null;
  if (!o) {
    box.append(el("p", { class: "note" }, "Load the area's terrain and radar analysis when needed. This can take several minutes on the first request."),
      el("button", { class: "btn", type: "button", onclick: () => loadOverview(rerender) }, "Load area overview"));
    return box;
  }
  // Quebradas and mountains.
  if (o.landscapeError) box.append(el("p", { class: "errline" }, `Terrain overview unavailable: ${o.landscapeError}`));
  else if (!o.landscape) box.append(el("p", { class: "note", role: "status" }, "Analysing quebradas and relief on the DEM…"));
  else {
    const L = o.landscape, c = L.quebrada_counts;
    const total = c.debris_flow_prone + c.debris_flood + c.flood + c.unknown;
    box.append(el("div", { class: "counters" },
      counter(total, "mapped quebradas and rivers", "#1d2428"),
      counter(c.debris_flow_prone, "debris-flow prone basins (huayco)", HAZARD_COLORS.debris_flow_prone),
      counter(c.debris_flood, "debris-flood basins", HAZARD_COLORS.debris_flood),
      counter(c.flood, "flood-type basins", HAZARD_COLORS.flood),
      counter(`${n(L.steep_ha)} ha`, "steep or very steep slopes (> 30 %)", "#8c5a32"),
      counter(L.elevation_m ? `${n(L.elevation_m.min)}–${n(L.elevation_m.max)} m` : "—", "elevation range", "#6b4423")));
    box.append(el("p", { class: "note" }, "Quebradas are coloured by basin type from the Melton ruggedness number (Wilford et al. 2004); grey = basin beyond the analysed area or large river. "
      + "Brown fill = steep (30–60 %) and very steep (> 60 %) slopes, FAO classes. Copernicus DEM; OpenStreetMap waterways. Susceptibility, not probability."));
  }
  // NISAR ponding.
  const w = o.nisar;
  if (!w || w.status === "submitting" || w.status === "queued" || w.status === "running") {
    box.append(el("p", { class: "note", role: "status" }, "Detecting ponded water with NISAR radar for this area… (first time for an area takes a few minutes)"));
  } else if (w.status === "error") box.append(el("p", { class: "errline" }, `NISAR ponding: ${w.error}`));
  else {
    const r = w.result, a = r.areas_ha;
    box.append(el("div", { class: "counters" },
      counter(w.count.new, `ponding patches newly observed by NISAR (${n(a.new_water)} ha)`, PONDING_COLORS.new_water),
      counter(w.count.persistent, `persistent dark patches: water or smooth dry ground (${n(a.persistent_low_backscatter)} ha)`, PONDING_COLORS.persistent_low_backscatter)));
    const v = (r.validation.held_out || []).find((t) => t.nisar_date === r.event.date) || (r.validation.held_out || [])[0];
    box.append(el("p", { class: "note" }, `NISAR L2 GCOV ${r.event.date} vs dry baseline ${r.baseline.map((b) => b.date).join(", ")} (rain in the 3 days before: ${n(r.event.rain && r.event.rain.antecedent_3d_mm)} mm, modeled). `
      + (v ? `Agreement with OPERA DSWx-HLS on ${v.nisar_date}: precision ${v.precision ?? "—"}, recall ${v.recall ?? "—"}.` : "No independent optical reference near the event.")));
  }
  return box;
}

function counter(value, label, color) {
  return el("div", { class: "counter" }, el("span", { class: "counter-v", style: `color:${color}` }, String(value)), el("span", { class: "counter-l" }, label));
}
