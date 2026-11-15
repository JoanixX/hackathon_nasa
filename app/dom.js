// Small DOM helpers. Text always goes through textContent; model or imported text is never parsed as HTML.
export const $ = (id) => document.getElementById(id);

export function el(tag, attrs, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) if (c !== null && c !== undefined && c !== false) e.append(c instanceof Node ? c : document.createTextNode(String(c)));
  return e;
}

const BADGE = { observed: ["b-observed", "observed"], derived: ["b-derived", "derived"], modeled: ["b-modeled", "modeled"],
  ai_generated: ["b-ai", "AI-generated"], illustrative: ["b-illustrative", "illustrative"], unknown: ["b-unknown", "unknown"],
  simulated: ["b-sim", "simulated"], fixture: ["b-sim", "synthetic demo"] };

export function badge(cls) {
  const [c, t] = BADGE[cls] || ["b-unknown", cls];
  return el("span", { class: `badge ${c}`, title: `Evidence class: ${t}` }, t);
}

export function announce(msg) { $("status-live").textContent = msg; }

let toastTimer = null;
export function toast(msg) {
  const t = $("toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, 5000);
  announce(msg);
}

/** A status line that the job runner updates. */
export function statusLine() {
  const p = el("p", { class: "note", role: "status" });
  p.set = (msg, kind) => { p.textContent = msg; p.className = kind === "error" ? "errline" : kind === "warn" ? "warnline" : "note"; };
  return p;
}

export function explain(text) {
  const d = el("details", { class: "glossary" }, el("summary", { text: "What is this?" }), el("p", { text }));
  return d;
}
