// Zone drawing with a fixed vertex count (4–8, chosen before drawing) and vertex editing with terra-draw.
// Placing: each map click adds a vertex; the zone closes itself when the chosen count is reached.
// Editing: vertices can be dragged; vertices cannot be added or removed, so the count stays fixed.
const C = window.RaizCore;
export const MIN_VERTICES = 4, MAX_VERTICES = 8;
let draw = null, map = null;
let onChange = () => {};
let warn = () => {};
let placing = null; // {n, points, onDone}

export function initDraw(m, handlers) {
  map = m;
  onChange = handlers.onChange || onChange;
  warn = handlers.onWarn || warn;
  const TD = window.terraDraw;
  const AD = window.terraDrawMaplibreGlAdapter;
  if (!TD || !AD) throw new Error("The drawing library did not load (check the network).");
  const selectMode = new TD.TerraDrawSelectMode({
    flags: { polygon: { feature: { draggable: true, coordinates: { midpoints: false, draggable: true, deletable: false } } } },
    validation: (feature, ctx) => {
      if (ctx && ctx.updateType && ctx.updateType !== "provisional" && C.ringSelfIntersects(feature.geometry.coordinates[0])) {
        warn("That move would make edges cross. The vertex was not moved.");
        return { valid: false, reason: "Edges cross" };
      }
      return { valid: true };
    },
    styles: { selectedPolygonColor: "#e2a33b", selectedPolygonOutlineColor: "#1b6fa8", selectionPointColor: "#ffffff",
      selectionPointOutlineColor: "#1b6fa8", polygonFillColor: "#e2a33b", polygonFillOpacity: 0.25, polygonOutlineColor: "#b9791b", polygonOutlineWidth: 3 },
  });
  // Polygon mode is registered only so stored zones render with the right style; placing uses our handler.
  draw = new TD.TerraDraw({ adapter: new AD.TerraDrawMapLibreGLAdapter({ map, coordinatePrecision: 7 }),
    modes: [new TD.TerraDrawPolygonMode({ styles: { fillColor: "#e2a33b", fillOpacity: 0.25, outlineColor: "#b9791b", outlineWidth: 3 } }), selectMode] });
  draw.start();
  draw.setMode("select");
  draw.on("change", (_ids, type) => { if (type === "delete" || type === "update") onChange(polygons()); });
  map.on("click", onMapClick);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && placing) cancelPlacing("Drawing cancelled."); });
  return draw;
}

function draftData() {
  if (!placing) return { type: "FeatureCollection", features: [] };
  const pts = placing.points;
  const feats = pts.map((p, i) => ({ type: "Feature", geometry: { type: "Point", coordinates: p }, properties: { n: String(i + 1) } }));
  if (pts.length > 1) feats.push({ type: "Feature", geometry: { type: "LineString", coordinates: pts }, properties: {} });
  return { type: "FeatureCollection", features: feats };
}

function refreshDraft() { const s = map.getSource("draft"); if (s) s.setData(draftData()); }

/** Start placing a zone with exactly n vertices (4–8). Returns false if n is out of range. */
export function startPlacing(n, onProgress) {
  if (!Number.isInteger(n) || n < MIN_VERTICES || n > MAX_VERTICES) return false;
  placing = { n, points: [], onProgress: onProgress || (() => {}) };
  map.getCanvas().style.cursor = "crosshair";
  if (draw) draw.setMode("select");
  refreshDraft();
  placing.onProgress(0, n);
  return true;
}

export function cancelPlacing(msg) {
  placing = null;
  if (map) { map.getCanvas().style.cursor = ""; refreshDraft(); }
  if (msg) warn(msg);
}

export function isPlacing() { return !!placing; }

function onMapClick(e) {
  if (!placing) return;
  const p = [Number(e.lngLat.lng.toFixed(7)), Number(e.lngLat.lat.toFixed(7))];
  const pts = placing.points;
  // The new edge (last vertex -> p) may not cross any earlier, non-adjacent edge.
  if (pts.length >= 2) {
    const a = pts[pts.length - 1];
    for (let i = 0; i < pts.length - 2; i++) {
      if (crosses(pts[i], pts[i + 1], a, p)) { warn("That edge would cross another edge. Place the vertex elsewhere."); return; }
    }
  }
  // The closing vertex must also leave a simple ring.
  if (pts.length + 1 === placing.n && C.ringSelfIntersects(C.closeRing([...pts, p]))) {
    warn("Closing here would make edges cross. Place the last vertex elsewhere.");
    return;
  }
  pts.push(p);
  refreshDraft();
  placing.onProgress(pts.length, placing.n);
  if (pts.length === placing.n) {
    const ring = C.closeRing(pts);
    if (C.ringSelfIntersects(ring)) { warn("The zone's edges cross. Start again and place the vertices around the area."); cancelPlacing(); return; }
    const done = placing;
    cancelPlacing();
    draw.addFeatures([{ type: "Feature", geometry: { type: "Polygon", coordinates: [ring] }, properties: { mode: "polygon" } }]);
    onChange(polygons());
    done.onProgress(done.n, done.n, true);
  }
}

function crosses(a, b, c, d) {
  const o = (p, q, r) => Math.sign((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0]));
  return o(a, b, c) !== o(a, b, d) && o(c, d, a) !== o(c, d, b);
}

export function setMode(mode) { if (draw && mode === "select") draw.setMode("select"); }

export function polygons() {
  if (!draw) return [];
  return draw.getSnapshot().filter((f) => f.geometry.type === "Polygon" && f.geometry.coordinates[0].length >= 4)
    .map((f) => ({ id: f.id, geometry: { type: "Polygon", coordinates: f.geometry.coordinates } }));
}

export function remove(id) { if (draw) draw.removeFeatures([id]); onChange(polygons()); }

export function clear() { cancelPlacing(); if (draw) draw.clear(); onChange(polygons()); }

/** Replace one zone's geometry (only when the user accepts a proposal, which already has 4–8 vertices). */
export function replaceGeometry(id, geometry) {
  if (!draw) return null;
  draw.removeFeatures([id]);
  const ring = C.closeRing(geometry.coordinates[0].map((p) => [Number(p[0].toFixed(7)), Number(p[1].toFixed(7))]));
  const res = draw.addFeatures([{ type: "Feature", geometry: { type: "Polygon", coordinates: [ring] }, properties: { mode: "polygon" } }]);
  onChange(polygons());
  const ok = Array.isArray(res) ? res.find((r) => r.valid !== false) : null;
  return ok ? ok.id : null;
}

/** Programmatic placement (keyboard users and tests): vertices in lon/lat, same rules as clicking. */
export function placeVertices(points) {
  if (!placing) return false;
  for (const p of points) onMapClick({ lngLat: { lng: p[0], lat: p[1] } });
  return true;
}
