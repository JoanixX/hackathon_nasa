import { loadScript } from "./loading.js";
// Charts that each answer one question, built only when their data exist.
const charts = new Map();
const TXT = "#ece3d2", DIM = "#b4ab99", GRID = "rgba(236,227,210,0.08)";
const reduce = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

async function make(canvas, cfg) {
  try { if (!window.Chart) await loadScript("https://cdn.jsdelivr.net/npm/chart.js@4.6.1/dist/chart.umd.min.js"); }
  catch (error) { canvas.replaceWith(Object.assign(document.createElement("p"), { textContent: error.message })); return; }
  if (!canvas.isConnected) return;
  if (charts.has(canvas)) charts.get(canvas).destroy();
  const base = { animation: reduce() ? false : { duration: 250 }, responsive: true, maintainAspectRatio: false,
    plugins: { legend: { labels: { color: TXT, boxWidth: 12 } }, tooltip: { mode: "index", intersect: false } } };
  const c = new Chart(canvas, { ...cfg, options: deepMerge(base, cfg.options || {}) });
  charts.set(canvas, c);
  return c;
}

function deepMerge(a, b) {
  const out = { ...a };
  for (const [k, v] of Object.entries(b)) out[k] = v && typeof v === "object" && !Array.isArray(v) ? deepMerge(a[k] || {}, v) : v;
  return out;
}

const axis = (title) => ({ title: { display: true, text: title, color: DIM }, ticks: { color: DIM }, grid: { color: GRID } });

/** When did it rain? Daily modeled precipitation with acquisition days marked. */
export function rainChart(canvas, rain, acq, highlight) {
  const labels = rain.days.map((d) => d.date);
  const mark = (key) => {
    const s = new Set((acq && acq.datasets[key] || []).map((x) => x.date));
    return labels.map((d) => (s.has(d) ? 0 : null));
  };
  return make(canvas, {
    type: "bar",
    data: { labels, datasets: [
      { label: "Precipitation (mm/day, POWER MERRA-2)", data: rain.days.map((d) => d.mm), backgroundColor: labels.map((d) => (highlight && highlight.includes(d) ? "#4bb3ae" : "rgba(75,179,174,0.55)")) },
      { label: "Sentinel-1 RTC acquisition", type: "line", data: mark("opera_rtc"), showLine: false, pointStyle: "triangle", pointRadius: 5, borderColor: "#6db3df", backgroundColor: "#6db3df" },
      { label: "NISAR GCOV acquisition", type: "line", data: mark("nisar_gcov"), showLine: false, pointStyle: "rectRot", pointRadius: 5, borderColor: "#ece3d2", backgroundColor: "#ece3d2" },
    ] },
    options: { scales: { y: axis("mm/day"), x: { ticks: { color: DIM, maxTicksLimit: 8 }, grid: { display: false } } } },
  });
}

/** How steep is the zone? DEM slope distribution of each confirmed zone. */
export function slopeChart(canvas, zones) {
  const edges = zones[0].terrain.slope_histogram.edges_percent;
  const labels = edges.slice(0, -1).map((e, i) => (i === edges.length - 2 ? `≥ ${e}%` : `${e}–${edges[i + 1]}%`));
  const palette = ["#e2a33b", "#6db3df", "#9fd0c9", "#d9c08f", "#e2654f", "#86c06c"];
  return make(canvas, {
    type: "bar",
    data: { labels, datasets: zones.map((z, i) => {
      const cells = z.terrain.slope_histogram.cells; const tot = cells.reduce((a, b) => a + b, 0) || 1;
      return { label: z.name, data: cells.map((c) => Math.round((100 * c) / tot)), backgroundColor: palette[i % palette.length] };
    }) },
    options: { scales: { y: { ...axis("share of zone (%)"), max: 100 }, x: axis("slope (Copernicus DEM, 30 m)") } },
  });
}

/** What does the budget buy? Seeds, germination and establishment kept separate. */
export function planChart(canvas, totals) {
  return make(canvas, {
    type: "bar",
    data: { labels: ["Seeds released", "Expected germinated", "Expected established"],
      datasets: [{ label: "Count under the entered assumptions", data: [totals.seeds_released, totals.expected_germinated, totals.expected_established],
        backgroundColor: ["#f4d35e", "#9fd0c9", "#86c06c"] }] },
    options: { plugins: { legend: { display: false } }, scales: { y: axis("count"), x: { ticks: { color: DIM }, grid: { display: false } } } },
  });
}

/** How sensitive is establishment to planting delay? Only when a half-life was entered. */
export function delayChart(canvas, est) {
  return make(canvas, {
    type: "line",
    data: { labels: est.points.map((p) => `+${p.delay_days} d`),
      datasets: [["low", "Short half-life", "#e2654f"], ["central", "Entered half-life", "#e2a33b"], ["high", "Long half-life", "#86c06c"]]
        .map(([k, l, c]) => ({ label: l, data: est.points.map((p) => p[k]), borderColor: c, backgroundColor: c })) },
    options: { scales: { y: axis("established plants (count)"), x: axis("planting delay after the reference date") } },
  });
}

export function destroyAll() { charts.forEach((c) => c.destroy()); charts.clear(); }
