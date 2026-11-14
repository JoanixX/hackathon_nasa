# RAÍZ-SAR AI

### SAR-informed planting assessment, slope bioengineering and AI-assisted AR scenarios

Current solution for the team's **NASA Space Apps Challenge 2026 / Dancing with the SARs** preparation. Repository: `JoanixX/hackathon_nasa` (private). The project has pivoted from the earlier NiñoRadar flood-exposure concept.

**Status: prompts, documentation and agent setup.** This revision does not build the application, run AI inference, validate species, process satellite scenes, fly a drone or demonstrate AR.

## Read first

Agents first read local [`context/START_HERE.md`](context/START_HERE.md). [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) and [`GEMINI.md`](GEMINI.md) route agents to shared instructions. `context/` and `prompts/` are ignored and absent from clones; copy them through an authorized private channel when needed. Report missing private context rather than claiming it was read.

## Current solution

Support environmental/GIS specialists and municipal planners evaluating where locally appropriate vegetation could contribute to erosion control and slope reinforcement, informed by NISAR evidence, terrain and field/ecological assessment.

The owner's latest requirements are:

1. A prevention-oriented approach using suitable root-forming trees/vegetation, without guaranteeing that planting prevents every huaico.
2. A drone extension that **plants seeds or seed capsules**.
3. A **required interactive geospatial map with AR**.
4. **Required AI-assisted construction of an interactive future planting scenario in AR**, with assumptions and generated content clearly labeled.

The two requested scenario locators are Río Seco/Carabayllo in northern Lima and lower Piura/Sechura. Their coordinates are approximate examples, not verified intervention boundaries. Species in the attachment are research candidates, not approved prescriptions.

## Source and scope

- [Current solution source and owner overrides](docs/SOURCE_CONTEXT.md).
- [Scope, data contracts and acceptance gates](docs/SCOPE_AND_VALIDATION.md).
- [Sources, scientific constraints and decisions](docs/SOURCES_AND_DECISIONS.md).

The latest attachment and corrections supersede the old pilot and optional-AR instructions. Earlier files in `docs/research/` remain dated background; their presence does not select their proposed product directions.

## Modules to specify

| Module | Required behavior |
| --- | --- |
| Scenario selector | Switch the two requested areas with explicit real/synthetic geometry labels |
| Optical/SAR comparison | Dated evidence with provenance, quality and scientifically defensible interpretation |
| Discrete timeline | Separate actual acquisitions, planning states and generated future horizons |
| Sector dashboard | Terrain, evidence, candidate species, quantities, budget and grounded indicators |
| Budget/drone planning | Eligibility-first allocation; seed-deposition plan as an extension |
| Establishment scenarios | Transparent planting-delay/germination/establishment assumptions |
| Planning assistant | Grounded printable draft without official-approval claims |
| Interactive AR and AI future scene | Supported-device AR linked to a versioned plan and actual AI integration gate |
| GIS connector | `loadArcGISGeoJSON(url)` with an English normalized schema and validation |

The source requests a single `index.html` prototype with HTML5, Tailwind CDN, Leaflet, Chart.js and icons. Research must resolve additional AR/AI dependencies, secure contexts and credential protection. No application stack has been installed or selected for production.

## Three local prompts

| File | Assignment |
| --- | --- |
| `prompts/01_product_logic_and_visual_refactor.md` | Product logic, complete module flows, prevention-oriented refactor and prototype plan |
| `prompts/02_architecture_research.md` | SAR/ecology feasibility, architecture, actual AI/AR integration, scalability, concurrency and errors |
| `prompts/03_ux_ui_ar_and_digital_twins_research.md` | Required interactive AR, AI future-scene construction, map UX, animation and evidence communication |

Each prompt embeds the complete current solution context, binding corrections and acceptance gates. Analysis and planning are the default; implementation requires the accompanying request. The prompts do not require the Google Docs or other prompts to be intelligible.

## Scientific interpretation

Radar backscatter is not automatically a measurement of buried moisture pockets, penetration depth, survival probability or root reinforcement. The attachment's numeric examples remain unverified illustrations. Inspect actual product channels/units and local band coverage. Seeds deposited do not equal established trees, and an attractive future scene does not validate ecological or geotechnical outcomes.

## Working rules

- English deliverables, code/comments, identifiers, file names and UX/UI; Spanish conversation per the recorded owner preference.
- Exactly one tracked path per new commit; preserve published history.
- Keep `context/` and `prompts/` private and ignored.
- Use the local technology-research skill for material technology choices and the adversarial-QA skill for executable assurance.
- Property-based testing is mandatory for executable logic; use bounded fuzzing at malformed-input boundaries. Documentation-only checks must not be reported as application tests.

See [CONTRIBUTING.md](CONTRIBUTING.md). The code license remains undecided. Respect dataset/library/asset terms, source attribution and institutional identity; this is not an official NASA, SERFOR or CENEPRED product.
