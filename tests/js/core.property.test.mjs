// fast-check properties for the DOM-free core embedded in index.html (<script id="raiz-core">).
// Run: node --test tests/js/core.property.test.mjs   (FAST_CHECK_MODULE may point at a local fast-check build)
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";

const fc = (await import(process.env.FAST_CHECK_MODULE || "fast-check")).default ?? (await import(process.env.FAST_CHECK_MODULE || "fast-check"));
const RUNS = Math.max(1, Math.round(Number(process.env.RAIZ_PBT_SCALE || "1") * 1));
const html = readFileSync(new URL("../../index.html", import.meta.url), "utf8");
const src = html.match(/<script id="raiz-core">([\s\S]*?)<\/script>/)[1];
const sandbox = { Number, Math, Date, Intl, JSON, Array, Object, Set, String };
vm.createContext(sandbox);
vm.runInContext(src, sandbox);
const C = sandbox.RaizCore;
const stats = {};
const run = (name, prop, numRuns) => {
  const n = numRuns * RUNS;
  fc.assert(prop, { numRuns: n, verbose: 1 });
  stats[name] = n;
};

const AR_EVENTS = ["start", "preview", "supported", "unsupported", "granted", "denied", "error", "target_found", "target_lost", "end", "stale_plan", "bogus"];

test("AR state machine: only declared states, active requires permission and registration", () => {
  run("ar_state_machine", fc.property(fc.array(fc.constantFrom(...AR_EVENTS), { maxLength: 60 }), (events) => {
    let s = "idle";
    let granted = false;
    for (const e of events) {
      const prev = s;
      s = C.arTransition(s, e);
      assert.ok(Object.hasOwn(C.AR_TRANSITIONS, s), `unknown state ${s}`);
      if (s === "capability_check") granted = false;
      if (prev === "permission_request" && s === "registering") granted = true;
      if (s === "active") assert.ok(granted, "active without a granted camera session");
      if (s === "active") assert.ok(prev === "registering" || prev === "tracking_lost" || prev === "active");
      if (prev === "preview") assert.ok(s === "preview" || s === "ended", "preview cannot become camera AR");
    }
  }), 5000);
});

test("Version guard accepts only the latest request for the current plan (model oracle)", () => {
  const op = fc.oneof(
    fc.record({ t: fc.constant("issue"), kind: fc.constantFrom("scene", "report"), plan: fc.constantFrom("p1", "p2", null) }),
    fc.record({ t: fc.constant("invalidate"), kind: fc.constantFrom("scene", "report") }),
    fc.record({ t: fc.constant("accept"), idx: fc.nat(30), current: fc.constantFrom("p1", "p2", null), resp: fc.constantFrom("p1", "p2", null, undefined) }),
  );
  run("version_guard", fc.property(fc.array(op, { maxLength: 40 }), (ops) => {
    const g = C.createVersionGuard();
    const tokens = [];
    const latest = {};
    for (const o of ops) {
      if (o.t === "issue") { const tok = g.issue(o.kind, o.plan); tokens.push(tok); latest[o.kind] = tok; }
      else if (o.t === "invalidate") { g.invalidate(o.kind); latest[o.kind] = null; }
      else if (tokens.length) {
        const tok = tokens[o.idx % tokens.length];
        const expected = latest[tok.kind] === tok && tok.planVersion === o.current &&
          (o.resp === undefined || o.resp === null || o.resp === o.current);
        assert.equal(g.accept(tok, o.current, o.resp), expected);
      }
    }
  }), 5000);
});

test("Dependents: plan-level changes always clear scene and report", () => {
  run("dependents", fc.property(fc.constantFrom("scenario", "dataset", "plan_inputs", "plan"), (c) => {
    const d = C.dependentsOf(c);
    assert.ok(d.includes("scene") && d.includes("report"));
  }), 200);
});

function validScene(nPlacements, fracs) {
  const sorted = [...fracs].sort((a, b) => a - b);
  return {
    plan_version: "p1", scene_version: "s1",
    frame: { target_aspect: 0.7067, meters_per_ar_unit: 2000, vertical_exaggeration: 50, origin_x_m: 0, origin_y_m: 0 },
    placements: Array.from({ length: nPlacements }, (_, i) => ({ x: ((i % 10) - 5) / 11, y: 0.1, asset_id: "broad_tree", reveal_rank: (i % 100) / 100 })),
    zones: [{ outline: [[0, 0], [0.1, 0], [0.1, 0.1]] }],
    deposition_points: [[0, 0]],
    stages: [0, 3, 6, 12].map((h, i) => ({ horizon_months: h, stage_label: C.STAGES[i], max_height_m: i * 0.5,
      visible_fraction_of_expected: i === 0 ? 0 : sorted[i - 1], caption: "ok" })),
    inference: { mode: "fixture" },
  };
}

test("validateScene accepts well-formed scenes", () => {
  run("scene_valid", fc.property(fc.nat(500), fc.array(fc.double({ min: 0, max: 1, noNaN: true }), { minLength: 3, maxLength: 3 }), (n, fr) => {
    // Compare lengths: arrays from the vm context have a different Array.prototype (strict deepEqual fails).
    const errs = C.validateScene(validScene(n, fr), "p1");
    assert.equal(errs.length, 0, Array.from(errs).join(" "));
  }), 2000);
});

test("validateScene rejects stale plans, out-of-target placements, unknown assets and plants at month 0", () => {
  const mutation = fc.constantFrom("stale", "outside", "nan", "asset", "month0", "order", "caption", "mode", "toomany", "outline");
  run("scene_mutations", fc.property(mutation, fc.double({ min: 0.51, max: 1e6, noNaN: true }), (m, big) => {
    const s = validScene(10, [0.2, 0.5, 1]);
    if (m === "stale") s.plan_version = "p0";
    if (m === "outside") s.placements[0].x = big;
    if (m === "nan") s.placements[0].y = NaN;
    if (m === "asset") s.placements[0].asset_id = "<script>";
    if (m === "month0") s.stages[0].visible_fraction_of_expected = 0.3;
    if (m === "order") s.stages.reverse();
    if (m === "caption") s.stages[1].caption = "<img src=x onerror=alert(1)>";
    if (m === "mode") s.inference.mode = "actual";
    if (m === "toomany") s.placements = Array(2001).fill(s.placements[0]);
    if (m === "outline") s.zones[0].outline = [[0, 0], [Infinity, 0], [0, 1]];
    assert.ok(C.validateScene(s, "p1").length > 0, m);
  }), 3000);
});

test("validateScene never throws on arbitrary input", () => {
  run("scene_fuzz", fc.property(fc.anything({ maxDepth: 4, withNullPrototype: true, withBigInt: true, withMap: true, withSet: true }), (x) => {
    const errs = C.validateScene(x, "p1");
    assert.ok(Array.isArray(errs) && errs.length > 0);
  }), 5000);
});

test("visiblePlacements is monotone in the visible fraction and empty at 0", () => {
  run("visible_monotone", fc.property(fc.array(fc.double({ min: 0, max: 1, noNaN: true }), { maxLength: 200 }), fc.double({ min: 0, max: 1, noNaN: true }), fc.double({ min: 0, max: 1, noNaN: true }), (ranks, a, b) => {
    const ps = ranks.map((r) => ({ reveal_rank: r }));
    const [lo, hi] = a <= b ? [a, b] : [b, a];
    const vlo = C.visiblePlacements(ps, { visible_fraction_of_expected: lo }).length;
    const vhi = C.visiblePlacements(ps, { visible_fraction_of_expected: hi }).length;
    assert.ok(vlo <= vhi);
    assert.equal(C.visiblePlacements(ps, { visible_fraction_of_expected: 0 }).length, 0);
  }), 3000);
});

test("Tabletop <-> metric round trip", () => {
  run("tabletop_round_trip", fc.property(fc.double({ min: -0.5, max: 0.5, noNaN: true }), fc.double({ min: -0.5, max: 0.5, noNaN: true }),
    fc.double({ min: 1, max: 1e5, noNaN: true }), fc.double({ min: -1e7, max: 1e7, noNaN: true }), fc.double({ min: -1e7, max: 1e7, noNaN: true }), (x, y, mpu, ox, oy) => {
      const f = { meters_per_ar_unit: mpu, origin_x_m: ox, origin_y_m: oy };
      const [mx, my] = C.tabletopToMetric(f, x, y);
      const [bx, by] = C.metricToTabletop(f, mx, my);
      assert.ok(Math.abs(bx - x) < 1e-6 && Math.abs(by - y) < 1e-6);
    }), 3000);
});

test("Formatting never throws and hides non-finite values", () => {
  run("formatting", fc.property(fc.oneof(fc.integer(), fc.double(), fc.constant(null), fc.constant(undefined)), (v) => {
    const s = C.formatPEN(v);
    if (v === null || v === undefined || !Number.isFinite(v)) assert.equal(s, "—");
    else assert.ok(s.startsWith("S/ "));
    assert.equal(typeof C.formatCount(v), "string");
  }), 3000);
});

test("Polling backoff is bounded and non-decreasing", () => {
  run("backoff", fc.property(fc.nat(1000), (n) => {
    const a = C.backoffDelay(n), b = C.backoffDelay(n + 1);
    assert.ok(a >= 500 && b <= 4000 && a <= b);
  }), 1000);
});

test("Job transitions mirror the backend contract", () => {
  const legal = { validating: ["queued", "failed"], queued: ["running", "cancelled", "failed"], running: ["ready", "partial", "failed", "cancelled", "queued"],
    failed: ["queued"], cancelled: ["queued"], partial: ["queued"], ready: ["queued"] };
  const states = Object.keys(legal);
  run("job_legal", fc.property(fc.constantFrom(...states), fc.constantFrom(...states), (a, b) => {
    assert.equal(C.jobLegal(a, b), legal[a].includes(b));
  }), 500);
});

// Angles built from positive increments (normalized below 2π): strictly increasing by construction.
const starRing = fc.integer({ min: 3, max: 14 }).chain((n) => fc.tuple(
  fc.array(fc.integer({ min: 1, max: 1000 }), { minLength: n + 1, maxLength: n + 1 }),
  fc.array(fc.double({ min: 0.5, max: 5, noNaN: true }), { minLength: n, maxLength: n })));

test("Star-shaped rings never self-intersect; a bow-tie always does", () => {
  run("ring_star", fc.property(starRing, ([steps, radii]) => {
    const total = steps.reduce((s, v) => s + v, 0);
    // The origin is in the polygon's kernel only if every angular gap (wrap included) is below π.
    // Minimized counterexamples [1,1,1,1,1,4] and [129,69,10,5,364,2,340] violated this; Shapely confirms
    // both rings self-intersect. The wrap gap is steps[0] + steps[n].
    const gaps = [...steps.slice(1, -1), steps[0] + steps[steps.length - 1]];
    fc.pre(Math.max(...gaps) * 2 < total);
    let acc = 0;
    const a = steps.slice(0, -1).map((v) => { acc += v; return (acc / total) * 2 * Math.PI; });
    const ring = C.closeRing(a.map((t, i) => [radii[i] * Math.cos(t), radii[i] * Math.sin(t)]));
    assert.equal(C.ringSelfIntersects(ring), false);
  }), 3000);
  run("ring_bowtie", fc.property(fc.double({ min: 0.1, max: 100, noNaN: true }), fc.double({ min: 0.1, max: 100, noNaN: true }), (w, h) => {
    assert.equal(C.ringSelfIntersects([[0, 0], [w, h], [w, 0], [0, h], [0, 0]]), true);
  }), 2000);
});

test("closeRing is idempotent and closes", () => {
  run("close_ring", fc.property(fc.array(fc.tuple(fc.double({ noNaN: true }), fc.double({ noNaN: true })), { minLength: 1, maxLength: 20 }), (pts) => {
    const r = C.closeRing(pts.map((p) => [p[0], p[1]]));
    assert.deepEqual(Array.from(r[0]), Array.from(r[r.length - 1]));
    assert.equal(C.closeRing(r).length, r.length);
  }), 2000);
});

test("Step gating: later steps open only with their prerequisites", () => {
  const arb = fc.record({ dataset: fc.option(fc.record({ sectors: fc.record({ features: fc.array(fc.constant({}), { maxLength: 3 }) }) }), { nil: null }),
    plan: fc.option(fc.record({ budget: fc.record({ allocations: fc.array(fc.record({ capsules: fc.nat(10) }), { maxLength: 3 }) }) }), { nil: null }) });
  run("step_gating", fc.property(arb, (s) => {
    const a = C.stepAvailability(s);
    const zones = !!(s.dataset && s.dataset.sectors.features.length);
    const funded = !!(s.plan && s.plan.budget.allocations.some((x) => x.capsules > 0));
    assert.equal(a.plan.open, zones); assert.equal(a.evidence.open, zones);
    assert.equal(a.future.open, funded); assert.equal(a.report.open, !!s.plan);
    for (const k of C.STEPS) if (!a[k].open) assert.ok(a[k].reason.length > 0, "closed step must say why");
    assert.ok(a.explore.open && a.zones.open && a.compare.open);
  }), 3000);
});

test("bracketDates returns the nearest acquisitions strictly around the event", () => {
  const day = fc.integer({ min: 0, max: 400 }).map((d) => new Date(Date.UTC(2026, 0, 1) + d * 864e5).toISOString().slice(0, 10));
  run("bracket_dates", fc.property(fc.uniqueArray(day, { maxLength: 40 }), day, (dates, ev) => {
    const { before, after } = C.bracketDates(dates, ev);
    const lower = dates.filter((d) => d < ev).sort(), upper = dates.filter((d) => d > ev).sort();
    assert.equal(before, lower.length ? lower[lower.length - 1] : null);
    assert.equal(after, upper.length ? upper[0] : null);
  }), 3000);
});

test("rainPeaks returns the wettest valid days in descending order", () => {
  run("rain_peaks", fc.property(fc.array(fc.record({ date: fc.string({ maxLength: 10 }), mm: fc.oneof(fc.double({ min: 0, max: 300, noNaN: true }), fc.constant(null)) }), { maxLength: 60 }), fc.nat(5), (days, n) => {
    const p = C.rainPeaks(days, n);
    assert.ok(p.length <= n && p.every((d) => Number.isFinite(d.mm)));
    for (let i = 1; i < p.length; i++) assert.ok(p[i - 1].mm >= p[i].mm);
    const valid = days.filter((d) => Number.isFinite(d.mm)).map((d) => d.mm).sort((a, b) => b - a);
    if (p.length) assert.equal(p[0].mm, valid[0]);
  }), 3000);
});

test("terrainHeightAt stays within the grid's height range", () => {
  run("terrain_height", fc.property(fc.integer({ min: 2, max: 8 }), fc.integer({ min: 2, max: 8 }), fc.double({ min: -0.6, max: 0.6, noNaN: true }), fc.double({ min: -0.6, max: 0.6, noNaN: true }), fc.integer({ min: 0, max: 1000 }), (nx, ny, x, y, seed) => {
    const heights = Array.from({ length: nx * ny }, (_, i) => ((i * 7919 + seed) % 500));
    const frame = { target_aspect: 0.7, meters_per_ar_unit: 2000, vertical_exaggeration: 50 };
    const h = C.terrainHeightAt({ nx, ny, heights_m: heights }, frame, x, y);
    const k = frame.vertical_exaggeration / frame.meters_per_ar_unit;
    assert.ok(h >= Math.min(...heights) * k - 1e-9 && h <= Math.max(...heights) * k + 1e-9);
  }), 3000);
});

test.after(() => console.log("fast-check runs per property:", JSON.stringify(stats)));
