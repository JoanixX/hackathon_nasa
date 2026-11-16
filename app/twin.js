// 3D digital-twin views on the MapLibre terrain (no extra library): species trees, observed ponding,
// and huayco (debris-flow) scenarios along the real downhill path of a quebrada.
// The huayco views are illustrative scenarios built from the DEM path; they are not a debris-flow model.
let map = null;
let raf = null;
let settlePlayback = null;
let recorder = null;
export const recordingStats = {};

const EMPTY = { type: "FeatureCollection", features: [] };
/** Feature count last drawn per twin source (diagnostics and browser checks). */
export const counts = { "twin-trees": 0, "twin-water": 0, "twin-mud": 0, "twin-path": 0 };
function put(id, fc) { counts[id] = fc && fc.features ? fc.features.length : 0; map.getSource(id).setData(fc || EMPTY); }
const M_PER_DEG_LAT = 111320;

export const COLORS = {
  water: "#2f7fd8", waterPartial: "#8cc4ee", mud: "#7b5a3a", mudEdge: "#5a3f25", path: "#3a2a18",
  quebrada: "#2a6fb0", trunk: "#6b4a2b",
};

export function initTwin(m) {
  map = m;
  const add = (id) => { if (!map.getSource(id)) map.addSource(id, { type: "geojson", data: EMPTY }); };
  ["twin-trees", "twin-water", "twin-mud", "twin-path"].forEach(add);
  map.addLayer({ id: "twin-water", type: "fill-extrusion", source: "twin-water",
    paint: { "fill-extrusion-color": ["coalesce", ["get", "color"], COLORS.water], "fill-extrusion-height": ["coalesce", ["get", "h"], 0.8],
      "fill-extrusion-base": 0, "fill-extrusion-opacity": 0.85 } });
  map.addLayer({ id: "twin-path", type: "line", source: "twin-path",
    paint: { "line-color": COLORS.path, "line-width": ["interpolate", ["linear"], ["zoom"], 11, 1.5, 16, 4], "line-dasharray": [1.5, 1] } });
  map.addLayer({ id: "twin-mud", type: "fill-extrusion", source: "twin-mud",
    paint: { "fill-extrusion-color": ["coalesce", ["get", "color"], COLORS.mud], "fill-extrusion-height": ["coalesce", ["get", "h"], 3],
      "fill-extrusion-base": 0, "fill-extrusion-opacity": 0.92, "fill-extrusion-vertical-gradient": true } });
  map.addLayer({ id: "twin-trees", type: "fill-extrusion", source: "twin-trees",
    paint: { "fill-extrusion-color": ["get", "color"], "fill-extrusion-height": ["get", "top"], "fill-extrusion-base": ["get", "base"],
      "fill-extrusion-opacity": 1, "fill-extrusion-vertical-gradient": true } });
}

function circle(lon, lat, rM, n = 10, rot = 0) {
  const k = 1 / (M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180));
  const ring = [];
  for (let i = 0; i <= n; i++) {
    const a = rot + (i / n) * 2 * Math.PI;
    ring.push([lon + Math.cos(a) * rM * k, lat + (Math.sin(a) * rM) / M_PER_DEG_LAT]);
  }
  return { type: "Polygon", coordinates: [ring] };
}

/**
 * Tree digital twins: each placement becomes a trunk plus a crown shaped by its species model
 * (broad-flat algarrobo, rounded sapote, umbrella faique). `growth` scales the mature form (0..1).
 */
export function treeFeatures(placements, speciesById, growth = 1) {
  const feats = [];
  for (const p of placements) {
    if (p.lon === null || p.lon === undefined) continue;
    const sp = speciesById[p.species_id] || {};
    const m = sp.model || { height_m: 6, crown_radius_m: 3, crown_shape: "rounded", trunk_ratio: 0.35, crown_color: "#4f8a3a", trunk_color: COLORS.trunk };
    const H = m.height_m * growth, R = Math.max(0.6, m.crown_radius_m * growth);
    const trunkTop = H * m.trunk_ratio;
    const seed = (p.reveal_rank || 0.5) * 6.28;
    feats.push({ type: "Feature", geometry: circle(p.lon, p.lat, Math.max(0.25, R * 0.12), 6, seed), properties: { color: m.trunk_color || COLORS.trunk, base: 0, top: trunkTop + H * 0.1 } });
    if (m.crown_shape === "umbrella") {
      feats.push({ type: "Feature", geometry: circle(p.lon, p.lat, R, 12, seed), properties: { color: m.crown_color, base: H * 0.78, top: H } });
    } else if (m.crown_shape === "broad_flat") {
      feats.push({ type: "Feature", geometry: circle(p.lon, p.lat, R * 0.75, 12, seed), properties: { color: m.crown_color, base: trunkTop, top: H * 0.82 } });
      feats.push({ type: "Feature", geometry: circle(p.lon, p.lat, R, 12, seed + 0.2), properties: { color: m.crown_color, base: H * 0.55, top: H } });
    } else {
      // Rounded crown approximated by three stacked discs.
      [[0.7, 0.35, 0.6], [1.0, 0.55, 0.85], [0.65, 0.8, 1.0]].forEach(([rf, b, t]) =>
        feats.push({ type: "Feature", geometry: circle(p.lon, p.lat, R * rf, 12, seed), properties: { color: m.crown_color, base: H * b, top: H * t } }));
    }
  }
  return { type: "FeatureCollection", features: feats };
}

export function setTrees(fc) { put("twin-trees", fc); }

/** Observed ponding (DSWx water polygons) drawn as a thin water body on the terrain. */
export function setWater(fc, depth = 0.8) {
  const feats = (fc && fc.features ? fc.features : []).map((f) => ({ ...f, properties: { ...f.properties, color: COLORS.water, h: depth } }));
  put("twin-water", { type: "FeatureCollection", features: feats });
}

export function clearAll() {
  stop();
  ["twin-trees", "twin-water", "twin-mud", "twin-path"].forEach((id) => map.getSource(id) && put(id, EMPTY));
}

export function pointInPolygon(pt, poly) {
  const rings = poly.type === "Polygon" ? [poly.coordinates[0]] : poly.coordinates.map((p) => p[0]);
  return rings.some((ring) => {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  });
}

export function stop() {
  if (raf !== null) cancelAnimationFrame(raf); raf = null;
  if (settlePlayback) { const finish = settlePlayback; settlePlayback = null; finish({ cancelled: true }); }
}

/**
 * Animate a huayco front down the DEM path. With vegetation, the front narrows and stops inside the
 * first planted zone (an illustrative assumption shown to the user); without it, the front runs the
 * full path and spreads into a fan at the end. Returns a promise resolved when the animation ends.
 */
// Illustrative assumption shown in the interface: inside a planted zone the front narrows by half and
// stops after this many 30 m path cells (~240 m). It is not a modeled vegetation effect.
export const ASSUMED_STOP_CELLS = 8;

export function playHuayco({ path, zones, withTrees, seconds = 14, onFrame }) {
  stop();
  const coords = path.geometry.coordinates;
  if (coords.length < 2 || !Number.isFinite(seconds) || seconds <= 0) throw new Error("A flow view needs two path points and a positive duration.");
  put("twin-path", { type: "FeatureCollection", features: [path] });
  let stopAt = coords.length - 1;
  let hit = -1;
  if (withTrees && zones.length) {
    hit = coords.findIndex((c) => zones.some((z) => pointInPolygon(c, z.geometry)));
    if (hit >= 0) stopAt = Math.min(coords.length - 1, hit + ASSUMED_STOP_CELLS);
  }
  // Geometry and zone intersections are invariant during playback: build them once.
  const inside = coords.map(c => withTrees && zones.some(z => pointInPolygon(c, z.geometry)));
  const cells = coords.map((c, i) => {
    const radius = (18 + 50 * i / Math.max(1, coords.length - 1)) * (inside[i] ? 0.5 : 1);
    return circle(c[0], c[1], radius, 10);
  });
  const t0 = performance.now();
  let lastIndex = -1, lastFrame = -Infinity;
  return new Promise((resolve) => {
    settlePlayback = resolve;
    const frame = (now) => {
      const prog = Math.min(1, (now - t0) / (seconds * 1000));
      const idx = Math.max(1, Math.round(prog * stopAt));
      if (prog < 1 && (idx === lastIndex || now - lastFrame < 1000 / 24)) { raf = requestAnimationFrame(frame); return; }
      lastIndex = idx; lastFrame = now;
      const feats = [];
      for (let i = 0; i <= idx; i += Math.max(1, Math.ceil((idx + 1) / 120))) {
        const front = i > idx - 6;
        feats.push({ type: "Feature", geometry: cells[i], properties: { color: front ? COLORS.mudEdge : COLORS.mud, h: front ? 4 : 2.5 } });
      }
      if (!withTrees && prog >= 1) {
        const end = coords[coords.length - 1];
        feats.push({ type: "Feature", geometry: circle(end[0], end[1], 260, 24), properties: { color: COLORS.mud, h: 1.5 } });
      }
      put("twin-mud", { type: "FeatureCollection", features: feats });
      if (onFrame) onFrame(prog, idx, stopAt, coords.length - 1, hit);
      if (prog < 1) raf = requestAnimationFrame(frame); else { raf = null; settlePlayback = null; resolve({ cancelled: false }); }
    };
    raf = requestAnimationFrame(frame);
  });
}

/** VP8 through WebCodecs when the browser supports it (frames are encoded off the main thread). */
async function webCodecsConfig(width, height, fps) {
  if (typeof VideoEncoder === "undefined" || typeof VideoFrame === "undefined") return null;
  const config = { codec: "vp8", width, height, bitrate: Math.min(8e6, Math.round(width * height * fps * 0.12)), framerate: fps };
  try { return (await VideoEncoder.isConfigSupported(config)).supported ? config : null; } catch (_) { return null; }
}

/**
 * Record the map canvas as a WebM video while `run()` plays; returns a download URL.
 * Prefers WebCodecs (VP8) + the built-in muxer (app/webm.js); falls back to MediaRecorder. Both paths copy
 * labelled frames during MapLibre's render callback and reject an empty result instead of downloading it.
 */
export async function recordVideo(run, fps = 30, label = "Illustrative planning view") {
  const canvas = map.getCanvas();
  if (recorder) throw new Error("A video is already being recorded.");
  const width = canvas.width & ~1, height = canvas.height & ~1;
  const wc = await webCodecsConfig(width, height, fps);
  if (wc) return recordWithWebCodecs(run, fps, label, canvas, wc);
  if (!canvas.captureStream || typeof MediaRecorder === "undefined") throw new Error("Video recording is not supported in this browser.");
  const mimeType = ["video/webm", "video/webm;codecs=vp8", "video/webm;codecs=vp9"].find(type => MediaRecorder.isTypeSupported(type));
  if (!mimeType) throw new Error("WebM recording is not supported in this browser.");
  // Copy while MapLibre's render callback still has a populated WebGL buffer. A separate 2D canvas
  // avoids preserveDrawingBuffer (and its permanent map cost) and keeps capture resources separate from the interactive map.
  const output = document.createElement("canvas"); output.width = canvas.width; output.height = canvas.height;
  const context = output.getContext("2d", { willReadFrequently: true });
  if (!context || !output.captureStream) throw new Error("Canvas video capture is unavailable.");
  context.fillStyle = "#f6f3ed"; context.fillRect(0, 0, output.width, output.height);
  Object.assign(recordingStats, { width: output.width, height: output.height, frames: 0, chunks: 0, bytes: 0 });
  recordingStats.encoder = "mediarecorder";
  const stream = output.captureStream(0), chunks = [];
  let frame = null, lastCopy = -Infinity, copied = 0, captureError = null;
  const started = performance.now();
  const copy = () => {
    const now = performance.now();
    if (now - lastCopy < 1000 / fps) return;
    try { context.fillRect(0, 0, output.width, output.height); context.drawImage(canvas, 0, 0); if (copied === 2) {
      const data = context.getImageData(0, 0, output.width, output.height).data;
      let low = 255, high = 0;
      for (let i = 0; i < data.length; i += 512) { low = Math.min(low, data[i]); high = Math.max(high, data[i]); }
      recordingStats.body_color_range = high - low;
    }
    context.fillStyle = "#1b2226"; context.fillRect(0, output.height - 30, output.width, 30);
    context.fillStyle = "#ffffff"; context.font = "14px sans-serif";
    context.fillText(label + " | " + ((now - started) / 1000).toFixed(1) + " s | OSM/OpenFreeMap · NASA/Copernicus", 10, output.height - 10);
    stream.getTracks()[0]?.requestFrame?.();
    copied++; recordingStats.frames = copied; recordingStats.muted = stream.getTracks()[0]?.muted; lastCopy = now; } catch (error) { captureError = error; }
  };
  const repaint = () => { map.triggerRepaint(); frame = requestAnimationFrame(repaint); };
  map.on("render", copy);
  try {
    recorder = new MediaRecorder(stream, { mimeType });
    recorder.ondataavailable = e => { if (e.data.size) { chunks.push(e.data); recordingStats.chunks++; recordingStats.bytes += e.data.size; } };
    const done = new Promise((resolve, reject) => { recorder.onstop = resolve; recorder.onerror = () => reject(new Error("Video recording failed.")); });
    done.catch(() => {});
    recorder.start(250); map.triggerRepaint(); frame = requestAnimationFrame(repaint);
    try { await run(); } finally { if (recorder.state !== "inactive") recorder.stop(); }
    await done;
    if (captureError) throw captureError;
    if (!copied) throw new Error("No map frames could be recorded.");
    const blob = new Blob(chunks, { type: "video/webm" });
    if (blob.size === 0) throw new Error("The video encoder produced no frames. Try another browser.");
    return URL.createObjectURL(blob);
  } finally {
    if (frame !== null) cancelAnimationFrame(frame);
    map.off("render", copy);
    if (recorder && recorder.state !== "inactive") recorder.stop();
    stream.getTracks().forEach(track => track.stop()); recorder = null;
    output.width = output.height = 0;
  }
}


async function recordWithWebCodecs(run, fps, label, canvas, config) {
  const { muxWebM } = await import("./webm.js");
  const output = document.createElement("canvas"); output.width = config.width; output.height = config.height;
  const context = output.getContext("2d");
  if (!context) throw new Error("Canvas video capture is unavailable.");
  for (const k of Object.keys(recordingStats)) delete recordingStats[k];
  Object.assign(recordingStats, { width: config.width, height: config.height, frames: 0, copies: 0, fresh_frames: 0, chunks: 0, bytes: 0, dropped: 0, encoder: "webcodecs-vp8" });
  const encoded = [];
  let encodeError = null, frame = null, ticker = null, copied = 0, encodedFrames = 0, fresh = false;
  const encoder = new VideoEncoder({
    output: (chunk) => {
      const data = new Uint8Array(chunk.byteLength); chunk.copyTo(data);
      encoded.push({ data, timestampUs: chunk.timestamp, key: chunk.type === "key" });
      recordingStats.chunks++; recordingStats.bytes += data.length;
    },
    error: (e) => { encodeError = e; },
  });
  encoder.configure(config);
  recorder = { state: "recording", stop() {} }; // marks a recording in progress (one at a time)
  const started = performance.now();
  // The render callback only copies the latest map image (the WebGL buffer is valid only then);
  // a fixed-rate clock encodes the copy, so the video keeps real time even when rendering is slow.
  const copy = () => {
    if (encodeError) return;
    try {
      context.fillStyle = "#f6f3ed"; context.fillRect(0, 0, output.width, output.height);
      context.drawImage(canvas, 0, 0);
      copied++; fresh = true; recordingStats.copies = copied;
    } catch (error) { encodeError = error; }
  };
  const tick = () => {
    if (encodeError || !copied) return;
    if (encoder.encodeQueueSize > 8) { recordingStats.dropped++; return; } // back-pressure: never queue unbounded frames
    const now = performance.now();
    try {
      context.fillStyle = "#1b2226"; context.fillRect(0, output.height - 30, output.width, 30);
      context.fillStyle = "#ffffff"; context.font = "14px sans-serif";
      context.fillText(label + " | " + ((now - started) / 1000).toFixed(1) + " s | OSM/OpenFreeMap · NASA/Copernicus", 10, output.height - 10);
      const vf = new VideoFrame(output, { timestamp: Math.round((now - started) * 1000) });
      encoder.encode(vf, { keyFrame: encodedFrames % (fps * 2) === 0 });
      vf.close();
      encodedFrames++; recordingStats.frames = encodedFrames;
      if (fresh) { fresh = false; recordingStats.fresh_frames = (recordingStats.fresh_frames || 0) + 1; }
    } catch (error) { encodeError = error; }
  };
  const repaint = () => { map.triggerRepaint(); frame = requestAnimationFrame(repaint); };
  map.on("render", copy);
  try {
    map.triggerRepaint(); frame = requestAnimationFrame(repaint);
    ticker = setInterval(tick, 1000 / fps);
    await run();
    tick();
    clearInterval(ticker); ticker = null;
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
    map.off("render", copy);
    if (encoder.state === "configured") await encoder.flush();
    if (encodeError) throw new Error("Video encoding failed: " + (encodeError.message || encodeError));
    if (!copied || !encodedFrames) throw new Error("No map frames could be recorded.");
    if (!encoded.length) throw new Error("The video encoder produced no frames. Try another browser.");
    const bytes = muxWebM(encoded, { width: config.width, height: config.height });
    return URL.createObjectURL(new Blob([bytes], { type: "video/webm" }));
  } finally {
    if (ticker !== null) clearInterval(ticker);
    if (frame !== null) cancelAnimationFrame(frame);
    map.off("render", copy);
    if (encoder.state !== "closed") encoder.close();
    recorder = null;
    output.width = output.height = 0;
  }
}

export function setMud(fc) { put("twin-mud", fc); }
export function setPath(path) { put("twin-path", path ? { type: "FeatureCollection", features: [path] } : null); }

/**
 * Export a timeline as WebM frame by frame: each frame is timeline.renderAt(i / fps), drawn after the map settles,
 * and stamped i / fps. The clip duration equals the timeline duration whatever the rendering speed (no dropped ticks).
 */
export async function recordTimeline(tl, { fps = 12, label = "Illustrative timeline", caption = () => "" } = {}) {
  if (recorder) throw new Error("A video is already being recorded.");
  const canvas = map.getCanvas();
  const width = canvas.width & ~1, height = canvas.height & ~1;
  const config = await webCodecsConfig(width, height, fps);
  if (!config) throw new Error("This browser cannot encode video frames (WebCodecs VP8 is required for timeline export).");
  const { muxWebM } = await import("./webm.js");
  const output = document.createElement("canvas"); output.width = width; output.height = height;
  const ctx = output.getContext("2d");
  const encoded = [];
  let encodeError = null;
  const encoder = new VideoEncoder({
    output: (chunk) => { const d = new Uint8Array(chunk.byteLength); chunk.copyTo(d); encoded.push({ data: d, timestampUs: chunk.timestamp, key: chunk.type === "key" }); },
    error: (e) => { encodeError = e; },
  });
  encoder.configure(config);
  recorder = { state: "recording", stop() {} };
  for (const k of Object.keys(recordingStats)) delete recordingStats[k];
  const n = Math.round(tl.total * fps) + 1;
  Object.assign(recordingStats, { encoder: "webcodecs-vp8-frame-by-frame", fps, frames: 0, planned_frames: n, timeline_s: tl.total, settle_timeouts: 0, width, height });
  const settle = () => new Promise((resolve) => {
    let done = false;
    const finish = (timedOut) => { if (done) return; done = true; if (timedOut) recordingStats.settle_timeouts++; resolve(); };
    map.once("idle", () => finish(false));
    setTimeout(() => finish(true), 4000);
    map.triggerRepaint();
  });
  const capture = () => new Promise((resolve) => { map.once("render", () => { ctx.fillStyle = "#f6f3ed"; ctx.fillRect(0, 0, width, height); ctx.drawImage(canvas, 0, 0); resolve(); }); map.triggerRepaint(); });
  try {
    for (let i = 0; i < n; i++) {
      if (encodeError) throw encodeError;
      const s = tl.renderAt(i / fps);
      await settle();
      await capture();
      ctx.fillStyle = "#1b2226"; ctx.fillRect(0, height - 30, width, 30);
      ctx.fillStyle = "#ffffff"; ctx.font = "14px sans-serif";
      ctx.fillText(`${label} | ${caption(s)} | OSM/OpenFreeMap · NASA/Copernicus`, 10, height - 10);
      while (encoder.encodeQueueSize > 6) await new Promise((r) => setTimeout(r, 5)); // back-pressure, never drop
      const vf = new VideoFrame(output, { timestamp: Math.round((i * 1e6) / fps), duration: Math.round(1e6 / fps) });
      encoder.encode(vf, { keyFrame: i % (fps * 2) === 0 });
      vf.close();
      recordingStats.frames = i + 1;
    }
    await encoder.flush();
    if (encodeError) throw encodeError;
    if (encoded.length !== n) throw new Error(`The encoder returned ${encoded.length} of ${n} frames.`);
    recordingStats.duration_s = (n - 1) / fps + 1 / fps;
    recordingStats.bytes = encoded.reduce((a, e) => a + e.data.length, 0);
    return URL.createObjectURL(new Blob([muxWebM(encoded, { width, height, frameMs: 1000 / fps })], { type: "video/webm" }));
  } finally {
    if (encoder.state !== "closed") encoder.close();
    recorder = null;
    output.width = output.height = 0;
  }
}
