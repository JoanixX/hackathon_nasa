# ADR 0002 — Map-first frontend, free real-data sources and Piura focus

- **Date:** November 15, 2026.
- **Status:** accepted by the owner on November 15, 2026 (approval of the frontend audit and its six recommendations).
- **Amends:** [ADR 0001](0001-technology-stack.md) for the map engine, frontend file layout, basemap and imagery sources, and adds one Python dependency. The backend, job, AI and AR choices of ADR 0001 stand.

## Context

The first implementation worked end to end but the frontend failed as a product. A browser and code audit found these causes:

1. Four panels and six tabs were visible at once, ordered by module (M1–M8) instead of by user task; disabled controls did not say what was missing.
2. The `Street map (OpenStreetMap)` layer used `tile.openstreetmap.org` while the API sent `Referrer-Policy: same-origin`, so browsers requested tiles without a Referer. The [OSMF tile usage policy](https://operations.osmfoundation.org/policies/tiles/) requires a valid Referer, forbids restrictive referrer policies and headless bots, and offers no availability guarantee.
3. The optical layer was `VIIRS_SNPP_CorrectedReflectance_TrueColor` in `GoogleMapsCompatible_Level9` (about 306 m per pixel) shown at zoom 14 (about 10 m per pixel), a ~32x enlargement.
4. Charts were drawn before their prerequisites existed (processed SAR, selected sector, computed plan, an establishment half-life).
5. "Post-rainfall assessment" showed a synthetic speckled raster plus the regular grid of drone deposition nodes; there was no rainfall evidence or real before/after pair.
6. The "3D preview" was a separate A-Frame scene on a flat plane (no DEM) and the camera AR needed a printed target the UI never introduced.
7. Leaflet 1.9's default attribution prefix shows a flag unrelated to the project.
8. Sector polygons were synthetic offsets that fall on the Chillón floodplain and urban areas, and slopes were placeholders.

Verified data facts (November 14–15, 2026):

- ASF catalog: NISAR L2 GCOV over the lower Piura locator starts on 2026-06-21 (21 granules June–October, 20 dual-pol `DHDH`). No NISAR acquisition covers the January–April 2026 rainy season there.
- ASF catalog: 119 OPERA RTC-S1 (Sentinel-1, C-band) granules over the same AOI between January and May 2026; OPERA DSWx-S1 has none.
- NASA GIBS WMTS (no account): `NISAR_L2_Geocoded_Polarimetric_Covariance` (`GoogleMapsCompatible_Level13`, about 19 m/pixel) returned valid tiles over Piura for June–October 2026 dates and none over Carabayllo; `OPERA_L2_Radiometric_Terrain_Corrected_SAR_Sentinel-1` (`Level12`) returned valid tiles over Piura on 2026-02-10, 02-13 and 02-22; `HLS_S30/L30_Nadir_BRDF_Adjusted_Reflectance` (`Level12`) has valid pixels only on acquisition days; `IMERG_Precipitation_Rate` is `Level6` (about 2.4 km/pixel display, coarser data).
- NASA POWER daily API (no key) returned `PRECTOTCORR` (MERRA-2 reanalysis, mm/day) for Piura in 2026.
- Copernicus DEM GLO-30 COGs are readable anonymously from `copernicus-dem-30m` on AWS by windowed HTTP reads.

## Decision

| Concern | Decision |
| --- | --- |
| Map engine | Replace Leaflet with **MapLibre GL JS 5.24.1** (BSD-3-Clause, UMD build): vector basemap, raster layers, `raster-dem` terrain, hillshade and 3D in one engine. MapLibre 6 ships ESM plus a separate worker only; revisit after the drawing adapter is verified with it |
| Basemap | **OpenFreeMap** vector styles (MIT code, OSM data under ODbL; no key, no request limits stated). `tile.openstreetmap.org` is removed. The API sends `Referrer-Policy: strict-origin-when-cross-origin` |
| Optical context | **HLS S30/L30** from GIBS at `Level12`, with dates that actually have pixels over the area; VIIRS kept only for regional zooms (≤ 9) |
| SAR display | GIBS visualizations of **NISAR GCOV** (June–October 2026 over Piura) and **OPERA RTC-S1** (rainy season), labeled as rendered imagery; quantitative dB values only from downloaded products (Earthdata Login) |
| Rainfall | NASA POWER daily precipitation, labeled as modeled reanalysis (MERRA-2), plus the GIBS IMERG layer as coarse context |
| Elevation | Copernicus DEM GLO-30 (a surface model) for slope statistics, Terrarium terrain tiles served by the API, hillshade and the AR terrain mesh, so 2D, 3D and AR use one elevation source |
| Drawing | **terra-draw 1.38.0** with **terra-draw-maplibre-gl-adapter 1.4.1** (MIT); polygons validated server-side with Shapely |
| Assisted boundary | **scikit-image 0.26.0** SLIC superpixels on HLS colour plus DEM slope propose a boundary; the user compares and accepts or rejects it. No model edits a boundary silently. SAM remains an optional later path |
| Frontend layout | `index.html` stays the single entry point; application code moves to native ES modules under `app/` (no build step, no framework). The Tailwind browser CDN (development-only) is dropped for plain CSS custom properties in `app/styles.css` |
| Scope | **Piura is the primary study area**; Carabayllo stays as a secondary selector. User-drawn or imported zones are the real-data path; synthetic sectors remain only as a labeled demo dataset |
| Twin and AR | The **3D twin** is MapLibre terrain from the DEM with the same zones and layers; the separate A-Frame preview is removed. **AR** stays MindAR image tracking, now with a DEM terrain mesh and an in-app target guide |
| Post-rainfall | Rain timing from POWER → Sentinel-1 RTC before/after on the same dates the catalog lists → change shown at the product's resolution; NISAR covers dry-season change and later monitoring |

## Alternatives considered

- **Keep Leaflet** with a raster OSM-derived provider: lowest migration cost, but no vector basemap, DEM terrain or 3D in the same engine; the twin would stay a second engine.
- **CesiumJS:** strong globe/3D, but its standard terrain and imagery path uses Cesium ion tokens and it would duplicate the 2D engine.
- **deck.gl:** unnecessary for the current data volume.
- **Esri World Imagery:** terms require an ArcGIS account for application use; not adopted.
- **EOX Sentinel-2 cloudless:** clear 10 m mosaic but CC BY-NC-SA 4.0 (non-commercial); not adopted by default.
- **A language model moving vertices:** imprecise and unverifiable for geometry; the LLM is not used for boundaries.
- **SAM (segment-geospatial):** stronger segmentation but a multi-gigabyte PyTorch dependency and slow CPU inference; deferred.

## Consequences

- The frontend is rewritten; backend contracts are extended (zones, terrain, rainfall, availability, refinement) rather than replaced.
- GIBS tiles are visualizations: they are not used as numeric backscatter. Charts show real POWER rainfall, catalog acquisition dates and DEM slope; SAR dB charts appear only after an authorized download.
- New network dependencies at run time: OpenFreeMap, GIBS, NASA POWER, ASF catalog and the Copernicus DEM bucket. Each failure has an explicit UI state; no fixture stands in silently.
- One new Python dependency (scikit-image); the hashed lock is regenerated in the target image.

## Review triggers

OpenFreeMap terms or availability change; GIBS layer identifiers or resolutions change; NISAR rainy-season coverage over Piura appears (2027 season); MapLibre 6 verified with the drawing adapter; a measured need for SAM; Earthdata credentials configured (enables quantitative SAR series).
