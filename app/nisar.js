// NISAR water evidence for the confirmed zones: job, images (shown in the panel, not on the map) and measurements.
import { api, post } from "./api.js";
import { el, badge, statusLine, toast } from "./dom.js";
import { state, invalidate } from "./state.js";
import { mark } from "./perf.js";

const C = window.RaizCore;
let polling = null;

function zonesForEvidence() {
  return state.dataset.sectors.features.filter((f) => !f.properties.exclusion_reason)
    .map((f) => ({ sector_id: f.properties.sector_id, name: f.properties.sector_name, geometry: f.geometry }));
}

/** Area of interest: the zones' box padded by 0.02 deg (the server snaps it and caps it at 0.25 deg). */
function aoi() {
  let w = 180, s = 90, e = -180, n = -90;
  const walk = (c) => { if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); } else c.forEach(walk); };
  state.dataset.sectors.features.forEach((f) => walk(f.geometry.coordinates));
  return [w - 0.02, s - 0.02, e + 0.02, n + 0.02];
}

export async function runNisar(rerender, eventDate = null) {
  const key = state.dataset.dataset_version + ":" + (eventDate || "auto");
  if (state.nisar && state.nisar.key === key && state.nisar.status !== "error") return;
  state.nisar = { key, status: "submitting" };
  rerender();
  const t0 = performance.now();
  let st;
  try {
    st = await post("/api/nisar/water", { aoi: aoi(), event_date: eventDate, zones: zonesForEvidence() });
  } catch (e) { state.nisar = { key, status: "error", error: e.message }; rerender(); return; }
  const mine = (polling = Symbol("nisar"));
  let attempt = 0;
  while (!C.JOB_TERMINAL.has(st.state)) {
    if (polling !== mine || !state.nisar || state.nisar.key !== key) return; // superseded (zones changed)
    state.nisar = { key, status: st.state, job_id: st.job_id };
    rerender();
    await new Promise((r) => setTimeout(r, Math.min(8000, C.backoffDelay(attempt++) * 2)));
    try { st = await api(`/api/jobs/${encodeURIComponent(st.job_id)}`); } catch (e) { /* keep polling */ }
  }
  if (polling !== mine || !state.nisar || state.nisar.key !== key) return;
  if (st.state === "ready" && st.result) {
    state.nisar = { key, status: "ready", result: st.result };
    invalidate("plan_inputs"); // the plan depends on this evidence version
    state.plan = null;
    mark("data.nisar_water", st.result.evidence_version, performance.now() - t0);
    toast(`NISAR evidence ready: ${st.result.event.date} vs dry baseline.`);
  } else state.nisar = { key, status: "error", error: st.error_message || "NISAR evidence failed.", code: st.error_code };
  rerender();
}

const fmt = (v, d = 2) => (v === null || v === undefined ? "—" : Number(v).toFixed(d));
const ha = (v) => (v === null || v === undefined ? "—" : v < 0.01 && v > 0 ? "<0.01" : Number(v).toFixed(2));

function img(r, name, alt) {
  return el("img", { src: `/api/nisar/files/${r.run_id}/${r.images[name]}`, alt, loading: "lazy", class: "nisar-img" });
}

export function nisarCard(rerender) {
  const box = el("div", { class: "block nisar" }, el("h2", {}, "NISAR water evidence ", badge("observed"), " ", badge("derived")));
  const s = state.nisar;
  if (!state.dataset || state.datasetKind === "demo") {
    box.append(el("p", { class: "note" }, "Confirm real zones first: the NISAR analysis is computed for their exact boundaries."));
    return box;
  }
  if (!s || s.status === "error") {
    if (s && s.error) box.append(el("p", { class: "errline" }, s.error));
    box.append(el("p", { class: "note" }, "Reads the real NISAR L2 GCOV radar (HH, HV, 20 m) over your zones for every acquisition on one orbit track, "
      + "picks a dry baseline and the latest rain event from NASA POWER rainfall, and measures new, persistent and receded surface water. "
      + "The first run for an area reads the radar from NASA (a few minutes); later runs reuse it."),
      el("button", { class: "btn primary", type: "button", onclick: () => runNisar(rerender) }, s ? "Try again" : "Analyse ponding with NISAR"));
    return box;
  }
  if (s.status !== "ready") {
    box.append(el("p", { class: "note", role: "status" }, s.status === "running" ? "Reading NISAR GCOV windows and classifying water… (first run per area takes minutes)"
      : "Queued for the radar worker…"));
    return box;
  }
  const r = s.result;
  const ev = r.event, base = r.baseline[r.baseline.length - 1];
  box.append(el("p", {}, el("strong", {}, `Event ${ev.date}`), ` (rain in the 3 days before: ${fmt(ev.rain && ev.rain.antecedent_3d_mm, 1)} mm, modeled) compared with the dry baseline `,
    el("strong", {}, r.baseline.map((b) => b.date).join(", ")), `. Track ${r.track} ${String(r.direction).toLowerCase()}, frame ${r.frame}; same geometry on every date.`));
  // Before / after radar images (real GCOV, false colour) and the water classes over the event image.
  const pair = el("div", { class: "nisar-pair" },
    el("figure", {}, img(r, `radar_${base.date}`, `NISAR radar on ${base.date}`), el("figcaption", {}, `Before: ${base.date}`)),
    el("figure", {}, el("div", { class: "nisar-stack" }, img(r, `radar_${ev.date}`, `NISAR radar on ${ev.date}`), img(r, "classes", "Water classes")),
      el("figcaption", {}, `After: ${ev.date}, with water classes`)));
  box.append(pair,
    el("p", { class: "note" }, "Radar colours: red = HH, green = HV, blue = HH−HV (dB, fixed stretch). Classes: ",
      el("span", { class: "sw", style: "background:#1f78ff" }), " new water ",
      el("span", { class: "sw", style: "background:#142878" }), " persistent low backscatter ",
      el("span", { class: "sw", style: "background:#f0aa28" }), " receded ",
      el("span", { class: "sw", style: "background:#969696" }), " unknown."));
  // Per-zone measurements.
  const rows = r.zones.map((z) => el("tr", {},
    el("td", {}, z.name || z.sector_id), el("td", {}, z.valid_coverage === null ? "—" : `${Math.round(z.valid_coverage * 100)}%`),
    el("td", {}, `${fmt(z.hh_db_baseline.median, 1)} → ${fmt(z.hh_db_event.median, 1)}`), el("td", {}, fmt(z.delta_hh_db.median, 1)),
    el("td", {}, ha(z.areas_ha.new_water)), el("td", {}, ha(z.areas_ha.persistent_low_backscatter)), el("td", {}, ha(z.areas_ha.receded)), el("td", {}, ha(z.areas_ha.unknown))));
  box.append(el("table", { class: "metrics" },
    el("thead", {}, el("tr", {}, ...["Zone", "Observed", "HH median dB (before → after)", "ΔHH dB", "New water ha", "Persistent ha", "Receded ha", "Unknown ha"].map((t) => el("th", {}, t)))),
    el("tbody", {}, ...rows)));
  const t = r.threshold;
  const tests = (r.validation.held_out || []).map((v) => `${v.nisar_date} vs ${v.reference}: precision ${fmt(v.precision)}, recall ${fmt(v.recall)}, IoU ${fmt(v.iou)} (${v.reference_pixels} reference pixels)`);
  box.append(el("details", {}, el("summary", {}, "Method, calibration and validation"),
    el("p", { class: "note" }, `Water threshold HH < ${fmt(t.hh_db, 2)} dB, calibrated against OPERA DSWx-HLS open water on dry-date pairs `
      + `(${Object.entries(t.reference_dates).map(([d, x]) => `${d}↔${x.reference_date}`).join(", ")}; training F1 ${fmt(t.train_f1)}). New water also needs a drop of ${-r.params.delta_db} dB from the baseline; groups under ${r.params.mmu_pixels} pixels are not reported.`),
    tests.length ? el("ul", { class: "note" }, ...tests.map((x) => el("li", {}, x))) : el("p", { class: "warnline" }, "No held-out optical reference: accuracy not measured."),
    el("p", { class: "note" }, r.validation.note),
    el("ul", { class: "note" }, ...r.limits.map((x) => el("li", {}, x))),
    el("p", { class: "note" }, `Products: ${[...r.baseline, ev].map((b) => b.granule_id).join("; ")}. Evidence ${r.evidence_version}.`)));
  const dates = r.acquisitions.map((a) => a.date);
  const sel = el("select", { "aria-label": "Event acquisition" }, ...dates.map((d) => el("option", { value: d, selected: d === ev.date }, d)));
  box.append(el("div", { class: "row" }, el("label", {}, "Compare another acquisition ", sel),
    el("button", { class: "btn", type: "button", onclick: () => runNisar(rerender, sel.value) }, "Analyse this date")));
  return box;
}

/** NISAR water polygons (new + persistent) for the 3D "before" view. */
export function nisarWater() {
  const r = state.nisar && state.nisar.status === "ready" ? state.nisar.result : null;
  if (!r) return null;
  const features = r.features.filter((f) => f.properties.class === "new_water" || f.properties.class === "persistent_low_backscatter");
  return { date: r.event.date, features, source: "NISAR L2 GCOV", evidence_version: r.evidence_version };
}
