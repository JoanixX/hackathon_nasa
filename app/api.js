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
  const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts });
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
