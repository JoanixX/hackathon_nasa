// Bounded browser timings. Durations and page-relative marks have separate fields.
const queue = [];
const LIMIT = 600;
const sessionId = crypto.randomUUID();
export const marks = [];
export function mark(name, detail = "", durationMs = null) {
  const e = { name, ms: Math.round(performance.now()), detail: String(detail).slice(0, 200) };
  if (durationMs !== null && Number.isFinite(durationMs)) e.duration_ms = Math.max(0, Math.round(durationMs));
  marks.push(e); if (marks.length > LIMIT) marks.shift();
  queue.push(e); if (queue.length > LIMIT) queue.shift();
  if (new URLSearchParams(location.search).has("perf")) console.info("[perf]", e);
}
export async function timed(name, fn) {
  const t0 = performance.now();
  try { return await fn(); } finally { mark(name, "", performance.now() - t0); }
}
function flush() {
  if (!queue.length) return;
  const body = JSON.stringify({ session_id: sessionId, events: queue.splice(0, 200) });
  if (!(navigator.sendBeacon && navigator.sendBeacon("/api/client-perf", new Blob([body], { type: "application/json" })))) {
    fetch("/api/client-perf", { method: "POST", headers: { "Content-Type": "application/json" }, body, keepalive: true }).catch(() => {});
  }
}
if (typeof PerformanceObserver !== "undefined") {
  for (const type of ["longtask", "paint", "resource"]) {
    try {
      new PerformanceObserver(list => {
        for (const entry of list.getEntries()) {
          if (type === "resource") {
            const url = new URL(entry.name, location.href);
            if (url.pathname === "/api/client-perf") continue;
            mark("resource." + (url.origin === location.origin ? "local" : "external"), url.host + url.pathname.slice(0, 100), entry.duration);
          } else mark(type + "." + entry.name, "", entry.duration);
        }
      }).observe({ type, buffered: true });
    } catch (_) { /* Optional timing types vary by browser. */ }
  }
}
setInterval(flush, 2000);
addEventListener("pagehide", flush);
