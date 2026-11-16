import { test } from "node:test";
import assert from "node:assert/strict";
import { createLoadScope } from "../../app/loading.js";
const module = await import(process.env.FAST_CHECK_MODULE || "fast-check");
const fc = module.default ?? module;
const seed = 20261115;

test("out-of-order completions cannot cross an input invalidation, even when abort is ignored", async () => {
  await fc.assert(fc.asyncProperty(fc.array(fc.array(fc.string({ maxLength: 8 }), { minLength: 1, maxLength: 12 }), { minLength: 1, maxLength: 8 }), async batches => {
    const scope = createLoadScope(), applied = [], requests = [], promises = [];
    for (let epoch = 0; epoch < batches.length; epoch++) {
      if (epoch) scope.reset();
      for (const key of batches[epoch]) promises.push(scope.run(key, signal => new Promise(resolve => requests.push({ resolve, epoch, key, signal })), value => applied.push(value)));
      await Promise.resolve();
    }
    // Complete newest first, then obsolete requests. Abort cannot be trusted to stop all work.
    for (const r of requests.slice().reverse()) r.resolve({ epoch: r.epoch, key: r.key });
    await Promise.all(promises);
    const expected = new Set(batches.at(-1));
    assert.equal(applied.length, expected.size);
    assert.deepEqual(new Set(applied.map(v => v.key)), expected);
    assert.ok(applied.every(v => v.epoch === batches.length - 1));
    assert.ok(requests.filter(r => r.epoch < batches.length - 1).every(r => r.signal.aborted));
  }), { numRuns: 3000, seed, verbose: true });
});

test("deduplicated loads recover from rejection and new loads survive old finalizers", async () => {
  await fc.assert(fc.asyncProperty(fc.string({ maxLength: 30 }), async key => {
    const scope = createLoadScope(); let firstDone, secondDone, calls = 0;
    const first = scope.run(key, () => new Promise(r => { firstDone = r; }), () => assert.fail("stale apply"));
    await Promise.resolve(); scope.reset();
    const work = () => { calls++; return new Promise(r => { secondDone = r; }); };
    const current = scope.run(key, work, () => {});
    await Promise.resolve(); firstDone(1); await first;
    assert.equal(scope.run(key, work, () => {}), current);
    secondDone(2); assert.equal(await current, 2); assert.equal(calls, 1);
    await assert.rejects(scope.run(key, () => Promise.reject(new Error("offline")), () => {}), /offline/);
    assert.equal(await scope.run(key, () => 3, () => {}), 3);
  }), { numRuns: 2000, seed, verbose: true });
});
