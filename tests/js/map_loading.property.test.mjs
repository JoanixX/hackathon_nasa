import { test } from "node:test";
import assert from "node:assert/strict";
const module = await import(process.env.FAST_CHECK_MODULE || "fast-check");
const fc = module.default ?? module;
globalThis.location = { origin: "http://local" };
globalThis.window = { matchMedia: () => ({ matches: false }) };
class MapStub {
  constructor(opts) { this.opts = opts; this.layers = new Map([["labels", { id: "labels", type: "symbol" }], ["building", { id: "building", type: "fill", "source-layer": "building" }]]); this.sources = new Map(); this.additions = 0; queueMicrotask(() => this.load()); }
  on(name, ...handlers) { if (name === "load") this.load = handlers.at(-1); }
  addControl() {}
  getStyle() { return { layers: [...this.layers.values()], sources: { osm: { type: "vector" } } }; }
  getSource(id) { return this.sources.get(id); }
  addSource(id, source) { assert.ok(!this.sources.has(id)); this.additions++; this.sources.set(id, { ...source, setData() {} }); }
  removeSource(id) { this.sources.delete(id); }
  addLayer(layer) { assert.ok(!this.layers.has(layer.id)); this.layers.set(layer.id, structuredClone(layer)); }
  getLayer(id) { return this.layers.get(id); }
  removeLayer(id) { this.layers.delete(id); }
  setPaintProperty(id, name, value) { const l = this.layers.get(id); l.paint ||= {}; l.paint[name] = value; }
  getPaintProperty(id, name) { return this.layers.get(id)?.paint?.[name]; }
  setLayoutProperty(id, name, value) { const l = this.layers.get(id); l.layout ||= {}; l.layout[name] = value; }
  getLayoutProperty(id, name) { return this.layers.get(id)?.layout?.[name]; }
  setTerrain(value) { this.terrain = value; }
  getContainer() { return { clientWidth: 1280, clientHeight: 800 }; }
  fitBounds(bounds, options) { this.fitOptions = options; }
  setLight() {} setSky() {} easeTo() {} getZoom() { return 14; }
}
globalThis.maplibregl = { Map: MapStub, NavigationControl: class {}, ScaleControl: class {} };
const M = await import("../../app/map.js");
const region = [-81.45, -6.4, -79.15, -3.35];

test("only explicit overlays create DEM; imagery sources stay bounded and opacity never reloads them", async () => {
  await fc.assert(fc.asyncProperty(fc.array(fc.tuple(fc.constantFrom("3d", "shade", "waterways", "nisar", "dswx"), fc.boolean()), { maxLength: 40 }), async actions => {
    const map = await M.initMap("map", { center: [-80.63, -5.19], zoom: 13, region });
    assert.equal(map.getSource("dem"), undefined);
    assert.deepEqual(map.opts.maxBounds, [[region[0], region[1]], [region[2], region[3]]]);
    let requestedDEM = false;
    for (const [key, on] of actions) {
      M.fitBounds(region, 60, on);
      assert.equal(map.fitOptions.duration, on ? 1200 : 0);
      if (key === "3d") M.setTerrain(on);
      else if (key === "shade") M.setHillshade(on);
      else if (key === "waterways") M.setVisibility(["rivers", "quebradas"], on);
      else {
        M.setImagery(key, on ? "2026-02-12" : null);
        if (on) {
          assert.deepEqual(map.getSource("img-" + key).bounds, region);
          const additions = map.additions;
          M.setImagery(key, "2026-02-12", .2);
          assert.equal(map.additions, additions);
          assert.equal(map.getLayer("img-" + key).paint["raster-opacity"], .2);
        } else assert.equal(map.getSource("img-" + key), undefined);
      }
      if ((key === "3d" || key === "shade") && on) requestedDEM = true;
      assert.equal(!!map.getSource("dem"), requestedDEM);
      if (map.getSource("dem")) assert.deepEqual(map.getSource("dem").bounds, region);
    }
    if (map.getLayer("buildings-3d")) assert.deepEqual(map.getLayer("buildings-3d").paint["fill-extrusion-color"], M.BUILDING_COLOR);
    M.setTerrain(false);
    for (const key of ["nisar", "dswx"]) M.setImagery(key, null);
  }), { numRuns: 1500, seed: 20261115, verbose: true });
});
