// fast-check properties for the shared growth + event timeline (app/timeline.js); pure clock functions only.
import { test } from "node:test";
import assert from "node:assert/strict";

const fcMod = await import(process.env.FAST_CHECK_MODULE || "fast-check");
const fc = fcMod.default ?? fcMod;
globalThis.window = globalThis.window || {};
const { createTimeline, growthAt, GROWTH_MONTHS } = await import(new URL("../../app/timeline.js", import.meta.url));
const SEED = 20261115;

const path = (n) => ({ type: "Feature", geometry: { type: "LineString", coordinates: Array.from({ length: n }, (_, i) => [-80.6 + i * 0.0003, -5.2 - i * 0.0002]) }, properties: {} });

test("growth is monotone, starts at seeding (0) and reaches the mature form (1)", () => {
  assert.equal(growthAt(0), 0);
  assert.ok(Math.abs(growthAt(GROWTH_MONTHS) - 1) < 1e-12);
  fc.assert(fc.property(fc.double({ min: -10, max: 100, noNaN: true }), fc.double({ min: -10, max: 100, noNaN: true }), (a, b) => {
    const [x, y] = a <= b ? [a, b] : [b, a];
    assert.ok(growthAt(x) <= growthAt(y) + 1e-12);
    assert.ok(growthAt(x) >= 0 && growthAt(y) <= 1 + 1e-12);
  }), { numRuns: 3000, seed: SEED });
});

test("timeline state is a pure function of time: event never before growth ends; same t gives same state", () => {
  fc.assert(fc.property(fc.integer({ min: 2, max: 80 }), fc.double({ min: 1, max: 30, noNaN: true }), fc.double({ min: 1, max: 30, noNaN: true }),
    fc.boolean(), fc.array(fc.double({ min: -5, max: 80, noNaN: true }), { minLength: 1, maxLength: 20 }), (n, gs, es, withTrees, times) => {
      const tl = createTimeline({ placements: [], speciesById: {}, path: path(n), zones: [], withTrees, growthSeconds: gs, eventSeconds: es });
      assert.ok(Math.abs(tl.total - (gs + es)) < 1e-9);
      let prev = null;
      for (const t of [...times].sort((a, b) => a - b)) {
        const s = tl.stateAt(t);
        assert.deepEqual(s, tl.stateAt(t));
        assert.ok(s.t >= 0 && s.t <= tl.total);
        if (s.t <= gs) assert.equal(s.eventProg, 0);
        assert.equal(s.growth === 0, !withTrees || s.months === 0);
        if (prev) { assert.ok(s.months >= prev.months); assert.ok(s.eventProg >= prev.eventProg); assert.ok(s.idx >= prev.idx); }
        assert.ok(s.idx <= s.stopAt);
        prev = s;
      }
      const end = tl.stateAt(tl.total);
      assert.equal(end.eventProg, 1);
      assert.equal(end.idx, end.stopAt);
    }), { numRuns: 1500, seed: SEED });
});

test("without a path the timeline is growth only", () => {
  const tl = createTimeline({ placements: [], speciesById: {}, path: null, withTrees: true, growthSeconds: 8, eventSeconds: 10 });
  assert.equal(tl.total, 8);
  assert.equal(tl.stateAt(100).eventProg, 0);
});
