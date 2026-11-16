import { mark } from "./perf.js";
// Same-origin API helpers and job polling with stale-response rejection.
const C = window.RaizCore;

export class ApiError extends Error {
  constructor(message, status, body, retryAfter) {
    super(message);
    this.status = status;
    this.body = body;
    this.retryAfter = retryAfter;
  }
}

export async function api(path, opts = {}) {
  const started = performance.now();
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
  mark("api.request", path.split("?")[0] + " " + res.status + " " + (res.headers.get("X-Request-ID") || ""), performance.now() - started);
  let body = null;
  try { body = await res.json(); } catch (_) { body = null; }
  if (!res.ok) {
    const detail = body && body.details ? " " + [].concat(body.details).slice(0, 4).join("; ") : "";
    throw new ApiError(((body && body.message) || `Request failed (${res.status})`) + detail, res.status, body, res.headers.get("Retry-After"));
  }
  return body;
}

export const post = (path, data) => api(path, { method: "POST", body: JSON.stringify(data) });

export const guard = C.createVersionGuard();

/**
 * Submit a job and poll it. `bound` jobs (scene, report) are discarded if the plan on screen changed.
 * Returns the final job status, or null when the result was stale or the request failed.
 */
export async function runJob({ kind, path, body, onStatus, currentPlan, bound = false, timeoutMs = 240000 }) {
  const tok = guard.issue(kind, bound ? currentPlan() : null);
  const current = () => (bound ? currentPlan() : tok.planVersion);
  let st;
  try {
    st = await post(path, body);
  } catch (e) {
    onStatus(e.status === 429 ? `The queue is full; try again in ${e.retryAfter || "a few"} seconds.` : e.message, "error");
    return null;
  }
  const t0 = Date.now();
  let attempt = 0;
  while (!C.JOB_TERMINAL.has(st.state) && Date.now() - t0 < timeoutMs) {
    onStatus(st.state === "running" ? "Working…" : "Queued…", "busy");
    await new Promise((r) => setTimeout(r, C.backoffDelay(attempt++)));
    if (!guard.accept(tok, current())) return null;
    try { st = await api(`/api/jobs/${encodeURIComponent(st.job_id)}`); } catch (e) { onStatus(`Status unavailable: ${e.message}`, "error"); }
  }
  if (!guard.accept(tok, current(), st.plan_version === null ? undefined : st.plan_version)) {
    onStatus("A newer request replaced this result.", "info");
    return null;
  }
  if (!C.JOB_TERMINAL.has(st.state)) { onStatus(`Still ${st.state} after ${Math.round(timeoutMs / 60000)} minutes.`, "error"); return st; }
  if (st.state === "failed") onStatus(`${st.error_message || "The job failed."}`, "error");
  else if (st.state === "partial") onStatus(`Partly done: ${st.error_message || ""}`, "warn");
  else onStatus("Done.", "ok");
  return st;
}


const wait = (ms, signal) => new Promise((resolve, reject) => {
  if (signal && signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
  const t = setTimeout(resolve, ms);
  if (signal) signal.addEventListener("abort", () => { clearTimeout(t); reject(new DOMException("Aborted", "AbortError")); }, { once: true });
});

/**
 * GET evidence that the server may build in a worker: 200 returns the result; 202 returns a job that is
 * polled (with backoff, abortable) until it is ready. 503 upstream_busy is retried after Retry-After.
 */
export async function evidence(path, { signal, onStatus, timeoutMs = 180000 } = {}) {
  const t0 = Date.now();
  let attempt = 0;
  for (;;) {
    let body;
    try {
      body = await api(path, { signal });
    } catch (e) {
      if (e.status === 503 && e.body && e.body.error === "upstream_busy" && Date.now() - t0 < timeoutMs) {
        if (onStatus) onStatus("Data providers are busy; retrying…");
        await wait(1000 * Math.min(10, Number(e.retryAfter) || 2), signal);
        continue;
      }
      throw e;
    }
    if (!(body && body.job_id && body.state)) return body;
    let st = body;
    while (!C.JOB_TERMINAL.has(st.state)) {
      if (Date.now() - t0 > timeoutMs) throw new ApiError("The evidence job is still running; try again shortly.", 504, st);
      if (onStatus) onStatus(st.state === "running" ? "Extracting from the imagery…" : "Queued for extraction…");
      await wait(C.backoffDelay(attempt++), signal);
      st = await api(`/api/jobs/${encodeURIComponent(st.job_id)}`, { signal });
    }
    if (st.state === "ready" && st.result) return st.result;
    throw new ApiError(st.error_message || "The evidence job failed.", 502, st);
  }
}