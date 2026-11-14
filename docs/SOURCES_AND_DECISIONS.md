# RAÍZ-SAR AI — Sources, overrides and decisions

## Source hierarchy

| ID | Source | Authority and status |
| --- | --- | --- |
| S0 | Owner's latest four corrections accompanying the attachment | Binding solution requirements: prevention through suitable root-forming vegetation; seed-planting drone extension; interactive AR map; AI-assisted future-state construction |
| S1 | Latest attached RAÍZ-SAR AI specification | Current solution source, interpreted in [SOURCE_CONTEXT.md](SOURCE_CONTEXT.md); scientific numbers and capability assertions require evidence |
| S2 | Primary technical/scientific documentation | Establish factual capabilities and limitations; does not cancel a product requirement merely because implementation needs research |
| S3 | Earlier NiñoRadar narrative, team Google Docs and existing research | Historical/supplementary background; previous solution and optional-AR scope are superseded |

The owner explicitly adopted a different solution. Do not preserve Catacaos/Cura Mori as the required pilot, health-access routing as the selected use case, or AR as optional. Retain the older research files without silently rewriting or publishing existing untracked work.

## Requirements reconciled

| Attachment statement | Latest interpretation |
| --- | --- |
| Reforestation and hidden moisture | Prevention-oriented planting assessment, with an explicit evidence gate for any wetness/moisture inference |
| Drone optimizer | Extra capability specifically for seed/capsule deposition; no actual flight command |
| Leaflet map in one HTML file | Required prototype entry point; AR needs an explicitly researched additional runtime and supported environment |
| Simulated LLM and decay formula called AI/ML | Clear demo mode; actual AI scenario-construction requirement needs a real inference path and verification |
| “X-ray” polygons and exact penetration depth | Educational metaphor only, never a validated subsurface measurement |
| HV/RVI confirms roots anchor slopes | Above-ground radar change does not establish root reinforcement; separate ecological/geotechnical assessment |
| Official SERFOR/CENEPRED dossier | Grounded printable planning draft without approval, signature or endorsement claim |
| Trees/ha and drone payload | Desired established plants differ from seeds/capsules, germination and establishment assumptions |
| Timeline phases | Actual acquisitions and generated future horizons kept distinct |
| Original geographic examples | Carabayllo and lower Piura/Sechura scenario selectors; validate boundaries and distinguish slope versus plain mechanisms |

## Primary references checked during this revision

Consultation date: November 14, 2026. These establish research constraints, not local data or model validation.

- [NASA NISAR mission overview](https://science.nasa.gov/mission/nisar/mission-overview/): band/access description distinguishes global L-band access from S-band coverage/access over India and selected sites. Do not assume local dual-band data.
- [ASF GCOV documentation](https://nisar-docs.asf.alaska.edu/gcov/): available covariance terms depend on acquisition mode, and normalization metadata matters. No assumption that every scene contains HH, VV, HV and VH, or that every value is sigma0.
- [ASF availability guide](https://nisar-docs.asf.alaska.edu/availability-overview/): data maturity is collection-specific; validated Level-3 SME2 is not established by the Level-0–2 validated release. Recheck before designing a soil-moisture dependency.
- [USDA Forest Service root-reinforcement research](https://research.fs.usda.gov/treesearch/6937): slope assessment depends on root characteristics and site conditions. A result from another species/site is not a locally validated planting prescription.
- [USDA Forest Service soil-bioengineering guidance](https://www.fs.usda.gov/t-d/pubs/pdfpubs/pdf12771814/pdf12771814dpi100.pdf): vegetation is relevant to certain erosion/shallow-failure mechanisms and must not be treated as a stand-alone solution for all deep failures.
- [FAO slope bioengineering discussion](https://www.fao.org/4/x0622e/x0622e0s.htm): establishment timing and technique depend on vegetation and site. Listed techniques from other regions are not automatic Peruvian species recommendations.

Detailed technical investigations remain future work. No scene download, soil-moisture retrieval, native-species validation, drone route, AR device test, AI inference or survival measurement was executed in this revision.

## Decision register

1. Adopt **RAÍZ-SAR AI** as the current product identity while keeping the existing private repository name and history.
2. Preserve the three prompt tracks, rewritten for the latest solution and self-contained English use.
3. Make interactive AR and AI-generated/assisted future-scene construction required product capabilities. A fallback does not erase either gate.
4. Define the drone extension as seed/capsule planting and separate it from imagery capture and real hardware operation.
5. Carry the source's single-HTML prototype target into research, while explicitly resolving AR/security/actual-AI dependencies rather than hiding them.
6. Replace unsupported source certainty with traceable evidence classes, sensitivity scenarios and explicit unknowns. Do not change the prevention goal into a flood-only viewer.
7. Keep `context/` and `prompts/` ignored; one tracked path per new commit. Preserve existing untracked `docs/research/` files.
8. Keep deliverables in English and conversational replies in Spanish, following the recorded later owner preference. Proper names and external identifiers remain exact.
9. The owner's subsequent stack-definition request is resolved by [TECHNOLOGY_STACK.md](TECHNOLOGY_STACK.md), [SAR_FOUNDATIONS.md](SAR_FOUNDATIONS.md), pinned manifests and [ADR 0001](decisions/0001-technology-stack.md). Do not treat earlier requests to choose tools as an instruction to reopen the selected baseline without evidence.

## SAR guide and stack evidence added

The owner supplied [NASA Earthdata's SAR introduction](https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/sar). Its Data Availability table was inspected directly in the browser after an automated reader returned 403. Relevant Python-oriented entries include pyroSAR, PyRAT and ISCE; each was compared with the actual GCOV product-level need rather than added indiscriminately.

Current primary product/tool documentation, official PyPI metadata and frontend release documentation were checked on November 14, 2026. The selected Python 3.12/Linux binary-wheel dry-run resolved 88 packages without installing them. The resolver ran on Windows/Python 3.11, so actual target environment markers, imports and native ABI remain an implementation gate. No runtime benchmark, scene processing, inference, service or camera test was performed. See the stack/ADR for exact sources, model access limitations and frontend artifact checks still pending.

## Research questions that must be answered

- Which slope mechanism and site can a vegetation intervention plausibly address, and on what establishment timescale?
- Which NISAR observations and independently validated indicators are actually available for the locations?
- Which native taxa and seed-deposition methods are appropriate, and where is planting unsuitable?
- How can the requested single-HTML demonstrator integrate real AR and an actual AI path without exposed credentials?
- What data/schema constraints keep an AI future scene grounded and distinguish illustration from prediction?
- What minimum evidence supports budget, seed quantities, establishment scenarios and any claimed benefit?
- Which AR registration/device approach can demonstrate the core within the real team/timebox?
