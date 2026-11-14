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
    failed: ["queued"], cancelled: ["queued"], partial: ["queued"], ready: [] };
  const states = Object.keys(legal);
  run("job_legal", fc.property(fc.constantFrom(...states), fc.constantFrom(...states), (a, b) => {
    assert.equal(C.jobLegal(a, b), legal[a].includes(b));
  }), 500);
});

test.after(() => console.log("fast-check runs per property:", JSON.stringify(stats)));
