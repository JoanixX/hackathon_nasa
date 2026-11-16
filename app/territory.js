// Lifecycle and compact controls for the existing map. Loaded only on first entry into 3D.
import { el } from "./dom.js";
import { PIURA_VIEWS, vegetationSamples, solarPosition, renderPolicy } from "./territory-geo.js";
import { TerritoryLayer } from "./territory-gl.js";

export function createTerritory(map, { onError, setBuildings, setHillshade, setMaterials, fitRegion, onChange = () => {} }) {
  const layer = new TerritoryLayer(onError), canvas = map.getCanvas();
  const originalRatio=map.getPixelRatio();
  const options = { trees: true, water: true, buildings: true, materials: true, shading: true, weather: "clear", animate: false, inspect: false };
  let active = false, disposed = false, lost = false, timer = null, refreshTimer = null, pointRequest = null, epoch = 0;
  const bindings = [];
  const info = el("p", { class: "note territory-inspect", id: "territory-inspect", role: "status" }, "Enable Inspect, then click a mapped element or the terrain.");
  const status = el("p", { class: "note", id: "territory-detail-status" });
  const controls = el("details", { class: "block territory-controls", open: true }, el("summary", {}, "Piura · territorial view"));
  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let softwareGraphics=false;
  const quality=el("select",{id:"territory-quality"});
  for(const [key,label]of [["1","Native resolution"],["0.75","Balanced resolution"],["0.5","Low resolution"]])quality.append(el("option",{value:key},label));
  const resolution=()=>renderPolicy({ratio:originalRatio,quality:Number(quality.value),software:softwareGraphics}).pixelRatio;
  quality.onchange=()=>{if(active)map.setPixelRatio(resolution());};
  function listen(name, fn) { map.on(name, fn); bindings.push([name, fn]); }
  function checkbox(label, key, run) {
    const input = el("input", { type: "checkbox", checked: options[key], "data-territory": key });
    input.addEventListener("change", () => { options[key] = input.checked; if (run) run(input.checked); refresh(); animate(); onChange(); });
    return el("label", { class: "territory-check" }, input, label);
  }
  const places = el("div", { class: "territory-places" });
  for (const [key, view] of Object.entries(PIURA_VIEWS)) places.append(el("button", { type: "button", class: "btn quiet", "data-place": key, onclick: () => {
    if (view.bounds) fitRegion(view.bounds);
    else map.easeTo({ center: view.center, zoom: view.zoom, bearing: view.bearing, pitch: 64, duration: motion.matches ? 0 : 1100 });
  } }, view.label));
  controls.append(places);
  const layers = el("div", { class: "territory-layers" },
    checkbox("Mapped buildings", "buildings", setBuildings), checkbox("Illustrative forest trees", "trees"),
    checkbox("Waterway ripples", "water"), checkbox("Land-cover materials", "materials", setMaterials),
    checkbox("Terrain shading", "shading", setHillshade), checkbox("Animate effects", "animate"), checkbox("Inspect coordinates / element", "inspect"));
  const weather = el("select", { id: "territory-weather" });
  for (const [key, label] of [["clear","Clear sky"],["overcast","Overcast"],["moderate","Moderate rain"],["heavy","Heavy rain"],["extreme","Extreme-weather view"]]) weather.append(el("option", { value: key }, label));
  weather.onchange = () => { options.weather = weather.value; atmosphere(); animate(); };
  const date = el("input", { type: "datetime-local", id: "territory-time", value: new Date(Date.now() - 5 * 3600e3).toISOString().slice(0,16) });
  date.onchange = () => atmosphere();
  controls.append(layers, el("label",{for:"territory-quality"},"Render quality"),quality,
    el("label", { for: "territory-weather" }, "Visual weather scenario"), weather,
    el("label", { for: "territory-time" }, "Sun date and time (Peru, UTC−05:00)"), date,
    el("p", { class: "note" }, "Weather and ripples are illustrative, not observations or forecasts. Tree locations, sizes and species are procedural within mapped forest/park cover; incomplete mapping cannot establish planting clearance."),
    el("div", { class: "row" }, el("button", { class: "btn", type: "button", onclick: () => map.easeTo({ pitch: 0, bearing: 0, duration: motion.matches ? 0 : 700 }) }, "Aerial view"),
      el("button", { class: "btn", type: "button", onclick: () => map.easeTo({ pitch: 64, duration: motion.matches ? 0 : 700 }) }, "Perspective view")),
    status, info,
    el("details", { class: "glossary" }, el("summary", {}, "Scale, materials and navigation"), el("p", {},
      "Drag to pan; right-drag or Ctrl-drag to rotate and tilt; scroll or pinch to zoom. Terrain defaults to ×1. Ochre/sand is the bare-ground display palette; mapped forest, agriculture, water and urban cover keep their classes. Elevation is a 30 m surface model, not surveyed bare ground. Buildings use mapped height, floors ×3 m, or an estimated 3 m. Map dates and accuracy differ by layer.")));

  function sourceFeatures() {
    // Query only visible layers/tiles: no regional feature download or independent tile scheduler.
    const layers=map.getStyle().layers.filter(l=>["fill","line"].includes(l.type)&&["landcover","park","landuse","transportation","building","water","waterway"].includes(l["source-layer"])).map(l=>l.id);
    return map.queryRenderedFeatures(undefined,{layers});
  }
  function refresh() {
    clearTimeout(refreshTimer);refreshTimer=null;
    if(!active||disposed||lost||!map.isStyleLoaded())return;
    if(map.getZoom()<13) {
      layer.setData([],[],map.getCenter().toArray());
      status.textContent="Regional terrain. Zoom closer for forest and waterway detail (zoom 13+).";
      animate();return;
    }
    if(!map.isSourceLoaded("dem")) {
      layer.setData([],[],map.getCenter().toArray());
      status.textContent="Loading source terrain. Close-up detail is withheld until DEM tiles are ready.";
      return;
    }
    const features=sourceFeatures(), bySourceLayer=f=>f.sourceLayer||f.layer?.["source-layer"];
    const cover=features.filter(f=>["landcover","park","landuse"].includes(bySourceLayer(f)));
    const exclusions=features.filter(f=>["transportation","building","water","waterway"].includes(bySourceLayer(f)));
    const center=map.getCenter().toArray();
    const samples=options.trees?vegetationSamples(cover,exclusions,center,map.getZoom()):[];
    const water=options.water?features.filter(f=>bySourceLayer(f)==="waterway"):[];
    layer.setData(samples,water,center);
    status.textContent=`${layer.stats.trees} illustrative trees · ${layer.stats.waterSegments} waterway segments · detail at zoom 13+. ${exclusions.length>256?"Dense infrastructure: procedural trees withheld.":"Only loaded mapping is used."}`;
    animate();
  }
  function schedule() {
    if(active&&!refreshTimer)refreshTimer=setTimeout(refresh,350);
  }
  function atmosphere() {
    if(!active)return;
    const cloudy=options.weather!=="clear", wet=["moderate","heavy","extreme"].includes(options.weather);
    if(date.value) {
      try {
        const c=map.getCenter(),sun=solarPosition(new Date(date.value+":00-05:00"),c.lng,c.lat);
        layer.sun=sun.direction;
        map.setLight({anchor:"map",position:[1.4,sun.azimuth,Math.min(88,Math.max(2,90-sun.altitude))],intensity:cloudy?.25:.5,color:"#fff2de"});
      }catch(error){onError(error.message);}
    }
    map.setSky({"sky-color":cloudy?"#9aaeb7":"#9dc5df","horizon-color":"#e7e2d7","fog-color":cloudy?"#aebcc0":"#e7e2d7",
      "sky-horizon-blend":.65,"horizon-fog-blend":.7,"fog-ground-blend":cloudy?.20:.08,"atmosphere-blend":.8});
    layer.rain=wet?({moderate:.5,heavy:.85,extreme:1}[options.weather]):0;
    map.triggerRepaint();
  }
  function animate() {
    clearTimeout(timer);timer=null;
    const policy=renderPolicy({software:softwareGraphics,reduced:motion.matches,visible:!document.hidden,animate:options.animate});
    layer.moving=policy.fps>0;
    if(!active||disposed||lost||document.hidden||!layer.moving||(!layer.stats.waterSegments&&!layer.rain))return;
    const tick=()=>{if(!active||disposed||lost||document.hidden)return;map.triggerRepaint();timer=setTimeout(tick,1000/policy.fps);};
    tick();
  }
  async function inspect(e) {
    if(!active||!options.inspect)return;
    pointRequest?.abort();const request=pointRequest=new AbortController(),version=++epoch;
    const feature=map.queryRenderedFeatures(e.point).find(f=>["building","water","waterway","transportation","landcover","landuse","park"].includes(f.sourceLayer||f.layer?.["source-layer"]));
    const p=feature?.properties||{},kind=feature?.sourceLayer||feature?.layer?.["source-layer"]||"terrain";
    const name=String(p.name||p["name:latin"]||p.class||kind).slice(0,140);
    const building=kind==="building"?` Height: ${Number.isFinite(p.height)?p.height+" m (mapped)":Number.isFinite(p.num_floors)?p.num_floors*3+" m (estimated from floors)":"3 m (display estimate)"}.`:"";
    const prefix=`${name} · ${e.lngLat.lng.toFixed(6)}, ${e.lngLat.lat.toFixed(6)} (WGS84).${building}`;
    info.textContent=prefix+" Checking source elevation…";
    const timeout=setTimeout(()=>request.abort(),8000);
    try {
      const q=new URLSearchParams({lon:e.lngLat.lng,lat:e.lngLat.lat});
      const response=await fetch("/api/terrain/point?"+q,{signal:request.signal});
      if(!response.ok)throw new Error("Source elevation unavailable.");
      const r=await response.json();
      if(version===epoch&&active)info.textContent=prefix+` DSM elevation: ${r.elevation_m===null?"unknown":r.elevation_m.toFixed(1)+" m, EGM2008"}. Source: Copernicus GLO-30; nearest source cell, not surveyed height.`;
    }catch(error){if(version===epoch&&active)info.textContent=prefix+" Source elevation unknown (unavailable or request cancelled).";}
    finally{clearTimeout(timeout);}
  }
  function contextLost(){lost=true;clearTimeout(timer);clearTimeout(refreshTimer);refreshTimer=null;pointRequest?.abort();onError("Graphics context lost. Waiting for browser recovery; elevation and details are unavailable.");}
  function contextRestored(){lost=false;layer.release();try{layer.allocate();refresh();atmosphere();animate();}catch(error){onError(error.message);}}
  function visibility(){animate();}
  map.addLayer(layer);
  const debug=layer.gl?.getExtension("WEBGL_debug_renderer_info");
  softwareGraphics=!!debug&&/swiftshader|llvmpipe|software|basic render/i.test(layer.gl.getParameter(debug.UNMASKED_RENDERER_WEBGL));
  if(softwareGraphics){quality.value="0.5";controls.append(el("p",{class:"warnline"},"Software graphics detected: half resolution by default; animated effects are limited to one update per second. Hardware performance remains unverified."));}
  listen("moveend",()=>{schedule();atmosphere();});listen("sourcedata",e=>{if(e.sourceId!=="dem"&&!['openmaptiles','overture'].includes(e.sourceId))return;schedule();});
  listen("terrain",schedule);listen("click",inspect);
  canvas.addEventListener("webglcontextlost",contextLost);canvas.addEventListener("webglcontextrestored",contextRestored);
  document.addEventListener("visibilitychange",visibility);motion.addEventListener("change",visibility);
  function setActive(value) {
    active=Boolean(value)&&!disposed;layer.active=active;
    if(active){map.setPixelRatio(resolution());setMaterials(options.materials);setBuildings(options.buildings);setHillshade(options.shading);refresh();atmosphere();animate();}
    else{clearTimeout(timer);clearTimeout(refreshTimer);refreshTimer=null;pointRequest?.abort();epoch++;layer.setData([],[],map.getCenter().toArray());if(map.getStyle())map.setPixelRatio(originalRatio);}
  }
  function dispose() {
    if(disposed)return;setActive(false);disposed=true;
    for(const [name,fn] of bindings)map.off(name,fn);
    canvas.removeEventListener("webglcontextlost",contextLost);canvas.removeEventListener("webglcontextrestored",contextRestored);
    document.removeEventListener("visibilitychange",visibility);motion.removeEventListener("change",visibility);
    if(map.getLayer(layer.id))map.removeLayer(layer.id);
  }
  listen("remove",dispose);
  return { controls, options, stats:layer.stats, setActive, refresh:()=>{refresh();animate();}, dispose };
}
