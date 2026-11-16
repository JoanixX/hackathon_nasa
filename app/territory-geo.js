// Pure geographic contracts for the territorial viewer. GeoJSON is always longitude, latitude.
export const EARTH_RADIUS = 6371008.8;
export const MERCATOR_CIRCUMFERENCE = 2 * Math.PI * 6371008.8;
/** Visibility and motion are hard repaint gates, even when a weather effect is selected. */
export function renderPolicy({software=false,reduced=false,visible=true,animate=false,ratio=1,quality=null}={}) {
  const native=Number.isFinite(ratio)&&ratio>=.25&&ratio<=4?ratio:1;
  const scale=[.5,.75,1].includes(quality)?quality:software?.5:1;
  return {pixelRatio:native*scale,fps:animate&&visible&&!reduced?(software?1:24):0};
}
export const PIURA_VIEWS = Object.freeze({
  region: { label: "All Piura", bounds: [-81.3284, -6.37209, -79.21004, -4.07949] },
  mountains: { label: "Andean ridges", center: [-79.62, -5.38], zoom: 11.4, bearing: -30 },
  valley: { label: "Chulucanas valley", center: [-80.16, -5.10], zoom: 12, bearing: -15 },
  huancabamba: { label: "Huancabamba", center: [-79.45, -5.24], zoom: 12.7, bearing: -25 },
  coast: { label: "Sechura coast", center: [-80.82, -5.56], zoom: 12, bearing: 0 },
});
export function validPosition(p) {
  return Array.isArray(p) && p.length >= 2 && Number.isFinite(p[0]) && Number.isFinite(p[1]) &&
    p[0] >= -180 && p[0] <= 180 && p[1] > -85 && p[1] < 85;
}
export function mercator(p, altitude = 0) {
  if (!validPosition(p) || !Number.isFinite(altitude)) throw new RangeError("Invalid geographic coordinate.");
  const lat = p[1] * Math.PI / 180;
  const unit = 1 / (MERCATOR_CIRCUMFERENCE * Math.cos(lat));
  return { x: (p[0] + 180) / 360, y: (1 - Math.asinh(Math.tan(lat)) / Math.PI) / 2, z: altitude * unit, unit };
}
export function fromMercator(x, y) {
  return [(x * 360) - 180, Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180 / Math.PI];
}
export function distanceM(a, b) {
  if (!validPosition(a) || !validPosition(b)) throw new RangeError("Invalid geographic coordinate.");
  const r = Math.PI / 180, dlat = (b[1] - a[1]) * r, dlon = (b[0] - a[0]) * r;
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dlon / 2) ** 2;
  return 2 * EARTH_RADIUS * Math.asin(Math.sqrt(Math.max(0, Math.min(1, h))));
}
function inRing(p, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [x, y] = ring[i], [u, v] = ring[j];
    if ((y > p[1]) !== (v > p[1]) && p[0] < (u - x) * (p[1] - y) / (v - y) + x) inside = !inside;
  }
  return inside;
}
export function contains(p, geom) {
  if (!validPosition(p) || !geom) return false;
  const polys = geom.type === "Polygon" ? [geom.coordinates] : geom.type === "MultiPolygon" ? geom.coordinates : [];
  return polys.some(rings => rings.length && inRing(p, rings[0]) && !rings.slice(1).some(r => inRing(p, r)));
}
export function geometryLines(g) {
  if (!g || !Array.isArray(g.coordinates)) return [];
  if (g.type === "LineString") return [g.coordinates];
  if (g.type === "MultiLineString" || g.type === "Polygon") return g.coordinates;
  if (g.type === "MultiPolygon") return g.coordinates.every(Array.isArray) ? g.coordinates.flat() : [];
  return [];
}
/** Fail closed on malformed or unbounded input, before loops or GPU allocation. */
export function usableGeometry(g) {
  const lines = geometryLines(g);
  if (!lines.length || lines.length > 128) return false;
  let count = 0;
  for (const line of lines) {
    if (!Array.isArray(line) || line.length < 2 || (count += line.length) > 12000 || !line.every(validPosition)) return false;
  }
  return true;
}
function segmentDistance(p, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1], d = dx * dx + dy * dy;
  const t = d ? Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d)) : 0;
  return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
}
export function clearOf(p, geometries, clearanceM) {
  const m = mercator(p), s = m.unit;
  for (const g of geometries) {
    if (contains(p, g)) return false;
    for (const line of geometryLines(g)) for (let i = 1; i < line.length; i++) {
      const a = mercator(line[i - 1]), b = mercator(line[i]);
      if (segmentDistance([0, 0], [(a.x - m.x) / s, (a.y - m.y) / s], [(b.x - m.x) / s, (b.y - m.y) / s]) < clearanceM) return false;
    }
  }
  return true;
}
export function vegetationCover(f) {
  const p = f.properties || {};
  return ["wood", "forest"].includes(p.class) || f.sourceLayer === "park" || f.layer?.["source-layer"] === "park" || p.class === "park" || p.subclass === "park";
}
/** Viewport-only illustration, never an inventory or a planting recommendation. */
export function vegetationSamples(features, exclusions, center, zoom, limit = 500) {
  if (!validPosition(center) || !Number.isFinite(zoom) || zoom < 13) return [];
  const cover = features.slice(0, 128).filter(f => vegetationCover(f) && usableGeometry(f.geometry));
  const blocked = exclusions.slice(0, 256).map(f => f.geometry).filter(usableGeometry);
  // An incomplete exclusion budget must not silently permit placement through omitted objects.
  if (!cover.length || exclusions.length > 256) return [];
  const anchor = mercator(center), step = zoom >= 15 ? 24 : 64, radius = Math.min(1100, 500 * 2 ** (15 - zoom));
  const gridUnit=mercator([0,-5.2]).unit; // fixed lattice: panning must not move existing illustrative trees
  let vertices = 0;
  for(const g of [...cover.map(f=>f.geometry),...blocked])for(const line of geometryLines(g)){
    vertices+=line.length;if(vertices>40000)return [];
  }
  const prepare = g => {
    const lines = geometryLines(g).map(line => line.map(p => {
      const m = mercator(p); return [(m.x-anchor.x)/anchor.unit, (m.y-anchor.y)/anchor.unit];
    }));
    const b = [Infinity,Infinity,-Infinity,-Infinity];
    for (const line of lines) for (const p of line) { b[0]=Math.min(b[0],p[0]);b[1]=Math.min(b[1],p[1]);b[2]=Math.max(b[2],p[0]);b[3]=Math.max(b[3],p[1]); }
    return { g, lines, b };
  };
  const coverIndex=cover.map(f=>prepare(f.geometry)), blockIndex=blocked.map(prepare);
  const near=(p,b,r=0)=>p[0]>=b[0]-r&&p[0]<=b[2]+r&&p[1]>=b[1]-r&&p[1]<=b[3]+r;
  const cx = Math.round(anchor.x / (gridUnit * step)), cy = Math.round(anchor.y / (gridUnit * step));
  const span = Math.ceil(radius / step), out = [];
  limit = Number.isFinite(limit) ? Math.max(0, Math.min(700, Math.floor(limit))) : 0;
  // Spiral rings prioritize near detail and keep a strict candidate budget independent of polygon size.
  let tried = 0;
  for (let ring = 0; ring <= span && out.length < limit && tried < 4096; ring++) {
    for (let x = -ring; x <= ring && out.length < limit; x++) for (let y = -ring; y <= ring && out.length < limit; y++) {
      if (ring && Math.max(Math.abs(x), Math.abs(y)) !== ring) continue;
      if (++tried > 4096) break;
      const seed = Math.abs(Math.sin((cx + x) * 127.1 + (cy + y) * 311.7));
      const mx=(cx + x + seed * .3) * step * gridUnit,my=(cy + y + seed * .2) * step * gridUnit;
      const p = fromMercator(mx,my),local=[(mx-anchor.x)/anchor.unit,(my-anchor.y)/anchor.unit];
      const clearance=12*mercator(p).unit/anchor.unit;
      if (!coverIndex.some(f => near(local,f.b)&&contains(p,f.g))) continue;
      if(blockIndex.some(f=>near(local,f.b,clearance)&&(contains(p,f.g)||f.lines.some(line=>{
        for(let i=1;i<line.length;i++)if(segmentDistance(local,line[i-1],line[i])<clearance)return true;
        return false;
      }))))continue;
      out.push({ lon: p[0], lat: p[1], height: 5 + seed * 5, radius: 2.5 + seed * 1.5, shade: seed, evidence: "illustrative" });
    }
  }
  return out;
}
/** Multiply a world-to-clip matrix by a local metric frame in JS double precision. */
export function localMatrix(matrix, origin) {
  const out = new Float32Array(16), s = origin.unit;
  for (let i = 0; i < 4; i++) {
    out[i] = matrix[i] * s; out[4 + i] = matrix[4 + i] * s; out[8 + i] = matrix[8 + i] * s;
    out[12 + i] = matrix[i] * origin.x + matrix[4 + i] * origin.y + matrix[8 + i] * (origin.z || 0) + matrix[12 + i];
  }
  return out;
}
/** Approximate solar geometry; UTC input, longitude east positive. Not a weather observation. */
export function solarPosition(date, lon, lat) {
  if (!(date instanceof Date) || !Number.isFinite(+date) || !validPosition([lon, lat])) throw new RangeError("Invalid sun input.");
  const r = Math.PI / 180, day = Math.floor((+date - Date.UTC(date.getUTCFullYear(), 0, 0)) / 864e5);
  const hour = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
  const gamma = 2 * Math.PI / 365 * (day - 1 + (hour - 12) / 24);
  const dec = .006918 - .399912 * Math.cos(gamma) + .070257 * Math.sin(gamma) - .006758 * Math.cos(2 * gamma) + .000907 * Math.sin(2 * gamma) - .002697 * Math.cos(3 * gamma) + .00148 * Math.sin(3 * gamma);
  const eq = 229.18 * (.000075 + .001868 * Math.cos(gamma) - .032077 * Math.sin(gamma) - .014615 * Math.cos(2 * gamma) - .040849 * Math.sin(2 * gamma));
  const angle = (hour * 60 + eq + 4 * lon) / 4 * r - Math.PI;
  const up = Math.sin(lat * r) * Math.sin(dec) + Math.cos(lat * r) * Math.cos(dec) * Math.cos(angle);
  const east = -Math.cos(dec) * Math.sin(angle), north = Math.cos(lat * r) * Math.sin(dec) - Math.sin(lat * r) * Math.cos(dec) * Math.cos(angle);
  return { altitude: Math.asin(Math.max(-1, Math.min(1, up))) / r, azimuth: (Math.atan2(east, north) / r + 360) % 360, direction: [east, -north, Math.max(.08, up)] };
}
