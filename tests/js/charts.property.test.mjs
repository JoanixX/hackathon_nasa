import { test } from "node:test";
import assert from "node:assert/strict";
const module = await import(process.env.FAST_CHECK_MODULE || "fast-check");
const fc = module.default ?? module;
const live = new Set();
globalThis.Chart = class { constructor() { live.add(this); } destroy() { live.delete(this); } };
globalThis.window = { Chart, matchMedia: () => ({ matches: true }) };
const Ch = await import("../../app/charts.js");
test("chart replacement and panel cleanup cannot retain discarded canvases", async () => {
  await fc.assert(fc.asyncProperty(fc.array(fc.tuple(fc.integer({ min: 0, max: 100000 }), fc.boolean()), { minLength: 1, maxLength: 30 }), async actions => {
    const canvas = { isConnected: true };
    for (const [n, detached] of actions) {
      canvas.isConnected = !detached;
      Ch.destroyAll();
      await Ch.planChart(canvas, { seeds_released:n, expected_germinated:n/2, expected_established:n/4 });
      assert.equal(live.size, detached ? 0 : 1);
      if (!detached) { await Ch.planChart(canvas, { seeds_released:n, expected_germinated:0, expected_established:0 }); assert.equal(live.size, 1); }
    }
    Ch.destroyAll(); assert.equal(live.size, 0);
  }), { numRuns: 1000, seed: 20261115, verbose: true });
});
