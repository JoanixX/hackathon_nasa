// Camera AR: MindAR image-target registration with an A-Frame scene built from the validated scene spec.
// The DEM mesh, zones, seed deposition and future vegetation use the same tabletop frame as the server.
const C = window.RaizCore;
const AR_LIBS = ["https://aframe.io/releases/1.6.0/aframe.min.js", "https://cdn.jsdelivr.net/npm/mind-ar@1.2.5/dist/mindar-image-aframe.prod.js"];
const $ = (id) => document.getElementById(id);
let libs = null;
let arState = "idle";
const TEXT = {
  idle: "Idle", capability_check: "Checking camera support…", permission_request: "Waiting for camera permission…",
  registering: "Point the camera at the printed RAÍZ-SAR AI target.", active: "Tracking the target. The scenario is registered to the tabletop target.",
  tracking_lost: "Target lost. Overlays are hidden until the target is in view again.",
  unsupported: "Camera AR needs HTTPS or localhost and a browser with camera access.",
  permission_denied: "Camera permission was denied. Allow the camera and try again, or use the 3D terrain view.",
  failed: "AR could not start.", ended: "AR session ended.", preview: "",
};

function loadScript(src) {
  return new Promise((res, rej) => { const s = document.createElement("script"); s.src = src; s.onload = res; s.onerror = () => rej(new Error(`Could not load ${src}`)); document.head.append(s); });
}
function loadLibs() {
  if (!libs) libs = loadScript(AR_LIBS[0]).then(register).then(() => (window.MINDAR && window.MINDAR.IMAGE ? null : loadScript(AR_LIBS[1])));
  return libs;
}

function event(evt, detail) {
  const prev = arState;
  arState = C.arTransition(arState, evt);
  $("ar-state").textContent = TEXT[arState] + (detail ? ` ${detail}` : "");
  document.body.dataset.arState = arState;
  const root = document.querySelector("#raiz-root");
  if (root && root.object3D) root.object3D.visible = arState === "active";
  if (arState === "ended" && prev !== "ended") teardown();
}

export function endForStalePlan() { if (arState !== "idle" && arState !== "ended") event("stale_plan"); }

function register() {
  const AF = window.AFRAME;
  if (!AF || AF.components["raiz-scene"]) return;
  const THREE = AF.THREE; // A-Frame's bundled three.js; no second copy is loaded
  const colors = { shrub_tree_small: 0x5f9f45, broad_tree: 0x4f8a3a, dry_forest_tree: 0x7aa04a };
  AF.registerComponent("raiz-scene", {
    init() {
      this.spec = window.__raizScene; this.stageIndex = 3; this.roots = false; this.evidence = true;
      this.group = new THREE.Group(); this.el.setObject3D("raiz", this.group); this.build();
    },
    h(x, y) { return C.terrainHeightAt(this.spec.terrain_grid, this.spec.frame, x, y); },
    build() {
      const s = this.spec, f = s.frame, g = s.terrain_grid;
      // Terrain: DEM mesh when available, otherwise the declared flat plane.
      const geo = new THREE.PlaneGeometry(1, f.target_aspect, g ? g.nx - 1 : 1, g ? g.ny - 1 : 1);
      if (g) {
        const pos = geo.attributes.position;
        for (let i = 0; i < pos.count; i++) pos.setZ(i, this.h(pos.getX(i), pos.getY(i)));
        geo.computeVertexNormals();
      }
      // The real place: a snapshot of the map (streets, buildings, quebradas, colours) draped on the DEM.
      const X = window.__raizExtras || {};
      const terrainMat = X.texture
        ? new THREE.MeshLambertMaterial({ map: new THREE.TextureLoader().load(X.texture) })
        : new THREE.MeshLambertMaterial({ color: 0xc9b48f, transparent: true, opacity: 0.9 });
      this.terrain = new THREE.Mesh(geo, terrainMat);
      this.terrainTexture = terrainMat.map || null;
      $("btn-ar-texture").disabled=!this.terrainTexture;
      $("btn-ar-texture").setAttribute("aria-pressed",String(!!this.terrainTexture));
      this.group.add(this.terrain);
      this.toAR = makeProjector(s.frame);
      this.buildWater(X.ponding);
      this.mudGroup = new THREE.Group(); this.group.add(this.mudGroup);
      this.path = X.path || null;
      // The evidence image is draped only over its own registered bounds, never stretched to the target.
      this.evidenceMesh = null;
      if (s.evidence_overlay) {
        const o = s.evidence_overlay;
        const w = Math.abs(o.x1 - o.x0), hh = Math.abs(o.y1 - o.y0);
        const eg = new THREE.PlaneGeometry(w, hh, 48, 48);
        eg.translate((o.x0 + o.x1) / 2, (o.y0 + o.y1) / 2, 0);
        const ep = eg.attributes.position;
        for (let i = 0; i < ep.count; i++) ep.setZ(i, this.h(ep.getX(i), ep.getY(i)) + 0.001);
        this.evidenceMesh = new THREE.Mesh(eg, new THREE.MeshBasicMaterial({ map: new THREE.TextureLoader().load(o.image), transparent: true, opacity: 0.8 }));
        this.group.add(this.evidenceMesh);
      }
      this.group.add(new THREE.AmbientLight(0xffffff, 0.75));
      const sun = new THREE.DirectionalLight(0xffffff, 0.6); sun.position.set(-1, 1, 1.2); this.group.add(sun);
      for (const z of s.zones) {
        const pts = z.outline.map(([x, y]) => new THREE.Vector3(x, y, this.h(x, y) + 0.003));
        const col = z.eligibility === "eligible" ? 0xe2a33b : z.eligibility === "excluded" ? 0xe2654f : 0xd9c08f;
        this.group.add(new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color: col })));
      }
      const dep = new THREE.InstancedMesh(new THREE.CircleGeometry(0.003, 8), new THREE.MeshBasicMaterial({ color: 0xf4d35e }), Math.max(1, s.deposition_points.length));
      const m4 = new THREE.Matrix4();
      s.deposition_points.forEach(([x, y], i) => { m4.makeTranslation(x, y, this.h(x, y) + 0.004); dep.setMatrixAt(i, m4); });
      dep.count = s.deposition_points.length; this.dep = dep;
      const n = Math.max(1, s.placements.length);
      const trunk = new THREE.CylinderGeometry(0.15, 0.2, 1, 6); trunk.rotateX(Math.PI / 2); trunk.translate(0, 0, 0.5);
      const root = new THREE.ConeGeometry(1, 1, 6); root.rotateX(-Math.PI / 2); root.translate(0, 0, -0.5);
      // Crown shapes per species model: broad-flat (algarrobo), rounded (sapote), umbrella (faique), cone (others).
      const crowns = {
        broad_flat: (() => { const g = new THREE.CylinderGeometry(1, 0.8, 1, 12); g.rotateX(Math.PI / 2); g.translate(0, 0, 0.5); return g; })(),
        rounded: (() => { const g = new THREE.SphereGeometry(0.5, 12, 8); g.translate(0, 0, 0.5); return g; })(),
        umbrella: (() => { const g = new THREE.CylinderGeometry(1, 0.95, 0.25, 14); g.rotateX(Math.PI / 2); g.translate(0, 0, 0.88); return g; })(),
        cone: (() => { const g = new THREE.ConeGeometry(1, 1, 7); g.rotateX(Math.PI / 2); g.translate(0, 0, 0.5); return g; })(),
      };
      this.trunks = new THREE.InstancedMesh(trunk, new THREE.MeshLambertMaterial({ color: 0x6b4a2b }), n);
      this.crowns = Object.fromEntries(Object.entries(crowns).map(([k, g]) => [k, new THREE.InstancedMesh(g, new THREE.MeshLambertMaterial({ color: 0xffffff }), n)]));
      this.roots = new THREE.InstancedMesh(root, new THREE.MeshBasicMaterial({ color: 0xa0732f, transparent: true, opacity: 0.45 }), n);
      this.rootsOn = false;
      this.species = Object.fromEntries((X.species || []).map((sp) => [sp.species_id, sp.model || {}]));
      for (const mesh of [this.trunks, this.roots, dep, ...Object.values(this.crowns)]) { mesh.frustumCulled = false; this.group.add(mesh); }
      for (const old of this.el.querySelectorAll(".raiz-zone")) old.remove();
      s.zones.forEach((z, i) => { const e = document.createElement("a-entity"); e.setAttribute("class", "raiz-zone clickable"); e.setAttribute("raiz-zone", `index: ${i}`); this.el.appendChild(e); });
      this.apply();
    },
    apply() {
      const s = this.spec, f = s.frame, st = s.stages[this.stageIndex];
      const vis = C.visiblePlacements(s.placements, st);
      const h = C.markerHeight(st, f);
      // Symbolic marker width (not to scale): readable markers that grow with the canopy stage.
      const r = 0.0018 + 0.0035 * Math.min(1, st.canopy_radius_m / 1.5);
      const m = new THREE.Matrix4(), q = new THREE.Quaternion(), col = new THREE.Color();
      const counts = { broad_flat: 0, rounded: 0, umbrella: 0, cone: 0 };
      vis.forEach((p, i) => {
        const model = this.species[p.species_id] || {};
        const shape = counts[model.crown_shape] !== undefined ? model.crown_shape : "cone";
        const tr = model.trunk_ratio || 0.45;
        const rr = r * ((model.crown_radius_m || 3) / 3);
        const z0 = this.h(p.x, p.y) + 0.002, th = h * tr;
        m.compose(new THREE.Vector3(p.x, p.y, z0), q, new THREE.Vector3(rr * 0.35, rr * 0.35, Math.max(th, 1e-4))); this.trunks.setMatrixAt(i, m);
        const k = counts[shape]++;
        m.compose(new THREE.Vector3(p.x, p.y, z0 + th * 0.6), q, new THREE.Vector3(rr, rr, Math.max(h - th * 0.6, 1e-4)));
        this.crowns[shape].setMatrixAt(k, m);
        col.set(model.crown_color || "#4f8a3a"); this.crowns[shape].setColorAt(k, col);
        m.compose(new THREE.Vector3(p.x, p.y, z0), q, new THREE.Vector3(rr * 0.7, rr * 0.7, Math.max(h * 0.6, 1e-4))); this.roots.setMatrixAt(i, m);
      });
      this.trunks.count = vis.length;
      for (const [k, mesh] of Object.entries(this.crowns)) { mesh.count = counts[k]; mesh.instanceMatrix.needsUpdate = true; if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true; }
      this.roots.count = this.rootsOn && st.horizon_months >= 6 ? vis.length : 0;
      for (const mesh of [this.trunks, this.roots]) mesh.instanceMatrix.needsUpdate = true;
      this.dep.visible = this.stageIndex === 0;
      if (this.evidenceMesh) this.evidenceMesh.visible = this.evidence;
      $("ar-caption").textContent = `${st.horizon_months === 0 ? "Seed deposition" : `${st.horizon_months} months`}: ${st.caption} (${vis.length} markers${this.rootsOn && st.horizon_months >= 6 ? "; " + s.labels.roots : ""})`;
      document.querySelectorAll("[data-ar-h]").forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.arH) === this.stageIndex)));
      document.body.dataset.arStage = String(this.stageIndex);
      document.body.dataset.arVisible = String(vis.length);
    },
    buildWater(ponding) {
      if (!ponding || !ponding.features || !this.toAR) return;
      const mat = new THREE.MeshBasicMaterial({ color: 0x2f7fd8, transparent: true, opacity: 0.75, side: THREE.DoubleSide });
      for (const f of ponding.features.slice(0, 250)) {
        const ring = f.geometry.type === "Polygon" ? f.geometry.coordinates[0] : f.geometry.coordinates[0][0];
        const pts = ring.map(([lo, la]) => this.toAR(lo, la));
        if (pts.some(([x, y]) => Math.abs(x) > 0.5 || Math.abs(y) > s_aspect(this.spec) / 2)) continue;
        const shape = new THREE.Shape(pts.map(([x, y]) => new THREE.Vector2(x, y)));
        const [cx, cy] = pts[0];
        const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), mat);
        mesh.position.z = this.h(cx, cy) + 0.003;
        this.group.add(mesh);
      }
    },
    playHuayco(withTrees) {
      if (!this.path || !this.toAR) { $("ar-caption").textContent = "Open the huayco view on the map first so the downhill path is known."; return; }
      while (this.mudGroup.children.length) this.mudGroup.remove(this.mudGroup.children[0]);
      const pts = this.path.geometry.coordinates.map(([lo, la]) => this.toAR(lo, la));
      const zones = withTrees ? this.spec.zones.filter((z) => z.species_id) : [];
      const inside = ([x, y]) => zones.some((z) => { let c = false; const o = z.outline; for (let i = 0, j = o.length - 1; i < o.length; j = i++) { if ((o[i][1] > y) !== (o[j][1] > y) && x < ((o[j][0] - o[i][0]) * (y - o[i][1])) / (o[j][1] - o[i][1]) + o[i][0]) c = !c; } return c; });
      let stopAt = pts.length - 1;
      if (withTrees) { const hit = pts.findIndex(inside); if (hit >= 0) stopAt = Math.min(pts.length - 1, hit + 8); }
      const mat = new THREE.MeshLambertMaterial({ color: 0x7b5a3a });
      const geo = new THREE.CylinderGeometry(1, 1, 1, 10); geo.rotateX(Math.PI / 2);
      const mud = new THREE.InstancedMesh(geo, mat, pts.length + 1); mud.frustumCulled = false; mud.count = 0;
      this.mudGroup.add(mud);
      const t0 = performance.now(), dur = 9000, m4 = new THREE.Matrix4(), q = new THREE.Quaternion();
      const step = (now) => {
        const prog = Math.min(1, (now - t0) / dur);
        const idx = Math.round(prog * stopAt);
        for (let i = 0; i <= idx; i++) {
          const [x, y] = pts[i];
          let rad = 0.004 + 0.01 * (i / pts.length);
          if (withTrees && inside(pts[i])) rad *= 0.5;
          m4.compose(new THREE.Vector3(x, y, this.h(x, y) + 0.002), q, new THREE.Vector3(rad, rad, 0.004)); mud.setMatrixAt(i, m4);
        }
        mud.count = idx + 1; mud.instanceMatrix.needsUpdate = true;
        if (prog < 1) requestAnimationFrame(step);
        else $("ar-caption").textContent = withTrees ? "Huayco with the trees: the front stops inside the planted zone (illustrative assumption)." : "Huayco without the trees: the front runs the whole downhill path.";
      };
      requestAnimationFrame(step);
    },
    setStage(i) { this.stageIndex = Math.max(0, Math.min(3, i)); this.apply(); },
    setRoots(on) { this.rootsOn = on; this.apply(); },
    setEvidence(on) { this.evidence = on; this.apply(); },
    setTexture(on) {
      this.terrain.material.map=on?this.terrainTexture:null;
      this.terrain.material.color.set(on&&this.terrainTexture?0xffffff:0xc9b48f);
      this.terrain.material.needsUpdate=true;
    },
  });
  AF.registerComponent("raiz-zone", {
    schema: { index: { type: "int" } },
    init() {
      const z = window.__raizScene.zones[this.data.index];
      const shape = new THREE.Shape(z.outline.map(([x, y]) => new THREE.Vector2(x, y)));
      const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.02, depthWrite: false }));
      mesh.position.z = 0.03;
      this.el.setObject3D("mesh", mesh);
      this.el.addEventListener("click", () => {
        $("ar-zone-info").textContent = `${z.sector_name}: ${z.eligibility.replaceAll("_", " ")}; seeds released ${C.formatCount(z.seeds_released)}; expected established ${C.formatCount(z.expected_established)} under the entered assumptions.`;
        document.body.dataset.arZone = z.sector_id;
      });
    },
  });
}

function s_aspect(spec) { return spec.frame.target_aspect; }

/** Lon/lat -> tabletop coordinates through the frame footprint (linear; the area is a few km wide). */
function makeProjector(frame) {
  const b = frame.bbox_lonlat;
  if (!b) return null;
  return (lon, lat) => [((lon - b[0]) / (b[2] - b[0])) - 0.5, ((lat - b[1]) / (b[3] - b[1])) * frame.target_aspect - frame.target_aspect / 2];
}

function comp() { const e = document.querySelector("[raiz-scene]"); return e && e.components["raiz-scene"]; }

export function wireHud() {
  $("btn-ar-texture").addEventListener("click",ev=>{const on=ev.currentTarget.getAttribute("aria-pressed")!=="true";ev.currentTarget.setAttribute("aria-pressed",String(on));comp()?.setTexture(on);});
  document.querySelectorAll("[data-ar-h]").forEach((b) => b.addEventListener("click", () => { const c = comp(); if (c) c.setStage(Number(b.dataset.arH)); }));
  $("btn-ar-roots").addEventListener("click", (ev) => { const on = ev.currentTarget.getAttribute("aria-pressed") !== "true"; ev.currentTarget.setAttribute("aria-pressed", String(on)); const c = comp(); if (c) c.setRoots(on); });
  $("btn-ar-evidence").addEventListener("click", (ev) => { const on = ev.currentTarget.getAttribute("aria-pressed") !== "true"; ev.currentTarget.setAttribute("aria-pressed", String(on)); const c = comp(); if (c) c.setEvidence(on); });
  $("btn-ar-exit").addEventListener("click", () => event("end"));
  document.querySelectorAll("[data-ar-huayco]").forEach((b) => b.addEventListener("click", () => { const c = comp(); if (c) c.playHuayco(b.dataset.arHuayco === "trees"); }));
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("ar-overlay").hidden) event("end"); });
}

function teardown() {
  const scene = document.querySelector("#ar-container a-scene");
  if (scene) { try { const sys = scene.systems && scene.systems["mindar-image-system"]; if (sys) sys.stop(); } catch (_) {} scene.remove(); }
  document.querySelectorAll("video").forEach((v) => { if (v.srcObject) v.srcObject.getTracks().forEach((t) => t.stop()); v.remove(); });
  $("ar-overlay").hidden = true;
  arState = "idle"; document.body.dataset.arState = "idle";
}

export async function startAR(scene, extras = {}) {
  window.__raizScene = scene;
  window.__raizExtras = extras;
  $("ar-overlay").hidden = false;
  $("ar-labels").textContent = [scene.labels.future, scene.labels.scale, scene.labels.marker, scene.frame.terrain,
    scene.evidence_overlay ? scene.evidence_overlay.label : ""].filter(Boolean).join(". ");
  $("btn-ar-exit").focus();
  event("start");
  if (!(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia)) { event("unsupported"); return; }
  event("supported");
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" }, audio: false });
    stream.getTracks().forEach((t) => t.stop());
  } catch (e) {
    if (e && (e.name === "NotAllowedError" || e.name === "SecurityError")) event("denied");
    else event("error", e && e.name === "NotFoundError" ? "No camera was found." : (e && e.message) || "Camera unavailable.");
    return;
  }
  event("granted");
  try { await loadLibs(); } catch (e) { event("error", e.message); return; }
  const c = $("ar-container");
  c.replaceChildren();
  c.insertAdjacentHTML("beforeend",
    '<a-scene mindar-image="imageTargetSrc: /assets/ar/target.mind; autoStart: true; uiScanning: no; uiLoading: no; uiError: no; filterMinCF: 0.0001; filterBeta: 0.001" ' +
    'color-space="sRGB" renderer="colorManagement: true; antialias: true" vr-mode-ui="enabled: false" device-orientation-permission-ui="enabled: false" embedded>' +
    '<a-camera position="0 0 0" look-controls="enabled: false" cursor="rayOrigin: mouse; fuse: false" raycaster="objects: .clickable"></a-camera>' +
    '<a-entity mindar-image-target="targetIndex: 0" id="raiz-anchor"><a-entity id="raiz-root" raiz-scene></a-entity></a-entity></a-scene>');
  const sc = c.querySelector("a-scene");
  sc.addEventListener("arReady", () => { document.body.dataset.arReady = "1"; });
  sc.addEventListener("arError", (ev) => event("error", ev && ev.detail && ev.detail.error ? String(ev.detail.error) : ""));
  const anchor = c.querySelector("#raiz-anchor");
  anchor.addEventListener("targetFound", () => event("target_found"));
  anchor.addEventListener("targetLost", () => event("target_lost"));
}
