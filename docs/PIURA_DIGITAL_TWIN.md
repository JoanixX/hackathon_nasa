# Piura territorial digital twin — implementation, sources and verification

Date: November 15, 2026, America/Lima. This is a local implementation within RAÍZ-SAR AI, not a new application or a certified reconstruction. [ADR 0005](decisions/0005-piura-territorial-view.md) records the architecture comparison and decision.

## Run and use

Start the existing stack with `docker compose up -d --build`, then open <http://localhost:8765>. Select **3D territory**. The existing workflow panel gains territorial controls: all-region framing, Andean ridges, Chulucanas valley, Huancabamba and Sechura navigation; aerial/perspective cameras; mapped buildings, cover materials, terrain shading, illustrative trees and waterway ripples; optional visual weather and sun date/time. These named locations are exploration locators, not surveyed hazard/planting boundaries.

Drag to pan, right-drag/Ctrl-drag to rotate and tilt, scroll/pinch to zoom, or use the existing navigation control. **All Piura** restores regional framing. Default terrain exaggeration is **×1**; optional ×3/×6 remain explicitly labelled. Enable **Inspect coordinates / element** and click the map for WGS84 coordinates, mapped element metadata, height-estimation status and a separate source DSM query. Disable inspection while drawing. The existing Zones workflow retains geographic polygons with 4–8 chosen vertices, editing and server validation.

**Animate effects** is opt-in and respects reduced-motion preferences. Rain/sky presets and flowing ripples are visual scenarios, not observations, forecasts, streamflow estimates or hydraulic simulations. Do not derive water depth, velocity, tree survival or hazard reduction from these effects. Real AI inference and actual camera AR continue through the existing Future workflow; this territorial work does not certify physical-device AR, NISAR water classification or the previously open WebM export gate.

## What changed

| Surface | Behaviour |
| --- | --- |
| `app/map.js` | Preserve regional zoom on entering 3D; explicit tile-cache bounds; no zoom-based building-height deformation; terrain tint/shading beneath mapped cover; independent territorial palette; ordinary map restoration |
| `app/territory-geo.js` | Bounded coordinate/geometry contracts, metre-preserving local Mercator frame, geographic holes, clearance envelopes, deterministic world-anchored illustrative vegetation and approximate sun geometry |
| `app/territory-gl.js` | One shared WebGL2 context; instanced trunk/crown mesh; batched per-segment waterway ripple shader; screen-space GPU visual rain; explicit allocations and cleanup |
| `app/territory.js` | Lazy compact controls, close-up refresh, source-elevation inspection with abort/timeout, visibility/reduced-motion handling, context-loss recovery and disposal |
| `raiz_sar/territory.py` and point API | Finite/in-region position checks; source-aware DSM sampling that keeps missing values null; fully validated tile plans before I/O |
| `tools/prepare_twin.py` | Reproducible bounded terrain package with tile hashes, source/CRS/terms, vertical scale, coverage audit and limitations |

No library was added or upgraded. The existing MapLibre 5.24.1 and Python scientific/GIS stack are retained. The three requested specialist skills were unavailable; the owner explicitly approved using available geospatial/research/QA alternatives. Their instructions are local resources, not new public project rules.

## Coordinates and scale

- Input/selection: longitude, latitude in WGS84, EPSG:4326, always in GeoJSON axis order.
- Display tiles: EPSG:3857, 256 × 256 Terrarium PNG. Formula: `height = R × 256 + G + B / 256 − 32768` metres. Source spacing is one arc-second, approximately 30 m near Piura; greater screen zoom does not create finer observations.
- Source elevations: Copernicus DSM orthometric heights relative to EGM2008, EPSG:3855. Surface includes canopy/structures. It is not a bare-earth DTM. No geoid-to-ellipsoid conversion is applied: do not combine ellipsoidal GNSS heights without a datum transformation.
- Local custom meshes use a double-precision geographic origin, a latitude-dependent Mercator metres-to-world factor and local float buffers. Horizontal and vertical metre dimensions share that factor. Matrix multiplication is performed in JavaScript double precision before conversion to a GPU matrix.
- The regional Mercator view has projection scale distortion and no ellipsoidal curvature renderer. Per-position object scaling compensates local Mercator scale; accurate analytical areas/distances remain backend geodesic/UTM operations (Piura normally UTM 17S, EPSG:32717). A 1:1 display multiplier is not a claim of survey accuracy.
- The stored OSM Piura boundary is simplified by about 0.0005°, with source metadata and a prior discrepant independent area check. It is a study mask, not a legally authoritative cadastral boundary. See `raiz_sar/boundaries/piura_department.source.json`.

## Source investigation and actual use

Consultation date: November 15, 2026. Public portal access is not a redistribution licence. Where local accuracy, currency, formats or terms were not verified, they remain pending rather than inheriting another dataset's specification.

| Source | Resolution, accuracy and dates | Coverage/access/format/terms | Use and resource implications |
| --- | --- | --- | --- |
| [Copernicus DEM public AWS registry](https://registry.opendata.aws/copernicus-dem/), [official handbook](https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf) | GLO-30 one arc-second DSM; WGS84/EGM2008. Handbook accuracy is a product specification, not a locally verified error bound. AWS identifies its public dataset as the 2021 release; individual acquisition dates unknown here | Real Piura windows checked; anonymous COG range reads. Free public-use terms and required attribution under the Copernicus DEM licence | **Used** for real geometry, source point sampling and the package audit. Eleven pre-existing local 1° cells were available (~327 MB total, rounded); new test package only 442 KB. Browser never loads native regional rasters |
| [OpenStreetMap licence](https://www.openstreetmap.org/copyright), [OpenFreeMap integration](https://openfreemap.org/quick_start/) | Vector mapping; scale, completeness, source dates and accuracy vary. Tile generalization changes by zoom | Real regional/city/Andean mapping rendered via vector tiles; ODbL attribution and derivative-database obligations apply | **Used** for land-cover polygons, streets, water polygons and mapped waterways. Dry/intermittent waterways are not assigned animated water. Roads drape through the native terrain renderer |
| [Overture building guide](https://docs.overturemaps.org/guides/buildings/), [licensing](https://docs.overturemaps.org/attribution/) | Source roofprints/footprints; varying spatial accuracy. Existing project release pin `2026-10-21.0`; a height tag is mapped information, not necessarily a surveyed measurement | Existing range-read PMTiles → cached MVT API, zoom 13–14. Source-specific ODbL/CC BY terms and attribution are retained | **Used** from the existing integration. 3D detail appears from zoom 14 at its full metre height: supplied height, floors ×3 m estimate, otherwise 3 m display estimate. No photogrammetric facade/roof reconstruction |
| [ESA WorldCover](https://esa-worldcover.org/en/data-access) | 10 m classes for 2020/v100 and 2021/v200; differing algorithms mean their difference is not a pure change observation | Global product includes Piura in its advertised footprint; local windows not downloaded/validated. COG/WMTS/WMS; CC BY 4.0 terms on the source site | **Researched, not used**. Valuable independent coverage/forest check; a tree-cover pixel is not an individual tree location. Avoid an eager large land-cover download |
| [NASA SRTM](https://www.earthdata.nasa.gov/data/instruments/srtm) | Approx. 30 m one arc-second global product; older acquisition epoch and datum must be checked before comparison | Candidate global coverage; direct product catalog request returned 403 in the research tool. No local SRTM file verified | **Alternative, not substituted**. A second DSM adds storage and requires bias/datum/nodata comparison; no demonstrated improvement over the cached source |
| [JAXA AW3D30](https://www.eorc.jaxa.jp/ALOS/en/dataset/aw3d30/aw3d30_e.htm) | Approx. 30 m PRISM DSM; public page lists v4.1 for global coverage outside Japan/Antarctica. Local source mix/accuracy not tested | Free commercial/noncommercial use subject to JAXA terms; downloadable DSM with quality information | **Alternative, not used**. Useful cross-check, not evidence of finer channel cross sections or verified individual trees |
| [Sentinel-2 documentation](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel2.html) | Native bands differ in resolution; 10 m visible/NIR does not imply 10 m all-band data. Clouds and acquisition date matter | Open Copernicus imagery; SAFE/COG paths depend on provider. Existing HLS/GIBS path is 30 m and separately dated | **Existing optional HLS context preserved**. No optical surface was converted into invented 3D geometry or vegetation measurements |
| [IGN geoportal service](https://www.gob.pe/institucion/ign/pages/9039-acceder-al-geoportal-institucional-del-instituto-geografico-nacional) | Official vector/raster and metadata access documented; Piura-specific scale, horizontal/vertical accuracy, update and export terms not inspected per layer | Institutional portal/catalog. Coverage and redistribution rights require per-layer checks | **Reference candidate, not downloaded**. Prefer an authoritative detailed DTM/contour reference when available; no assumed free unrestricted licence |
| [INGEMMET GEOCATMIN](https://geocatmin.ingemmet.gob.pe/geocatmin_v3/), [hazard metadata](https://catalogo.geoidep.gob.pe/metadatos/srv/api/records/c5580ab5-7277-4858-8d16-a982bd2cc23b) | Hazard metadata describes 1:100,000 topographic input and other source scales; not street-scale channels | Viewer and download metadata; formats/terms must be checked per export | **Reference candidate, not integrated**. Needed for independent geological/geomorphological review, not a substitute for local field assessment |
| [SENAMHI data access](https://www.senamhi.gob.pe/site/descarga-datos/), [official access description](https://www.gob.pe/9312-conocer-los-datos-hidrometeorologicos-del-peru-descargar-los-datos-meteorologicos) | Station-point observations, station/date/quality-specific; a station is not a spatial weather reconstruction | Public service describes a registered download path; no authenticated download or redistribution terms verified in this task | **Not connected to visual weather**. Existing POWER/GIBS evidence remains separately labelled. Rain presets never impersonate observations |
| [ANA services catalog through IDEP](https://www.geoidep.gob.pe/catalogo-nacional-de-servicios-web/servicio-de-visualizacion-wms) | Catalog identifies hydrographic basin services; detailed Piura channel accuracy, timestamps and hydraulic sections unknown | WMS discovery is not verified vector export, a licence or measured discharge | **Reference candidate, not integrated**. Needed for hydrologic cross-checks and eventual measured levels/sections |
| [CENEPRED SIGRID Piura report](https://sigrid4.cenepred.gob.pe/sigridv4/documento/17539), [SIGRID](https://sigrid.cenepred.gob.pe/sigridv3/) | Regional vulnerability/hazard evidence includes a 2023–24 Piura report; publication epoch and scale matter | Public technical documents/viewer; per-layer geometry/terms not validated | **Reference candidate**. No risk polygon or safety recommendation was invented from the terrain palette |

NISAR remains analytical evidence under [the existing integration plan](NISAR_EVIDENCE_INTEGRATION.md). Backscatter, optical water masks, mapped hydrography, visual ripples and source DSM geometry are distinct evidence. This task did not download a real GCOV product, calibrate a water classifier, verify S-band coverage or close the existing real-NISAR/planting acceptance gap.

## Reproducible preparation

Inside the existing container:

```bash
docker compose exec -T api python -m tools.prepare_twin --bbox -79.68 -5.44 -79.56 -5.32 --min-zoom 10 --max-zoom 11 --max-tiles 64 --output .local/qa/territory/terrain
```

Add `--plan-only` to inspect the work list without data reads/writes. The validated budget is 1–256 tiles; over-budget requests fail before I/O. The command uses the application's real cache/rendering code, writes `{z}/{x}/{y}.png`, and records SHA-256, bytes, CRS, terms/source links, scale and a separate coarse nodata/height audit. Repeated source bytes produce the same tile hashes; preparation timestamps naturally differ. It is a terrain package, not a complete offline basemap or building archive.

Missing input DSM pixels in the inherited Terrarium rendering path are displayed as zero; this format/path does not carry a coverage mask. This limitation is explicit in manifests. The source point endpoint returns **null/unknown**, never an invented zero, for missing coverage. Do not infer sea level, a depression or a dry channel from a missing tile. Detail is withheld while terrain tiles are loading. A per-tile coverage-mask delivery remains necessary for fully unambiguous regional display.

## Resource limits and lifecycle

Native tile streaming selects terrain detail; map cache is capped at 128 tiles and three zoom levels. Entering 3D retains the current geographic framing. Close-up detail is rebuilt after camera/source changes, not every animation frame. Trees use a fixed world lattice in loaded forest/park cover, source-polygon holes and a 12 m clearance envelope over loaded buildings, roads, waterways and water. This is a conservative display filter, not verified complete planting clearance. Dense/oversized inputs decline procedural tree rendering instead of silently ignoring constraints.

Budgets: 700 instances maximum, 128 cover features, 256 exclusion features, 40,000 prepared vertices, 4,096 candidate attempts, 192 waterway segments and three custom draw calls maximum. Only mapped river/canal lines without intermittent flags are eligible for ripples; mapped permanence does not establish water present today. Unknown widths use an explicitly illustrative narrow strip. Downstream direction follows the available DSM gradient; flat/uncertain gradients use standing ripples. The DSM is not channel bathymetry.

Animation requests at most 24 repaints/s, pauses while hidden and follows reduced motion. It is disabled by default. Explicit controls can disable custom layers independently. Lost graphics contexts release/recreate custom resources; removal aborts point requests, removes listeners, cancels timers and releases GPU handles. Network errors remain visible/unknown. Native renderer internals manage terrain culling/seams/LOD; this task does not claim a new occlusion engine or smooth continuous tree-LOD blending.

During software-rendered testing, the existing Uvicorn supervisor repeatedly lost child processes on the shared Windows/WSL host. Increasing its worker-health margin from 5 to 30 s is a starvation mitigation; this observation alone does not establish OOM, a raster crash or a definitive root cause. The application remains local-only on its existing port.

## Verification report

The executable commands and final measured results are recorded here after validation. Raw local artifacts live in `.local/qa/territory/` and `.local/fuzz/territory/`; fixtures are explicitly labelled and do not establish real-world geographic accuracy.

## Remaining limits

The implemented viewer is an evidence-aware territorial increment. It does not satisfy a claim of a complete surveyed Piura digital twin. Regional terrain resolution limits ravine cross sections; OSM cover and road data are incomplete; Overture source footprints can be estimates; default building heights and every procedural tree remain estimates. Facade textures, verified individual trees, hydraulic levels/velocity/depth, calibrated rain/flood scenarios, physical AR registration, dependable video export and target-hardware 60/30 FPS certification remain separate open gates. Visual weather has sky/fog/rain presets and approximate solar lighting, not volumetric observed clouds or calibrated atmospheric optics. No general AO/shadow/photogrammetry capability is claimed.
