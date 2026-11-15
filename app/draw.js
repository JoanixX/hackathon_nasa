// Zone drawing and vertex editing with terra-draw. Geometry is validated again by the server.
const C = window.RaizCore;
let draw = null;
let onChange = () => {};
let warn = () => {};

export function initDraw(map, handlers) {
  onChange = handlers.onChange || onChange;
  warn = handlers.onWarn || warn;
  const TD = window.terraDraw;
  const AD = window.terraDrawMaplibreGlAdapter;
  if (!TD || !AD) throw new Error("The drawing library did not load (check the network).");
  const notSelfIntersecting = (feature) => {
    const ring = feature.geometry.coordinates[0];
    if (TD.ValidateNotSelfIntersecting) return TD.ValidateNotSelfIntersecting(feature);
    return C.ringSelfIntersects(ring) ? { valid: false, reason: "Edges cross" } : { valid: true };
  };
  const polygonMode = new TD.TerraDrawPolygonMode({
    validation: (feature, ctx) => {
      if (ctx && (ctx.updateType === "finish" || ctx.updateType === "commit")) {
        const r = notSelfIntersecting(feature);
        const ok = r === true || (r && r.valid);
        if (!ok) warn("That edge would cross another edge. Place the vertex elsewhere.");
        return typeof r === "boolean" ? { valid: r } : r;
      }
      return { valid: true };
    },
    styles: { fillColor: "#e2a33b", fillOpacity: 0.2, outlineColor: "#b9791b", outlineWidth: 2, closingPointColor: "#1d2428", closingPointWidth: 5 },
  });
  const selectMode = new TD.TerraDrawSelectMode({
    flags: { polygon: { feature: { draggable: true, coordinates: { midpoints: true, draggable: true, deletable: true } } } },
    styles: { selectedPolygonColor: "#e2a33b", selectedPolygonOutlineColor: "#1b6fa8", selectionPointColor: "#ffffff",
      selectionPointOutlineColor: "#1b6fa8", midPointColor: "#1b6fa8" },
  });
  draw = new TD.TerraDraw({ adapter: new AD.TerraDrawMapLibreGLAdapter({ map, coordinatePrecision: 7 }), modes: [polygonMode, selectMode] });
  draw.start();
  draw.setMode("select");
  draw.on("finish", () => onChange(polygons()));
  draw.on("change", (_ids, type) => { if (type === "delete" || type === "update") onChange(polygons()); });
  return draw;
}

export function setMode(mode) { if (draw) draw.setMode(mode); }

export function polygons() {
  if (!draw) return [];
  return draw.getSnapshot().filter((f) => f.geometry.type === "Polygon" && f.geometry.coordinates[0].length >= 4)
    .map((f) => ({ id: f.id, geometry: { type: "Polygon", coordinates: f.geometry.coordinates } }));
}

export function remove(id) { if (draw) draw.removeFeatures([id]); onChange(polygons()); }

export function clear() { if (draw) draw.clear(); onChange(polygons()); }

/** Replace one drawn polygon's geometry (used only when the user accepts a suggestion). */
export function replaceGeometry(id, geometry) {
  if (!draw) return null;
  draw.removeFeatures([id]);
  const ring = C.closeRing(geometry.coordinates[0].map((p) => [Number(p[0].toFixed(7)), Number(p[1].toFixed(7))]));
  const res = draw.addFeatures([{ type: "Feature", geometry: { type: "Polygon", coordinates: [ring] }, properties: { mode: "polygon" } }]);
  onChange(polygons());
  const ok = Array.isArray(res) ? res.find((r) => r.valid !== false) : null;
  return ok ? ok.id : null;
}

export function load(features) {
  if (!draw) return;
  draw.clear();
  draw.addFeatures(features.map((g) => ({ type: "Feature", geometry: g, properties: { mode: "polygon" } })));
  onChange(polygons());
}
