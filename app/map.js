// MapLibre map: OpenFreeMap basemap, GIBS imagery, Copernicus DEM terrain, zones and results.
import { initTwin, COLORS } from "./twin.js";
const BASEMAP = "https://tiles.openfreemap.org/styles/liberty";
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const GIBS_ATTR = '<a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noopener">NASA GIBS</a>';
const DEM_ATTR = "Terrain: Copernicus DEM GLO-30 © DLR, © Airbus, provided under COPERNICUS by the EU and ESA";

export const LAYER_INFO = {
  hls: { title: "Optical context (HLS, 30 m)", gibs: "HLS_S30_Nadir_BRDF_Adjusted_Reflectance", tms: "GoogleMapsCompatible_Level12", ext: "png", maxzoom: 12,
    cls: "observed", src: "NASA HLS Sentinel-2 surface reflectance, true-colour rendering via GIBS", explain: "Harmonized Landsat Sentinel-2 true colour. Shown at its native 30 m; zooming further only enlarges pixels. Clouds are not removed." },
  nisar: { title: "NISAR radar (GCOV)", gibs: "NISAR_L2_Geocoded_Polarimetric_Covariance", tms: "GoogleMapsCompatible_Level13", ext: "png", maxzoom: 13,
    cls: "observed", src: "NISAR L2 GCOV normalized backscatter, false-colour rendering via GIBS", explain: "L-band radar backscatter from NISAR. Bright means a rough or vegetated surface or structures; dark means smooth surfaces such as calm water or flat bare soil. It is not a moisture or depth measurement." },
  rtc: { title: "Sentinel-1 radar (OPERA RTC)", gibs: "OPERA_L2_Radiometric_Terrain_Corrected_SAR_Sentinel-1", tms: "GoogleMapsCompatible_Level12", ext: "png", maxzoom: 12,
    cls: "observed", src: "OPERA RTC-S1 (C-band), rendering via GIBS", explain: "Terrain-corrected C-band radar from Sentinel-1. Complementary context; check actual acquisition dates and coverage separately from NISAR." },
  dswx: { title: "Surface water and ponding (OPERA DSWx-HLS)", gibs: "OPERA_L3_Dynamic_Surface_Water_Extent-HLS", tms: "GoogleMapsCompatible_Level12", ext: "png", maxzoom: 12,
    cls: "derived", src: "OPERA L3 DSWx-HLS (NASA JPL) via GIBS; 30 m", explain: "Open water (dark blue) and partial surface water such as ponding (light blue) classified from Landsat/Sentinel-2. Faint grey marks cloud: unknown, not dry." },
  imerg: { title: "Rain rate (GPM IMERG)", gibs: "IMERG_Precipitation_Rate", tms: "GoogleMapsCompatible_Level6", ext: "png", maxzoom: 6,
    cls: "derived", src: "GPM IMERG daily precipitation rate via GIBS (about 10 km)", explain: "Satellite precipitation estimate on a 0.1° grid. Use it to see when and roughly where it rained, not which street flooded." },
};

let map, terrainOn = false;
const listeners = {};

export function on(evt, fn) { (listeners[evt] = listeners[evt] || []).push(fn); }
function emit(evt, data) { (listeners[evt] || []).forEach((f) => f(data)); }

export function getMap() { return map; }

let regionBounds = null;
let coverageBounds = null;
let imagesVisible = true;

export function setImageVisibility(on) {
  imagesVisible=!!on;
  for(const id of Object.keys(LAYER_INFO)) if(map?.getLayer(`img-${id}`))map.setLayoutProperty(`img-${id}`,"visibility",on?"visible":"none");
}

export function setWorkWindow(bounds) {
  if(!bounds||!map)return;
  regionBounds=bounds;
  applyWorkConstraint();
  // DEM source bounds are immutable; replace it when changing the working locality.
  if(map.getSource("dem")) {
    const wasTerrain=terrainOn;
    map.setTerrain(null);
    for(const id of ["hillshade","relief-tint"])if(map.getLayer(id))map.removeLayer(id);
    map.removeSource("dem");ensureDEM();
    if(wasTerrain)map.setTerrain({source:"dem",exaggeration});
    setHillshade(wasTerrain);
  }
}

export function initMap(container, view) {
  terrainOn = false; exaggeration = 1; materialPaint = []; activeImagery.clear();
  regionBounds = view.region || null;
  coverageBounds = view.coverage || regionBounds;
  map = new maplibregl.Map({
    container, style: BASEMAP, center: view.center, zoom: view.zoom, pitch: 0, maxPitch: 75, fadeDuration: 0,
    // Constrain the camera centre, without forcing the viewport/terrain camera into a tiny rectangle.
    minZoom: 13, maxZoom: 18,
    maxTileCacheSize: 128, maxTileCacheZoomLevels: 3,
    attributionControl: { compact: false, customAttribution: `${GIBS_ATTR} · ${DEM_ATTR}` },
  });
  applyWorkConstraint();
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.on("error", (e) => emit("error", e && e.error ? e.error.message || String(e.error) : "Map error"));
  map.on("sourcedata",e=>{if(e.sourceId==="dem")syncTerrainAnchor();});
  map.on("moveend",syncTerrainAnchor);
  // Controls need the parsed style, not every remote glyph/vector tile. Tile readiness is separate.
  return new Promise((resolve) => map.on("style.load", () => { setupBase(); resolve(map); }));
}

export function terrainAnchorNeedsSync(current,sample) {
  return Number.isFinite(sample)&&Number.isFinite(current)&&(sample!==0||current<=0)&&Math.abs(sample-current)>.25;
}
export function constrainView(center,zoom,bounds) {
  if(!center.every(Number.isFinite)||!Number.isFinite(zoom))throw new RangeError("A finite camera is required.");
  const [w,s,e,n]=bounds;
  return {center:[Math.max(w,Math.min(e,center[0])),Math.max(s,Math.min(n,center[1]))],zoom:Math.max(13,Math.min(18,zoom))};
}
function applyWorkConstraint() {
  if(!regionBounds)return;
  map.setTransformConstrain((center,zoom)=>{
    const v=constrainView([center.lng,center.lat],zoom??13,regionBounds);
    return {center:new maplibregl.LngLat(...v.center),zoom:v.zoom};
  });
}
function syncTerrainAnchor() {
  if(!terrainOn||!map.isSourceLoaded?.("dem")||map.isMoving?.())return;
  const sample=map.queryTerrainElevation(map.getCenter());
  if(terrainAnchorNeedsSync(map.getCenterElevation(),sample))map.setCenterElevation(sample);
}

function firstSymbolId() {
  const l = map.getStyle().layers.find((x) => x.type === "symbol");
  return l ? l.id : undefined;
}

function ensureDEM() {
  if (map.getSource("dem")) return;
  map.addSource("dem", { type: "raster-dem", tiles: [`${location.origin}/api/terrain/{z}/{x}/{y}.png`], tileSize: 256,
    encoding: "terrarium", minzoom: 7, maxzoom: 12, attribution: "", ...(regionBounds ? { bounds: regionBounds } : {}) });
  // Coarsen toward the horizon instead of filling it with close-view tiles.
  map.setSourceTileLodParams?.(5, 2, "dem");
  // DEM tint/shading go BELOW mapped land cover, water, roads and labels. Height is not a land-cover class.
  const before = map.getStyle().layers.find(l => l.type !== "background")?.id;
  try { map.addLayer({ id: "relief-tint", type: "color-relief", source: "dem", layout: { visibility: "none" },
    paint: { "color-relief-opacity": 0.55, "color-relief-color": ["interpolate", ["linear"], ["elevation"],
      0, "rgba(0,0,0,0)", 60, "rgba(222,196,150,0.0)", 120, "#d9b98a", 300, "#b8875a", 700, "#8c5a32", 1500, "#6b4423", 3000, "#4a2e17"] } },
    before); } catch (e) { emit("error", "Relief tint unavailable in this map version: " + e.message); }
  map.addLayer({ id: "hillshade", type: "hillshade", source: "dem", layout: { visibility: "none" },
    paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "#5a3a1e", "hillshade-highlight-color": "#ffffff", "hillshade-illumination-direction": 315 } },
    before);
}

export function setHillshade(on) {
  if (on) ensureDEM();
  if (map.getLayer("hillshade")) map.setLayoutProperty("hillshade", "visibility", on ? "visible" : "none");
  if (map.getLayer("relief-tint")) map.setLayoutProperty("relief-tint", "visibility", on ? "visible" : "none");
}

export function setVisibility(ids, on) {
  for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
}

// Measured/mapped height when present; buildings without height (most ML footprints) get a neutral colour.
export const BUILDING_HEIGHT = ["coalesce", ["get", "height"], ["*", ["get", "num_floors"], 3], 3];
export const BUILDING_COLOR = ["case", ["any", ["has", "height"], ["has", "num_floors"]],
  ["interpolate", ["linear"], BUILDING_HEIGHT, 0, "#dfc8a6", 20, "#c39a92", 60, "#8daac1"], "#d6cbbb"];

/** Legible, shared 2D/3D palette (the base style's pale parks and white roads were not distinguishable). */
export const PALETTE = {
  park: "#6fb85c", grass: "#8fcf6f", wood: "#3f8f3a", sand: "#ead7a0", water: "#4f9be8",
  motorway: "#e8743b", trunk: "#f29e38", secondary: "#f5cf45", street: "#ffffff", streetCasing: "#8e8e8e",
  service: "#efe9df", path: "#b5652f", majorCasing: "#9c4f1f",
};

function styleBaseColors() {
  const P = PALETTE;
  const set = (id, prop, v) => { try { map.setPaintProperty(id, prop, v); } catch (_) { /* layer without that property */ } };
  for (const layer of map.getStyle().layers) {
    const id = layer.id, sl = layer["source-layer"];
    if (sl === "building") { map.setLayoutProperty(id, "visibility", "none"); continue; } // Overture footprints replace OSM-only buildings
    if (id === "park") { set(id, "fill-color", P.park); set(id, "fill-opacity", 0.75); }
    else if (id === "park_outline") set(id, "line-color", P.wood);
    else if (id === "landcover_wood") { set(id, "fill-color", P.wood); set(id, "fill-opacity", 0.7); }
    else if (id === "landcover_grass" || id === "landuse_pitch" || id === "landuse_track") set(id, "fill-color", P.grass);
    else if (id === "landcover_sand") set(id, "fill-color", P.sand);
    else if (id === "water") set(id, "fill-color", P.water);
    else if (sl === "transportation" && layer.type === "line") {
      const casing = id.endsWith("_casing");
      let c = null;
      if (/motorway/.test(id)) c = casing ? P.majorCasing : P.motorway;
      else if (/trunk_primary/.test(id)) c = casing ? P.majorCasing : P.trunk;
      else if (/secondary_tertiary|_link/.test(id)) c = casing ? P.majorCasing : P.secondary;
      else if (/minor|street/.test(id)) c = casing ? P.streetCasing : P.street;
      else if (/service_track/.test(id)) c = casing ? P.streetCasing : P.service;
      else if (/path_pedestrian/.test(id)) { c = casing ? P.streetCasing : P.path; if (!casing) set(id, "line-dasharray", [2, 1.2]); }
      if (c) set(id, "line-color", c);
    }
  }
}

function setupBase() {
  styleBaseColors();
  // Building footprints: Overture Maps (OSM + Google Open Buildings + Microsoft ML footprints) via the API.
  map.addSource("overture", { type: "vector", tiles: [`${location.origin}/api/buildings/{z}/{x}/{y}.pbf`], minzoom: 13, maxzoom: 14,
    attribution: "Buildings © OpenStreetMap contributors, Overture Maps Foundation (ODbL); Google Open Buildings (CC BY 4.0); Microsoft (ODbL)",
    ...(coverageBounds ? { bounds: coverageBounds } : {}) });
  map.addLayer({ id: "ov-buildings", type: "fill", source: "overture", "source-layer": "building", minzoom: 13,
    paint: { "fill-color": BUILDING_COLOR, "fill-outline-color": "#8a7356", "fill-opacity": 0.9 } }, firstSymbolId());
  const empty = { type: "FeatureCollection", features: [] };
  for (const id of ["zones", "suggestion", "nodes", "future", "region", "draft", "corridors"]) map.addSource(id, { type: "geojson", data: empty });
  const sym = firstSymbolId(); // data polygons render under basemap labels
  map.addSource("region-mask", { type: "geojson", data: empty });
  map.addLayer({ id: "region-mask", type: "fill", source: "region-mask", filter: ["==", ["get", "part"], "outside"],
    paint: { "fill-color": "#1b2226", "fill-opacity": 0.55 } }, sym);
  map.addLayer({ id: "region-boundary", type: "line", source: "region-mask", filter: ["==", ["get", "part"], "boundary"],
    paint: { "line-color": "#e2a33b", "line-width": 2.2, "line-opacity": 0.95 } }, sym);
  map.addLayer({ id: "region-line", type: "line", source: "region", paint: { "line-color": "#1d2428", "line-width": 1.2, "line-dasharray": [3, 3], "line-opacity": 0.6 } }, sym);
  // Quebradas: intermittent streams and other waterways from the OpenStreetMap basemap data.
  const vec = Object.entries(map.getStyle().sources).find(([, s]) => s.type === "vector");
  if (vec) {
    const width = ["interpolate", ["linear"], ["zoom"], 9, 1, 13, 2.2, 16, 4];
    map.addLayer({ id: "quebradas", type: "line", source: vec[0], "source-layer": "waterway", minzoom: 9, layout: { visibility: "none" },
      filter: ["==", ["get", "intermittent"], 1],
      paint: { "line-color": COLORS.quebrada, "line-opacity": 0.9, "line-width": width, "line-dasharray": [2, 1.2] } }, sym);
    map.addLayer({ id: "rivers", type: "line", source: vec[0], "source-layer": "waterway", minzoom: 9, layout: { visibility: "none" },
      filter: ["!=", ["get", "intermittent"], 1],
      paint: { "line-color": COLORS.quebrada, "line-opacity": 0.9, "line-width": width } }, sym);
  }
  // Area overview: steep terrain (brown), quebradas by basin type, NISAR-observed ponding (blue).
  for (const id of ["steep", "hazard-quebradas", "ponding-nisar"]) map.addSource(id, { type: "geojson", data: empty });
  map.addLayer({ id: "steep", type: "fill", source: "steep",
    paint: { "fill-color": ["match", ["get", "class"], "very_steep", "#6b4423", "#a0703f"], "fill-opacity": 0.45 } }, sym);
  map.addLayer({ id: "hazard-quebradas", type: "line", source: "hazard-quebradas",
    paint: { "line-color": ["match", ["get", "hazard_class"], "debris_flow_prone", "#c0392b", "debris_flood", "#e67e22", "flood", "#2a6fb0", "#8e8e8e"],
      "line-width": ["interpolate", ["linear"], ["zoom"], 9, 1.5, 13, 3, 16, 6], "line-opacity": 0.95 } }, sym);
  map.addLayer({ id: "ponding-nisar", type: "fill", source: "ponding-nisar",
    paint: { "fill-color": ["match", ["get", "class"], "new_water", "#1f78ff", "#142878"], "fill-opacity": 0.8,
      "fill-outline-color": "#ffffff" } }, sym);
  // Eligible natural ravine corridors (mapped waterways confirmed for huayco starts), highlighted on demand.
  map.addLayer({ id: "corridors", type: "line", source: "corridors",
    paint: { "line-color": "#00b3c7", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 3, 16, 8], "line-opacity": 0.85, "line-blur": 0.5 } }, sym);
  map.addLayer({ id: "zones-fill", type: "fill", source: "zones",
    paint: { "fill-color": ["match", ["get", "role"], "no_go", "#e2654f", "#e2a33b"], "fill-opacity": 0.38 } }, sym);
  map.addLayer({ id: "zones-line", type: "line", source: "zones",
    paint: { "line-color": ["match", ["get", "role"], "no_go", "#b23a28", "#a8650d"], "line-width": 3.2 } }, sym);
  map.addLayer({ id: "suggestion-line", type: "line", source: "suggestion",
    paint: { "line-color": "#1b6fa8", "line-width": 2.5, "line-dasharray": [2, 1.5] } }, sym);
  map.addLayer({ id: "nodes", type: "circle", source: "nodes",
    paint: { "circle-radius": 2.6, "circle-color": "#f4d35e", "circle-stroke-color": "#3b3326", "circle-stroke-width": 0.8 } });
  map.addLayer({ id: "future", type: "circle", source: "future",
    paint: { "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, 1.5, 15, 5], "circle-color": "#4f8a3a",
      "circle-stroke-color": "#e8f4e0", "circle-stroke-width": 0.8, "circle-opacity": 0.9 } });
  map.addLayer({ id: "zones-label", type: "symbol", source: "zones",
    layout: { "text-field": ["get", "label"], "text-size": 12, "text-font": ["Noto Sans Regular"] },
    paint: { "text-color": "#ffffff", "text-halo-color": "rgba(0,0,0,0.75)", "text-halo-width": 1.2 } });
  map.addLayer({ id: "draft-line", type: "line", source: "draft", filter: ["==", ["geometry-type"], "LineString"],
    paint: { "line-color": "#1d2428", "line-width": 2.5, "line-dasharray": [2, 1] } });
  map.addLayer({ id: "draft-pts", type: "circle", source: "draft", filter: ["==", ["geometry-type"], "Point"],
    paint: { "circle-radius": 7, "circle-color": "#e2a33b", "circle-stroke-color": "#1d2428", "circle-stroke-width": 2 } });
  map.addLayer({ id: "draft-num", type: "symbol", source: "draft", filter: ["==", ["geometry-type"], "Point"],
    layout: { "text-field": ["get", "n"], "text-size": 11, "text-font": ["Noto Sans Regular"], "text-allow-overlap": true },
    paint: { "text-color": "#1d2428" } });
  initTwin(map);
  map.on("click", "zones-fill", (e) => emit("zoneClick", e.features[0] && e.features[0].properties));
  emit("ready", map);
}

// Radar and optical tiles go through the API proxy, which makes GIBS's black no-data transparent.
const activeImagery = new Map();
const PROXY_KEY = { nisar: "nisar_gcov", rtc: "opera_rtc", hls: "hls_s30", dswx: "dswx" };
function gibsTiles(info, date, key) {
  if (PROXY_KEY[key]) return [`${location.origin}/api/tiles/${PROXY_KEY[key]}/${date}/{z}/{x}/{y}.png`];
  return [`${GIBS}/${info.gibs}/default/${date}/${info.tms}/{z}/{y}/{x}.${info.ext}`];
}

/** Show (or hide with date=null) a GIBS layer; rasters sit under labels and data layers. */
export function setImagery(key, date, opacity = 1) {
  const id = `img-${key}`;
  if (date && activeImagery.get(key) === date) { setImageryOpacity(key, opacity); return; }
  activeImagery.delete(key);
  if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(id)) map.removeSource(id);
  if (!date) return;
  activeImagery.set(key, date);
  const info = LAYER_INFO[key];
  map.addSource(id, { type: "raster", tiles: gibsTiles(info, date, key), tileSize: 256, maxzoom: info.maxzoom,
    attribution: `${info.src} (${date})`, ...(regionBounds ? { bounds: regionBounds } : {}) });
  // Linear resampling only smooths pixel edges when zoomed past the native level; it adds no detail.
  map.addLayer({ id, type: "raster", source: id, layout:{visibility:imagesVisible?"visible":"none"}, paint: { "raster-opacity": opacity, "raster-resampling": "linear", "raster-fade-duration": 0 } },
    "region-line");
}

export function setImageryOpacity(key, opacity) {
  const id = `img-${key}`;
  if (map.getLayer(id)) map.setPaintProperty(id, "raster-opacity", opacity);
}

export function setCorridors(fc) { setData("corridors", fc); }
export function setLandscape(r) { setData("steep", r ? r.steep : null); setData("hazard-quebradas", r ? r.quebradas : null); }
export function setPondingMap(fc) { setData("ponding-nisar", fc); }

/** Dim everything outside the exact study boundary and outline it (null clears). The box outline is hidden then. */
export function setRegionMask(feature) {
  if (!feature) { setData("region-mask", null); setVisibility(["region-line"], true); return; }
  const g = feature.geometry;
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  const world = [[-180, -85], [180, -85], [180, 85], [-180, 85], [-180, -85]];
  const holes = polys.map((p) => p[0].slice().reverse());
  setData("region-mask", { type: "FeatureCollection", features: [
    { type: "Feature", properties: { part: "outside" }, geometry: { type: "Polygon", coordinates: [world, ...holes] } },
    { type: "Feature", properties: { part: "boundary" }, geometry: { type: "MultiLineString", coordinates: polys.map((p) => p[0]) } },
  ] });
  setVisibility(["region-line"], false);
}

export function setData(sourceId, fc) {
  const s = map.getSource(sourceId);
  if (s) s.setData(fc || { type: "FeatureCollection", features: [] });
}

let exaggeration = 3; // default relief exaggeration in 3D (declared in the legend; x1 = true relief)
export function getExaggeration() { return exaggeration; }
export function setExaggeration(x) {
  exaggeration = x;
  if (terrainOn) map.setTerrain({ source: "dem", exaggeration });
}

/** 3D buildings from Overture footprints: mapped height, else floors x 3 m, else a 3 m display default (stated in the legend). */
export function setBuildings(on) {
  const id = "buildings-3d";
  if (!on) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", "none"); return; }
  if (!map.getLayer(id)) {
    map.addLayer({
      id, type: "fill-extrusion", source: "overture", "source-layer": "building", minzoom: 14,
      paint: {
        "fill-extrusion-color": BUILDING_COLOR,
        "fill-extrusion-height": ["max", BUILDING_HEIGHT, ["coalesce", ["get", "min_height"], 0]],
        "fill-extrusion-base": ["coalesce", ["get", "min_height"], 0],
        "fill-extrusion-opacity": 0.92,
        "fill-extrusion-vertical-gradient": true,
      },
    }, "zones-label");
  }
  map.setLayoutProperty(id, "visibility", "visible");
}

let materialPaint = [];
/** Surface colours describe mapped cover. Unclassified background is a display palette, not a classification. */
export function setTerritoryMaterials(on) {
  if (!on) { for (const [id, key, value] of materialPaint) if (map.getLayer(id)) map.setPaintProperty(id, key, value); materialPaint = []; return; }
  if (materialPaint.length) return;
  const paint = (layer, key, value) => { materialPaint.push([layer.id, key, map.getPaintProperty(layer.id, key)]); map.setPaintProperty(layer.id, key, value); };
  for (const layer of map.getStyle().layers) {
    const sl = layer["source-layer"];
    if (layer.type === "background") paint(layer, "background-color", "#d2c3a4");
    if (sl === "transportation" && layer.type === "line") paint(layer, "line-color", /casing/.test(layer.id) ? "#c2b9a8" : /path|track/.test(layer.id) ? "#9b8c72" : "#62676a");
    if (sl === "water" && layer.type === "fill") paint(layer, "fill-color", "#6096ad");
    if ((sl === "park" || sl === "landcover") && layer.type === "fill") {
      if (/wood|forest/.test(layer.id)) paint(layer, "fill-color", "#6e8253");
      else if (/grass|park/.test(layer.id)) paint(layer, "fill-color", "#a5ae76");
      else if (/sand/.test(layer.id)) paint(layer, "fill-color", "#d8c49a");
    }
    if (sl === "landuse" && layer.type === "fill" && /farmland|agricultur/.test(layer.id)) paint(layer, "fill-color", "#bac18b");
  }
}

function setAtmosphere(on) {
  if (typeof map.setSky === "function") {
    map.setSky(on ? { "sky-color": "#9cc3e0", "horizon-color": "#e9e2d0", "fog-color": "#e9e2d0", "sky-horizon-blend": 0.6,
      "horizon-fog-blend": 0.7, "fog-ground-blend": 0.35, "atmosphere-blend": 0.8 } : {});
  }
  if (typeof map.setLight === "function") map.setLight({ anchor: "map", position: [1.4, 210, 35], intensity: on ? 0.45 : 0.3, color: "#fff6e8" });
}

export function setTerrain(on) {
  terrainOn = on;
  if (on) {
    ensureDEM();
    map.setTerrain({ source: "dem", exaggeration });
    syncTerrainAnchor();
    setBuildings(true);
    setTerritoryMaterials(true);
    setAtmosphere(true);
    if (map.getLayer("relief-tint")) map.setLayoutProperty("relief-tint", "visibility", "visible"); // mountains read brown in 3D
    map.setPaintProperty("hillshade", "hillshade-exaggeration", 0.55);
    map.setLayoutProperty("hillshade", "visibility", "visible");
    map.easeTo({ pitch: 60, duration: reduceMotion() ? 0 : 1200 });
  } else {
    map.setTerrain(null);
    setBuildings(false);
    setTerritoryMaterials(false);
    setAtmosphere(false);
    if (map.getLayer("relief-tint") && map.getLayoutProperty("hillshade", "visibility") !== "visible") map.setLayoutProperty("relief-tint", "visibility", "none");
    if (map.getLayer("hillshade")) map.setPaintProperty("hillshade", "hillshade-exaggeration", 0.35);
    map.easeTo({ pitch: 0, bearing: 0, duration: reduceMotion() ? 0 : 900 });
  }
  return terrainOn;
}

export function flyTo(center, zoom) {
  if (!map) return;
  const opts = { center, zoom, essential: false };
  if (reduceMotion()) map.jumpTo(opts); else map.flyTo({ ...opts, curve: 1.4, speed: 1.1 });
}

export function fitBounds(b, padding = 60, animate = true) {
  // Guard: a zero-size container (hidden tab) makes fit computations produce NaN.
  const c = map.getContainer();
  if (!c.clientWidth || !c.clientHeight) { map.once("resize", () => fitBounds(b, padding, animate)); return; }
  map.fitBounds(b, { padding: { top: padding + 60, bottom: padding, left: Math.min(420, c.clientWidth / 2), right: padding }, duration: animate && !reduceMotion() ? 1200 : 0, maxZoom: 15 });
}

/**
 * Snapshot of the current map (streets, buildings, quebradas, data layers) over a lon/lat box, used as
 * the AR terrain texture so the tabletop shows the real place. The camera is restored afterwards.
 */
export async function snapshot(bbox, widthPx = 1024, aspect = 0.7067) {
  const cam = { center: map.getCenter(), zoom: map.getZoom(), bearing: map.getBearing(), pitch: map.getPitch() };
  const terrain = map.getTerrain();
  if (terrain) map.setTerrain(null);
  map.fitBounds([[bbox[0], bbox[1]], [bbox[2], bbox[3]]], { padding: 0, bearing: 0, pitch: 0, duration: 0 });
  try {
    await new Promise((resolve, reject) => {
      const ready = () => { clearTimeout(timer); map.off("idle", ready); resolve(); };
      const timer = setTimeout(() => { map.off("idle", ready); reject(new Error("The map snapshot timed out.")); }, 6000);
      if (map.loaded()) ready(); else map.once("idle", ready);
    });
    return await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { map.off("render", capture); reject(new Error("The map did not render a snapshot.")); }, 1000);
      const capture = () => {
        clearTimeout(timer);
        try {
          const src = map.getCanvas();
          const a = map.project([bbox[0], bbox[3]]), b = map.project([bbox[2], bbox[1]]);
          const dpr = src.width / map.getContainer().clientWidth;
          const out = document.createElement("canvas");
          out.width = widthPx; out.height = Math.round(widthPx * aspect);
          out.getContext("2d").drawImage(src, a.x * dpr, a.y * dpr, (b.x - a.x) * dpr, (b.y - a.y) * dpr, 0, 0, out.width, out.height);
          resolve(out.toDataURL("image/jpeg", 0.88));
        } catch (error) { reject(error); }
      };
      map.once("render", capture); map.triggerRepaint();
    });
  } finally {
    if (terrain) map.setTerrain(terrain);
    map.jumpTo(cam);
  }
}

export function reduceMotion() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }

export function bboxOf(fc) {
  let w = 180, s = 90, e = -180, n = -90;
  const walk = (c) => { if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); } else c.forEach(walk); };
  (fc.features || []).forEach((f) => walk(f.geometry.coordinates));
  return w <= e ? [w, s, e, n] : null;
}
