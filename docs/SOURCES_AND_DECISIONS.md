# Sources, precedence, and preparation decisions

## Source register

| ID | Source | Purpose | Status |
| --- | --- | --- | --- |
| F1 | Owner-provided NiñoRadar narrative | Authoritative product scope, pilot and limits | English translation in `SOURCE_CONTEXT.md`; original received November 14, 2026 |
| F2 | [Team research document](https://docs.google.com/document/d/10_RmLBz5asZoEUewSKRS8kkQ9_lA0bDfm1piiPGLaHs/edit?tab=t.flskznlxd0bg) | Supplementary research | Read through Google Docs connector November 14, 2026; document states November 12, 2026 update |
| F3 | Official mission/provider documentation and reproducible evidence | Technical verification | Research starting points; no satellite downloads, access tests or local coverage verification during setup |

F1 governs product commitments. F2 includes hypotheses, proposals and technical statements that need primary-source verification before adoption. Scientific contradictions must be documented with evidence and proposed corrections; product precedence does not justify repeating an incorrect technical claim.

The earlier setup inspected the document's four tabs: initial notes, the linked research tab, another copy of the NiñoRadar narrative and an empty tab. This repository retains a relevant summary and link rather than the full supplementary document.

The owner subsequently required English throughout the working tree, English file names, one file per commit, a private shared context directory, and reusable technology-research and adversarial-QA skills. The current English narrative preserves the source's substantive commitments; historical commits are retained without rewriting.

## Reconciling the main and supplementary sources

| Topic | Main narrative F1 | Supplement F2 | Working decision |
| --- | --- | --- | --- |
| Territory | Catacaos and Cura Mori, Piura | Coastal Piura and Tumbes, one case in each | Keep F1 pilot; Tumbes is future research |
| Users | Municipalities, risk management, humanitarian teams, researchers/communities | COER/COEL operators and brigades | Interview candidates; no claim of validated roles |
| Core | Water change, exposure, prioritization | Forecast + SAR + field verification | Prioritize F1's three capabilities |
| Coordination | Support verification | Assign, acknowledge and reconcile field reports | Optional extension, outside core MVP |
| Data | NISAR if comparable; clearly labeled historical Sentinel-1 | GCOV, Earthdata/ASF, SENAMHI, GPM, MTC, INEI and others | Research routes; no claim of tested access |
| Alerts | Complement official systems | Official notice, analytic notification and field report | No external alerts or dispatch in initial core |
| Visualization | Maps and dashboard | Timeline and evidence card | Evaluate UX without changing scientific scope |
| AR/digital twins | Undefined | Outside central requirements | Owner-requested research, experimental extension |
| Validation | Uncertainty and dates | Independent metrics, spatial/temporal separation | Future acceptance criteria without invented results |

## Useful supplementary lessons

- Keep observation, forecast and field report distinct, each with provenance and relevant times.
- Separate acquisition, publication, ingestion and processing. Faster polling produces no new acquisition.
- NISAR should produce an analytical layer rather than serve only as background imagery.
- Check geometry, polarization, version, resolution and quality before comparing observations.
- Preserve original, normalized and derived artifacts with traceability.
- Compare existing solutions without claiming to be the first flood map or exposure intersection system.
- Validate tasks and connectivity with users before committing to brigade synchronization or notifications.
- Evaluate scientific validity, interface utility and technical performance separately.

F2's specific latency, availability, revisit and maturity figures are not guarantees. Recheck them against the exact current product/version and record the research date. Historical statistics also require their original source and reference period.

## Research starting points from the supplementary document

These links were extracted during the earlier setup. Their presence does not establish current availability, automation permission, local coverage or redistribution rights.

| Primary source or portal | Research purpose |
| --- | --- |
| [NASA NISAR overview](https://science.nasa.gov/mission/nisar/mission-overview/) | Mission and physical observation limits |
| [ASF NISAR availability](https://nisar-docs.asf.alaska.edu/availability-overview/) | Current collections, maturity and access |
| [ASF NISAR products](https://nisar-docs.asf.alaska.edu/products-overview/) | Product levels, formats, variables and quality |
| [ASF urgent response](https://nisar-docs.asf.alaska.edu/urgent-response/) | Access restrictions and product differences |
| [NASA Earthdata Search](https://search.earthdata.nasa.gov/) | Scene discovery and metadata |
| [SENAMHI monitoring](https://www.senamhi.gob.pe/servicios/main.php?p=monitoreo-informacion-diaria) | Hydrological context and age of observations |
| [SENAMHI IDESEP services](https://idesep.senamhi.gob.pe/portalidesep/idesep_componente_catalogo_geoservicios.jsp) | Available geospatial services and formats |
| [SENAMHI flood observation](https://web2.senamhi.gob.pe/?p=observacion-de-inundaciones) | Existing flood products and initiatives |
| [CENEPRED SIGRID Collect](https://sigrid.cenepred.gob.pe/sigridv3/sigrid-collect) | Territorial and field-information patterns |
| [INEI spatial data infrastructure](https://ide.inei.gob.pe/) | Boundaries, cartography and information scale |
| [MTC road emergency open data](https://www.datosabiertos.gob.pe/dataset/emergencias-en-la-red-vial-nacional-ministerio-de-transportes-y-comunicaciones-%E2%80%93-mtc-0) | Reported road status, data dictionary and cutoff date |
| [Copernicus EMSR199](https://mapping.emergency.copernicus.eu/activations/EMSR199/) | Historical Peru 2017 reference; distinct mission and time |
| [Copernicus GloFAS](https://global-flood.emergency.copernicus.eu/general-information/about-glofas) | Forecasting versus observed surface change |

An ambiguous SERVIR acronym in the initial notes may refer to SERVIR-HKH. Confirm the intended program and coverage before using it; do not assume Peruvian operational coverage.

## Current preparation decisions

1. Keep `JoanixX/hackathon_nasa` private and preserve its existing history.
2. Maintain English documentation, prompts, code/comments, interface copy, identifiers and file/directory names. Preserve proper names, official source URLs and external protocol identifiers where translation would corrupt identity.
3. Keep `prompts/` and `context/` local and Git-ignored. Track only minimal agent entry points and general contribution rules.
4. Every new commit changes exactly one tracked path. File-name changes use a separate deletion commit and addition commit so each commit still changes one path.
5. Treat technology selections as pending until evidence supports an ADR; compare retaining the current solution and adding no dependency.
6. Require property-based testing for executable logic and adversarial/fuzzing assurance at relevant boundaries; accurately report execution and limitations.
7. No application, SAR pipeline, selected stack, downloaded scenes, measured scientific results or deployments exist at this stage.
8. Code license remains undecided; dataset redistribution rights are not assumed.

## Questions for the next investigations

- Is there a suitable comparable NISAR pair covering the pilot, and which product/version is appropriate?
- What independent reference can evaluate water changes, and with what limitations?
- Which cartography supports road/agricultural exposure without overstating coverage?
- Which minimal architecture can demonstrate the workflow with measured performance and controlled failures?
- How do users understand observation dates, uncertainty and potential exposure?
- Do AR or a digital twin improve a specific task compared with an accessible 2D map?
