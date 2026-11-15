// Single source of truth for the interface. Panels read it; actions update it and call render().
const C = window.RaizCore;

export const state = {
  step: "explore",
  health: null,
  scenarios: [],
  scenarioId: null,
  scenario: null,          // {summary, sectors, species} from the API
  imagery: { hls: null, nisar: null, rtc: null, imerg: null },  // active date per layer (null = off)
  dates: {},               // layer -> list of available dates
  coverage: {},            // date -> share of valid pixels around the focus point
  acquisitions: null,      // ASF catalog timeline for the current area
  drawn: [],               // [{id, geometry, name, role, original_geometry, refinement}]
  suggestion: null,        // {zoneId, ...proposal}
  dataset: null,           // confirmed zones dataset (user-drawn, imported or demo)
  datasetKind: null,       // "user" | "import" | "demo"
  plan: null,
  scene: null,
  sceneJob: null,
  report: null,
  rain: null,
  compare: { before: null, after: null, blend: 1, which: "after" },
  futureStage: 3,
  terrain3d: false,
};

const subs = [];
export function subscribe(fn) { subs.push(fn); }
export function update(patch) { Object.assign(state, patch); subs.forEach((f) => f(state)); }

/** Clear everything that depended on the changed input (versioned consistency across views). */
export function invalidate(change) {
  const patch = {};
  for (const d of C.dependentsOf(change)) {
    if (d === "plan") patch.plan = null;
    if (d === "scene") { patch.scene = null; patch.sceneJob = null; }
    if (d === "report") patch.report = null;
    if (d === "dataset") { patch.dataset = null; patch.datasetKind = null; }
  }
  Object.assign(state, patch);
}

export function region() {
  return state.scenario ? state.scenario.summary.region_bbox : null;
}

/** Area of interest for catalog and rain queries: confirmed zones, else drawn zones, else the locator. */
export function focusBox() {
  const feats = state.dataset ? state.dataset.sectors.features : state.drawn.map((d) => ({ geometry: d.geometry }));
  let w = 180, s = 90, e = -180, n = -90;
  const walk = (c) => { if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); } else c.forEach(walk); };
  feats.forEach((f) => walk(f.geometry.coordinates));
  if (w > e && state.scenario) {
    const { locator_lon: lon, locator_lat: lat } = state.scenario.summary;
    return [lon - 0.1, lat - 0.1, lon + 0.1, lat + 0.1];
  }
  const pad = 0.02;
  return [w - pad, s - pad, e + pad, n + pad];
}

export function focusPoint() {
  const b = focusBox();
  return b ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : null;
}
