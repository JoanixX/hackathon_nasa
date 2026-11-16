import { test } from "node:test";
import assert from "node:assert/strict";
const module = await import(process.env.FAST_CHECK_MODULE || "fast-check");
const fc = module.default ?? module;
let now = 0, sequence = 0, callbacks = new Map();
Object.defineProperty(globalThis, "performance", { value: { now: () => now }, configurable: true });
globalThis.requestAnimationFrame = fn => { const id = ++sequence; callbacks.set(id, fn); return id; };
globalThis.cancelAnimationFrame = id => callbacks.delete(id);
const T = await import("../../app/twin.js");
const sources = new Map(); let writes = 0;
const map = { getSource: id => sources.get(id), addSource: id => sources.set(id, { setData(value) { writes++; this.data = value; } }), addLayer() {} };
T.initTwin(map);

test("flow playback is bounded, reaches the endpoint and cancellation always settles", async () => {
  await fc.assert(fc.asyncProperty(fc.integer({min:2,max:100}), fc.integer({min:60,max:160}), fc.boolean(), async (n, hz, cancel) => {
    now = 0; writes = 0; callbacks.clear();
    const coords = Array.from({ length: n }, (_, i) => [-80.63 + i * .0001, -5.19 + i * .0001]);
    const promise = T.playHuayco({ path: { type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} }, zones: [], withTrees: false, seconds: .5 });
    if (cancel) T.stop();
    else for (let i = 0; callbacks.size && i < 200; i++) { now += 1000/hz; const batch = [...callbacks.values()]; callbacks.clear(); batch.forEach(fn => fn(now)); }
    assert.equal(callbacks.size, 0);
    assert.equal((await promise).cancelled, cancel);
    assert.ok(writes <= 15, "more GeoJSON updates than the 24 fps budget");
    if (!cancel) {
      const fan = sources.get("twin-mud").data.features.at(-1);
      const ring = fan.geometry.coordinates[0];
      const xs = ring.slice(0,-1).map(p=>p[0]), ys = ring.slice(0,-1).map(p=>p[1]);
      assert.ok(Math.abs((Math.max(...xs)+Math.min(...xs))/2 - coords.at(-1)[0]) < 1e-7);
      assert.ok(Math.abs((Math.max(...ys)+Math.min(...ys))/2 - coords.at(-1)[1]) < 1e-7);
      assert.ok(sources.get("twin-mud").data.features.length <= 122);
    }
    T.clearAll();
  }), { numRuns: 1500, seed: 20261115, verbose: true });
});

test("a newer flow resolves the old playback instead of stranding a recording", async () => {
  const path = { geometry: { coordinates: [[-80.6,-5.2],[-80.59,-5.19]] } };
  const first = T.playHuayco({ path, zones: [], withTrees: false });
  const next = T.playHuayco({ path, zones: [], withTrees: false });
  assert.equal((await first).cancelled, true);
  T.clearAll(); assert.equal((await next).cancelled, true);
  assert.throws(() => T.playHuayco({ path: { geometry: { coordinates: [[0,0]] } }, zones: [], withTrees: false }), /two path points/);
});

test("recording always releases capture tracks after success and failure", async () => {
  await fc.assert(fc.asyncProperty(fc.constantFrom("success", "run_error", "constructor_error", "unsupported", "empty"), async mode => {
    let streams = 0, stopped = 0;
    const captureStream = () => { streams++; return { getTracks: () => [{ stop() { stopped++; } }] }; };
    map.getCanvas = () => ({ width: 100, height: 100, captureStream });
    globalThis.document = { createElement: () => ({ captureStream, getContext: () => ({ drawImage() {}, fillRect() {}, fillText() {}, getImageData() { return { data: new Uint8Array(4) }; } }) }) };
    let render; map.on = (_name, fn) => { render = fn; }; map.off = () => { render = null; }; map.triggerRepaint = () => render?.();
    globalThis.MediaRecorder = class {
      static isTypeSupported() { return mode !== "unsupported"; }
      constructor() { if (mode === "constructor_error") throw new Error("constructor error"); this.state = "inactive"; }
      start() { this.state = "recording"; }
      stop() { this.state = "inactive"; queueMicrotask(() => { this.ondataavailable?.({ data: new Blob(mode === "empty" ? [] : ["encoded frame"]) }); this.onstop?.(); }); }
    };
    const action = () => T.recordVideo(async () => { if (mode === "run_error") throw new Error("view error"); });
    if (mode === "success") URL.revokeObjectURL(await action());
    else await assert.rejects(action());
    assert.equal(stopped, streams);
    assert.equal(streams, mode === "unsupported" ? 0 : 1);
  }), { numRuns: 1000, seed: 20261115, verbose: true });
});
