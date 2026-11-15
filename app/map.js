// MapLibre map: OpenFreeMap basemap, GIBS imagery, Copernicus DEM terrain, zones and results.
const BASEMAP = "https://tiles.openfreemap.org/styles/positron";
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best";
const GIBS_ATTR = '<a href="https://earthdata.nasa.gov/gibs" target="_blank" rel="noopener">NASA GIBS</a>';
const DEM_ATTR = "Terrain: Copernicus DEM GLO-30 © DLR, © Airbus, provided under COPERNICUS by the EU and ESA";

export const LAYER_INFO = {
  hls: { title: "Optical context (HLS, 30 m)", gibs: "HLS_S30_Nadir_BRDF_Adjusted_Reflectance", tms: "GoogleMapsCompatible_Level12", ext: "png", maxzoom: 12,
    cls: "observed", src: "NASA HLS Sentinel-2 surface reflectance, true-colour rendering via GIBS", explain: "Harmonized Landsat Sentinel-2 true colour. Shown at its native 30 m; zooming further only enlarges pixels. Clouds are not removed." },
  nisar: { title: "NISAR radar (GCOV)", gibs: "NISAR_L2_Geocoded_Polarimetric_Covariance", tms: "GoogleMapsCompatible_Level13", ext: "png", maxzoom: 13,
    cls: "observed", src: "NISAR L2 GCOV normalized backscatter, false-colour rendering via GIBS", explain: "L-band radar backscatter from NISAR. Bright means a rough or vegetated surface or structures; dark means smooth surfaces such as calm water or flat bare soil. It is not a moisture or depth measurement." },
  rtc: { title: "Sentinel-1 radar (OPERA RTC)", gibs: "OPERA_L2_Radiometric_Terrain_Corrected_SAR_Sentinel-1", tms: "GoogleMapsCompatible_Level12", ext: "png", maxzoom: 12,
    cls: "observed", src: "OPERA RTC-S1 (C-band), rendering via GIBS", explain: "C-band radar from Sentinel-1, terrain corrected. Used here because NISAR has no January–April 2026 acquisitions over Piura." },
  imerg: { title: "Rain rate (GPM IMERG)", gibs: "IMERG_Precipitation_Rate", tms: "GoogleMapsCompatible_Level6", ext: "png", maxzoom: 6,
    cls: "derived", src: "GPM IMERG daily precipitation rate via GIBS (about 10 km)", explain: "Satellite precipitation estimate on a 0.1° grid. Use it to see when and roughly where it rained, not which street flooded." },
};

let map, terrainOn = false;
const listeners = {};

export function on(evt, fn) { (listeners[evt] = listeners[evt] || []).push(fn); }
function emit(evt, data) { (listeners[evt] || []).forEach((f) => f(data)); }

export function getMap() { return map; }

export function initMap(container, view) {
  map = new maplibregl.Map({
    container, style: BASEMAP, center: view.center, zoom: view.zoom, pitch: 0, maxPitch: 75,
    attributionControl: { compact: false, customAttribution: `${GIBS_ATTR} · ${DEM_ATTR}` },
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
  map.on("error", (e) => emit("error", e && e.error ? e.error.message || String(e.error) : "Map error"));
  return new Promise((resolve) => map.on("load", () => { setupBase(); resolve(map); }));
}

function firstSymbolId() {
  const l = map.getStyle().layers.find((x) => x.type === "symbol");
  return l ? l.id : undefined;
}

function setupBase() {
  map.addSource("dem", { type: "raster-dem", tiles: [`${location.origin}/api/terrain/{z}/{x}/{y}.png`], tileSize: 256,
    encoding: "terrarium", maxzoom: 12, attribution: "" });
  map.addLayer({ id: "hillshade", type: "hillshade", source: "dem",
    paint: { "hillshade-exaggeration": 0.35, "hillshade-shadow-color": "#3b3326", "hillshade-highlight-color": "#ffffff", "hillshade-illumination-direction": 315 } },
    firstSymbolId());
  const empty = { type: "FeatureCollection", features: [] };
  for (const id of ["zones", "suggestion", "nodes", "future", "region"]) map.addSource(id, { type: "geojson", data: empty });
  const sym = firstSymbolId(); // data polygons render under basemap labels
  map.addLayer({ id: "region-line", type: "line", source: "region", paint: { "line-color": "#1d2428", "line-width": 1.2, "line-dasharray": [3, 3], "line-opacity": 0.6 } }, sym);
  map.addLayer({ id: "zones-fill", type: "fill", source: "zones",
    paint: { "fill-color": ["match", ["get", "role"], "no_go", "#e2654f", "#e2a33b"], "fill-opacity": 0.18 } }, sym);
  map.addLayer({ id: "zones-line", type: "line", source: "zones",
    paint: { "line-color": ["match", ["get", "role"], "no_go", "#c64b37", "#b9791b"], "line-width": 2.4 } }, sym);
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
  map.on("click", "zones-fill", (e) => emit("zoneClick", e.features[0] && e.features[0].properties));
  emit("ready", map);
}

// Radar and optical tiles go through the API proxy, which makes GIBS's black no-data transparent.
const PROXY_KEY = { nisar: "nisar_gcov", rtc: "opera_rtc", hls: "hls_s30" };
function gibsTiles(info, date, key) {
  if (PROXY_KEY[key]) return [`${location.origin}/api/tiles/${PROXY_KEY[key]}/${date}/{z}/{x}/{y}.png`];
  return [`${GIBS}/${info.gibs}/default/${date}/${info.tms}/{z}/{y}/{x}.${info.ext}`];
}

/** Show (or hide with date=null) a GIBS layer; rasters sit under labels and data layers. */
export function setImagery(key, date, opacity = 1) {
  const id = `img-${key}`;
  if (map.getLayer(id)) map.removeLayer(id);
  if (map.getSource(id)) map.removeSource(id);
  if (!date) return;
  const info = LAYER_INFO[key];
  map.addSource(id, { type: "raster", tiles: gibsTiles(info, date, key), tileSize: 256, maxzoom: info.maxzoom,
    attribution: `${info.src} (${date})` });
  // Linear resampling only smooths pixel edges when zoomed past the native level; it adds no detail.
  map.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": opacity, "raster-resampling": "linear", "raster-fade-duration": 0 } },
    "region-line");
}

export function setImageryOpacity(key, opacity) {
  const id = `img-${key}`;
  if (map.getLayer(id)) map.setPaintProperty(id, "raster-opacity", opacity);
}

export function setData(sourceId, fc) {
  const s = map.getSource(sourceId);
  if (s) s.setData(fc || { type: "FeatureCollection", features: [] });
}

let exaggeration = 1;
export function getExaggeration() { return exaggeration; }
export function setExaggeration(x) {
  exaggeration = x;
  if (terrainOn) map.setTerrain({ source: "dem", exaggeration });
}

/** 3D buildings from the basemap's OpenStreetMap footprints (OpenMapTiles `building` layer). */
function setBuildings(on) {
  const id = "buildings-3d";
  if (!on) { if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", "none"); return; }
  if (!map.getLayer(id)) {
    const src = Object.entries(map.getStyle().sources).find(([, s]) => s.type === "vector");
    if (!src) return;
    map.addLayer({
      id, type: "fill-extrusion", source: src[0], "source-layer": "building", minzoom: 13,
      paint: {
        // render_height comes from OSM height/levels tags, or an OpenMapTiles default when untagged.
        "fill-extrusion-color": ["interpolate", ["linear"], ["coalesce", ["get", "render_height"], 6], 0, "#d8cfbf", 20, "#c9bba3", 60, "#b5a487"],
        "fill-extrusion-height": ["interpolate", ["linear"], ["zoom"], 13, 0, 14.5, ["coalesce", ["get", "render_height"], 6]],
        "fill-extrusion-base": ["coalesce", ["get", "render_min_height"], 0],
        "fill-extrusion-opacity": 0.92,
        "fill-extrusion-vertical-gradient": true,
      },
    }, "zones-label");
  }
  map.setLayoutProperty(id, "visibility", "visible");
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
    map.setTerrain({ source: "dem", exaggeration });
    setBuildings(true);
    setAtmosphere(true);
    map.setPaintProperty("hillshade", "hillshade-exaggeration", 0.55);
    map.easeTo({ pitch: 60, zoom: Math.max(map.getZoom(), 14), duration: reduceMotion() ? 0 : 1600 });
  } else {
    map.setTerrain(null);
    setBuildings(false);
    setAtmosphere(false);
    map.setPaintProperty("hillshade", "hillshade-exaggeration", 0.35);
    map.easeTo({ pitch: 0, bearing: 0, duration: reduceMotion() ? 0 : 900 });
  }
  return terrainOn;
}

export function flyTo(center, zoom) {
  if (!map) return;
  const opts = { center, zoom, essential: false };
  if (reduceMotion()) map.jumpTo(opts); else map.flyTo({ ...opts, curve: 1.4, speed: 1.1 });
}

export function fitBounds(b, padding = 60) {
  // Guard: a zero-size container (hidden tab) makes fit computations produce NaN.
  const c = map.getContainer();
  if (!c.clientWidth || !c.clientHeight) { map.once("resize", () => fitBounds(b, padding)); return; }
  map.fitBounds(b, { padding: { top: padding + 60, bottom: padding, left: Math.min(420, c.clientWidth / 2), right: padding }, duration: reduceMotion() ? 0 : 1200, maxZoom: 15 });
}

export function reduceMotion() { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; }

export function bboxOf(fc) {
  let w = 180, s = 90, e = -180, n = -90;
  const walk = (c) => { if (typeof c[0] === "number") { w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]); } else c.forEach(walk); };
  (fc.features || []).forEach((f) => walk(f.geometry.coordinates));
  return w <= e ? [w, s, e, n] : null;
}
