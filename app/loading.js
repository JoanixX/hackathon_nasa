// Shared lazy loading and cancellation. No satellite work runs until a view requests it.
const scripts = new Map();
export function loadScript(src) {
  if (scripts.has(src)) return scripts.get(src);
  const pending = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = src; script.async = true;
    script.onload = resolve;
    script.onerror = () => { scripts.delete(src); script.remove(); reject(new Error("Could not load " + src)); };
    document.head.append(script);
  });
  scripts.set(src, pending);
  return pending;
}

/** One in-flight request per key; invalidation makes even uncancellable old results ineligible. */
export function createLoadScope() {
  let epoch = 0;
  const pending = new Map();
  return {
    reset() { epoch += 1; for (const p of pending.values()) p.controller.abort(); pending.clear(); },
    run(key, work, apply) {
      if (pending.has(key)) return pending.get(key).promise;
      const version = epoch, controller = new AbortController();
      const entry = { controller, promise: null };
      entry.promise = Promise.resolve().then(() => work(controller.signal)).then(value => {
        if (version !== epoch) return undefined;
        apply(value); return value;
      }).catch(error => { if (version === epoch && error.name !== "AbortError") throw error; }).finally(() => {
        if (pending.get(key) === entry) pending.delete(key);
      });
      pending.set(key, entry);
      return entry.promise;
    },
  };
}
