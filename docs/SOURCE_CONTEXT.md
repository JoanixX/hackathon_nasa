# RAÍZ-SAR AI — Current solution source

**Revision:** November 14, 2026. **Purpose:** define the solution and future AI assignments; this document does not implement the application.

This is the English working interpretation of the owner's latest attached specification, amended by the owner's explicit corrections in the accompanying message. It supersedes the earlier NiñoRadar flood-exposure concept as the current solution. Proper names and external identifiers retain their original spelling.

## 1. Source precedence and binding corrections

Apply this order: latest explicit owner corrections → latest attached solution specification → verified technical evidence for factual claims → older documents as historical background. A solution requirement establishes what to investigate/build; it does not establish that a scientific claim is already true.

The owner's four corrections are binding:

1. **Prevention-oriented bioengineering:** focus on trees or other suitable vegetation established from seeds whose root systems may reinforce appropriate slopes and contribute to reducing erosion and susceptibility to debris-flow-related hazards, locally called huaicos. This supersedes a generic flood-detection or restoration-only product.
2. **Seed-planting drone:** the drone extension deposits seeds or seed capsules. It is not merely an imagery drone and does not place mature trees or instantly establish root reinforcement.
3. **Mandatory interactive map with AR:** augmented reality is a required product capability, alongside the geospatial map. A 2D-only map or an ordinary 3D viewer does not fulfill this requirement. An accessible fallback is additional support, not a substitute for the required AR demonstration on a declared supported device.
4. **Mandatory AI-assisted AR future construction:** construct an interactive, spatially grounded future-state scenario showing the proposed planting intervention over time. Distinguish AI inference/generation, deterministic scene assembly and any ecological model. The result is a scenario with explicit inputs and assumptions, not an observed future or validated prediction by visual appearance.

## 2. Identity, team and timebox

- **Product:** RAÍZ-SAR AI.
- **Competition context:** a 48-hour NASA Space Apps Challenge 2026 hackathon, associated with “Dancing with the SARs” according to the supplied specification. Official submission rules still require verification.
- **Team:** one environmental engineer specializing in GIS/ArcGIS Pro and disaster risk management, plus two systems engineers covering frontend/backend/AI.
- **Repository:** retain the existing private `JoanixX/hackathon_nasa`; the earlier product name is historical.
- **Expertise requested from future agents:** senior full-stack architecture, WebGIS, AI and SAR remote sensing. Do not claim employment by NASA or institutional endorsement.

## 3. Problem and decision to support

The source describes extreme rainfall associated with El Niño activating sparsely vegetated ravines in Peru and motivating vegetation-based risk-reduction measures. It hypothesizes that useful residual moisture may persist after rainfall even when the surface appears dry in optical imagery.

The product should help an environmental/GIS specialist and a municipal restoration planner determine which sectors merit field evaluation, what locally appropriate planting intervention may be feasible, how to allocate a limited seed-planting budget, and how to communicate its possible development through an interactive map and AR scenario.

Retain the prevention objective without promising that planting prevents every huaico. Separate surface erosion, shallow slope failure and channelized debris-flow/runout processes. Establishment time, terrain, hydrology and geotechnical suitability constrain the contribution of roots. An intervention may require additional measures or be unsuitable.

## 4. Intended observation-to-intervention workflow

1. Inspect dated NISAR observations and terrain/ecological information, retaining mission, product, quality and coverage.
2. Derive scientifically defensible change/wetness indicators or clearly label exploratory proxies. Identify missing field evidence rather than inventing underground-water measurements.
3. Apply planting eligibility and exclusions before ranking candidate sectors. Moisture or a steep slope alone does not establish suitability.
4. Compare candidate native species and establishment methods with specialist evidence. Estimate seed/capsule needs separately from desired established plants.
5. Allocate an explicit budget using transparent objectives and constraints. Produce an illustrative drone seed-deposition plan as an extension.
6. Generate a scenario specification for the selected intervention, then build its spatially registered AR representation with visible time horizon and uncertainty.
7. Export an auditable planning draft and define field monitoring and future satellite-comparison protocols.

## 5. Two requested scenario locations

| Scenario | Source locator | Intended distinction | Source species candidates, not approved prescriptions |
| --- | --- | --- | --- |
| Río Seco ravine / Carabayllo, northern Lima | Approximate latitude/longitude `-11.83, -77.01` | Arid slopes and potential slope-bioengineering assessment | Tara (`Caesalpinia spinosa` as supplied) and Molle Costero (`Schinus molle` as supplied) |
| Lower Piura dry forest / Sechura depression | Approximate latitude/longitude `-5.52, -80.65` | Dry-forest establishment under different terrain and hydrological conditions | Algarrobo (`Prosopis pallida` as supplied) and Sapote (taxon unspecified) |

These are approximate map locators from the attachment, not surveyed boundaries, verified hazard footprints or confirmed ecological suitability. Verify names, coordinates, accepted taxonomy/synonyms, native range, conservation constraints, soil/salinity, water regime, land tenure and seed availability. Do not treat a floodable plain as the same slope-reinforcement problem as a ravine hillside.

Both scenario selectors remain required in the prototype specification. Choose a scientifically defensible primary slope case after evidence review; a secondary restoration comparison must not be misrepresented as equivalent debris-flow prevention.

## 6. Prototype delivery and visual direction requested by the source

The source requests a complete functional **single `index.html` entry point**, with HTML5, Tailwind CSS via CDN, Leaflet, Chart.js and Lucide or FontAwesome as the starting prototype stack. Preserve that delivery target for the demonstrator; assess the additional AR renderer/runtime and actual AI integration explicitly. A single HTML frontend does not eliminate remote dependencies, secure-context requirements or the need to protect server-side AI credentials.

Separate three modes: fixture-based interactive demonstration; authorized actual AI/model integration; and a future maintainable production architecture. Never label a fixture or deterministic heuristic as a trained ML model or live generative service. A demo-only adapter does not complete the required actual AI capability if inference was not executed.

The requested visual direction is an immersive dark mission-control interface with navy/slate surfaces, emerald/cyan/amber accents and restrained translucent panels. Use English copy, readable contrast, clear legends and reduced-motion behavior. “NASA-inspired” styling must not imply an official NASA application.

Future implementation should provide complete code without omitted sections and make advertised controls work. The current assignment prepares prompts and context only; it does not authorize building that code now.

## 7. Requested modules, interpreted under the corrections

### M1 — Scenario selector

Switch between the two locations, move the map camera and load sector geometries with distinct attributes. Clearly distinguish imported real boundaries from synthetic demonstration polygons. Reset or version dependent selections, optimization results, charts, reports and AR scenes on changes.

### M2 — Optical versus SAR evidence

Compare an attributed optical background/observation with a NISAR-derived layer where verified, or a labeled synthetic fixture. Keep mission, date, source, quality and unknown coverage visible. Do not imply arbitrary satellite tiles are Sentinel-2. The source's “X-ray” metaphor cannot be presented as literal subsurface imaging or an established depth measurement.

### M3 — Discrete temporal story

Provide three conceptual phases: pre-rainfall/bare-ground baseline; post-rainfall planting-assessment opportunity; and future establishment/monitoring at proposed horizons such as 3, 6 and 12 months. The attachment's day `+15` is an illustrative scenario date, not a universally optimal planting date. Observations must use actual acquisition dates; future phases must be labeled generated scenarios. Play/pause must not invent continuous satellite evidence.

### M4 — Sector evidence, planting calculations and charts

Show sector identity, area in hectares, slope with explicit units, available backscatter channels and index definitions, evidence status, candidate species and density assumptions. Calculate proposed established plants, seeds/capsules, budget and maintenance separately. Any erosion reduction, retained sediment, carbon or survival output needs a documented model, parameters, unit, horizon and uncertainty; otherwise display “Not estimated” or an explicit illustrative scenario.

The source requests a dual chart of moisture decline and increasing vegetation/backscatter. These are not automatically a conservation relationship or proof that water became biomass. Separate observations, modeled trends and illustrations, with no mixing of incompatible units on a hidden common axis.

### M5 — Budget optimizer and drone seed planting

Accept municipal budget in PEN (`S/`) or a desired planting target. Rank only eligible candidate sectors using transparent constraints and a documented objective. The source's dielectric-times-slope formula and “master anchoring nodes” are concept sketches, not validated engineering objectives.

The optional drone capability deposits seeds/capsules. Represent eligibility, payload, seed counts, germination/establishment assumptions, terrain, no-go areas, launch/landing, energy reserve, deposition rate and the source of operational constraints. A decorative zig-zag is not an autonomous executable flight plan. No flight command, upload or real planting occurs as part of the setup.

### M6 — Planting-delay and establishment scenarios

Compare source-requested delays such as now/day `+15`, `+30`, `+45` and `+60`, with explicit date semantics. Investigate whether calibrated moisture and ecological evidence supports a model. If not, provide transparent sensitivity scenarios without false probabilities or an exact countdown. Separate seed germination, seedling establishment and later survival. Ground moisture and local rainfall are not interchangeable with a backscatter proxy.

### M7 — Generative planning assistant and printable draft

Generate a sector-grounded planning draft with evidence summary, validated coordinate representation, assumptions, budget breakdown and limitations. Preserve source-record IDs and distinguish human-entered, measured, derived, modeled and AI-authored statements. Use a report-generation adapter with explicit actual/simulated mode. Printing/save-as-PDF should work for the generated draft, including source dates, scenario labels and map legend.

SERFOR and CENEPRED may be referenced as relevant institutions where justified. A generated report is **not** an official approved dossier, regulatory submission or certified statement of protected homes/retained debris. Do not imply endorsement, signature or compliance automatically.

### M8 — Required interactive AR and AI future-state construction

Connect sector selection and a versioned planting plan to a spatial scene containing terrain/reference geometry, proposed planting zones, species/asset choices, establishment stages and time horizons. Specify actual AI inputs/output schema, model/provider or local inference, deterministic constraints, validation and scene assembly. A prose answer, pre-rendered image or static 3D orbit view alone is insufficient.

At least one declared supported device must demonstrate real camera-based or equivalent environment-registered AR interaction. Compare marker/tabletop and geolocated approaches; retain a 2D/3D accessible fallback for unsupported devices. Keep present observations, proposed seed deployment and AI-generated future vegetation visually distinct. A root cutaway is illustrative unless independently supported, not satellite-observed root geometry.

### GIS import connector

Preserve the requested JavaScript interface `loadArcGISGeoJSON(url)` for future implementation. Normalize into English internal properties: `sector_id`, `sector_name`, `area_ha`, `slope_percent`, `dielectric_er`, `sigma_hh_db`, `sigma_hv_db`, `rvi`, `species_candidate`, plus provenance/quality/status fields. The attachment's original non-English attribute names are external legacy keys only; translate them at the import boundary, not throughout the application.

| Supplied external key | Normalized internal key | Validation requirement |
| --- | --- | --- |
| `nombre` | `sector_name` | Nonempty text; preserve source feature ID separately |
| `hectareas` | `area_ha` | Verify units and reconcile with geometry-derived area |
| `pendiente` | `slope_percent` | Confirm percent rather than degrees |
| `dielectric_er` | `dielectric_er` | Nullable; identify actual retrieval/model or illustrative source |
| `sigma_hh` | `sigma_hh_db` | Confirm normalization, channel and dB conversion before naming |
| `sigma_hv` | `sigma_hv_db` | Confirm channel availability, units and normalization |
| `rvi` | `rvi` | Store formula, required channels, units and validity |
| `especie` | `species_candidate` | Preserve supplied taxon string and specialist review status |

Inspect GeoJSON geometry, CRS assumptions, actual area/slope derivation, null values, units, feature count and URLs/CORS. Do not claim a one-minute real-data replacement without a tested compatible export.

## 8. Scientific assertions from the attachment that require correction or evidence

The following numbers are **unverified source examples**, not validated facts or fixture values ready to label as telemetry: `80%` tree mortality; hidden moisture at `20–40 cm` for months; universal L-band penetration of `30 cm`; dielectric values `3.2`/`24.5`; HH `-18`/`-8.5 dB`; HV `-11 dB`; RVI `0.12`/`0.58`; survival classes above `85%` or `65–85%`; and `92%` versus `38%` survival after delay. The example budget is `S/ 25,000`. The attachment's nominal wavelengths are approximately `24 cm` for L-band and `10 cm` for S-band; these are not depth guarantees.

Do not treat wavelength as penetration depth. NISAR backscatter is not a direct map of buried water pockets, dielectric constant, seedling survival or root reinforcement without an appropriate retrieval/model and independent validation. Confirm actual band/polarization coverage over Peru; the presence of two instruments on the mission does not establish local S-band availability. GCOV variables and normalization must be inspected rather than labeled indiscriminately as sigma0. The RVI formula must match actual available channels and units.

SAR vegetation change does not confirm that roots anchor a slope at 6–12 months. Erosion/carbon/protected-homes indicators require distinct models and evidence. Plan monitoring that can distinguish planting, germination, establishment, maintenance and possible later effects. Retain the root-reinforcement objective while stating its evidence and time limits.

## 9. Immediate deliverable and completion definition

Revise three self-contained English prompts: product logic/visual refactor; architecture/science/implementation research; and UX/UI/AR/AI future-state research. Keep them local and ignored. Update active project documentation and shared context to remove the superseded flood-only and optional-AR instructions. Preserve existing research as dated background without adopting its recommendations automatically.

No application, calibrated moisture model, species prescription, actual drone route, AR session, AI-generated future scene or validated prevention result is claimed by this documentation update.

## 10. Subsequent owner request — Defined SAR and application stack

The owner subsequently asked to incorporate [NASA Earthdata's SAR guide](https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/sar), examine its Python-oriented processing references, and define the stack. This resolves earlier open-ended technology selection while preserving the product requirements above.

Selected baseline: Python 3.12; FastAPI/Uvicorn/Pydantic; RQ with Valkey; SQLAlchemy/SQLite pilot metadata; asf_search and earthaccess; h5py/NumPy/SciPy/Rasterio/GeoPandas/Shapely/pyproj for product-level GCOV analysis; native HTML/JavaScript with Leaflet, Chart.js, Tailwind and Lucide; MindAR 1.2.5 with A-Frame 1.6.0 for actual image-tracked AR; and server-side Google Gen AI structured generation using default `gemini-3.8-flash`, validated before deterministic scene assembly. Use Hypothesis/pytest and fast-check/Playwright for executable QA.

pyroSAR, PyRAT and ISCE are evaluated tools, not automatic core dependencies. The chosen scientific path consumes already-corrected GCOV; raw focusing/InSAR requires a separate demonstrated need. Camera-free 3D remains a fallback, and heuristic/fixture output does not count as actual AI. A single HTML frontend does not contain backend credentials or do heavy HDF5 processing.

The exact versions and evidence are maintained in the stack specification, dependency manifests and ADR. Selected does not mean installed, runtime-tested or scientifically validated. A changed dependency or model requires a justified ADR amendment rather than silently replacing this baseline.
