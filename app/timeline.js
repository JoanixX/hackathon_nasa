// One timeline for the 3D views (NV-02): plantation age (months) then the huayco arriving along the accepted ravine.
// Every frame is a pure function of the timeline time t (seconds): pause, scrub, restart and export reproduce it exactly.
// The growth curve is ILLUSTRATIVE (logistic, mature form at about 5 years); it is not a measured growth model.
import * as T from "./twin.js";

export const GROWTH_MONTHS = 60;
const MID_MONTH = 24, WIDTH = 7;
const L = (m) => 1 / (1 + Math.exp(-(m - MID_MONTH) / WIDTH));

/** Fraction of the mature form at plantation age `months` (0 at seeding, 1 at GROWTH_MONTHS). Illustrative. */
export function growthAt(months) {
  const m = Math.max(0, Math.min(GROWTH_MONTHS, months));
  return (L(m) - L(0)) / (L(GROWTH_MONTHS) - L(0));
}

const M_PER_DEG_LAT = 111320;
function circle(lon, lat, rM, n = 10) {
  const k = 1 / (M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180));
  const ring = [];
  for (let i = 0; i <= n; i++) { const a = (i / n) * 2 * Math.PI; ring.push([lon + Math.cos(a) * rM * k, lat + (Math.sin(a) * rM) / M_PER_DEG_LAT]); }
  return { type: "Polygon", coordinates: [ring] };
}

/**
 * Build a timeline. `withTrees` decides whether the planted trees exist (intervention) — the clock, terrain path and
 * camera are the same in both cases so the two views are comparable.
 */
export function createTimeline({ placements, speciesById, path, zones = [], withTrees, growthSeconds = 10, eventSeconds = 10, eventAfterMonths = GROWTH_MONTHS }) {
  const coords = path ? path.geometry.coordinates : [];
  const flood = !!(path && path.properties && path.properties.kind === "flood"); // river flood vs. ravine debris flow
  const body = flood ? T.COLORS.water : T.COLORS.mud, edge = flood ? "#1c5aa6" : T.COLORS.mudEdge;
  const inside = coords.map((c) => withTrees && zones.some((z) => T.pointInPolygon(c, z.geometry)));
  const hit = inside.indexOf(true);
  const stopAt = withTrees && hit >= 0 ? Math.min(coords.length - 1, hit + T.ASSUMED_STOP_CELLS) : coords.length - 1;
  const cells = coords.map((c, i) => circle(c[0], c[1], (18 + 50 * i / Math.max(1, coords.length - 1)) * (inside[i] ? 0.5 : 1)));
  const total = growthSeconds + (coords.length > 1 ? eventSeconds : 0);
  let lastKey = null;

  function stateAt(t) {
    const tt = Math.max(0, Math.min(total, t));
    const months = Math.min(eventAfterMonths, (tt / growthSeconds) * eventAfterMonths);
    // At the end of the timeline the event is complete (no floating-point shortfall: (gs + es - gs) / es can be < 1).
    const eventProg = coords.length > 1 ? (tt >= total ? 1 : Math.max(0, Math.min(1, (tt - growthSeconds) / eventSeconds))) : 0;
    const idx = eventProg > 0 ? Math.max(1, Math.round(eventProg * stopAt)) : -1;
    const shown = Math.round(months * 10) / 10; // the label and the drawn trees use the same age
    return { t: tt, months: shown, growth: withTrees ? growthAt(shown) : 0, eventProg, idx, stopAt, hit, total };
  }

  /** Draw the state at time t (skips work when nothing visible changed). Returns the state. */
  function renderAt(t) {
    const s = stateAt(t);
    const key = `${Math.round(s.growth * 200)}|${s.idx}|${s.eventProg >= 1}`;
    if (key === lastKey) return s;
    lastKey = key;
    T.setTrees(withTrees && s.growth > 0.01 ? T.treeFeatures(placements, speciesById, s.growth) : null);
    const feats = [];
    if (s.idx >= 0) {
      for (let i = 0; i <= s.idx; i += Math.max(1, Math.ceil((s.idx + 1) / 120))) {
        const front = i > s.idx - 6;
        feats.push({ type: "Feature", geometry: cells[i], properties: { color: front ? edge : body, h: flood ? (front ? 2 : 1.2) : (front ? 4 : 2.5) } });
      }
      if (!withTrees && s.eventProg >= 1) {
        const end = coords[coords.length - 1];
        feats.push({ type: "Feature", geometry: circle(end[0], end[1], 260, 24), properties: { color: body, h: flood ? 0.8 : 1.5 } });
      }
    }
    T.setMud({ type: "FeatureCollection", features: feats });
    return s;
  }

  // Playback clock (real time x speed); the frame shown is always renderAt(t).
  let t = 0, speed = 1, playing = false, raf = null, last = 0, onTick = null;
  const loop = (now) => {
    if (!playing) return;
    t = Math.min(total, t + ((now - last) / 1000) * speed);
    last = now;
    const s = renderAt(t);
    if (onTick) onTick(s);
    if (t >= total) { playing = false; raf = null; return; }
    raf = requestAnimationFrame(loop);
  };
  return {
    total, stateAt, renderAt,
    get time() { return t; }, get playing() { return playing; }, get speed() { return speed; },
    onTick(fn) { onTick = fn; },
    play() { if (playing) return; if (t >= total) t = 0; playing = true; last = performance.now(); raf = requestAnimationFrame(loop); },
    pause() { playing = false; if (raf) cancelAnimationFrame(raf); raf = null; },
    seek(x) { t = Math.max(0, Math.min(total, x)); const s = renderAt(t); if (onTick) onTick(s); return s; },
    setSpeed(x) { speed = Math.max(0.25, Math.min(4, x)); },
    restart() { this.pause(); this.seek(0); this.play(); },
    dispose() { this.pause(); onTick = null; lastKey = null; },
    path, withTrees, flood,
  };
}
