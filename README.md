# NiñoRadar

### Satellite intelligence for understanding flood impacts

Prepared for **NASA Space Apps Challenge 2026**, associated with **Dancing with the SARs** according to the team's project narrative. Repository: `hackathon_nasa`. Team referenced by the supplementary document: **404 Gravity**.

**Status: documentation and agent setup.** The repository contains project context, scope, working rules and local research prompts. No application, SAR pipeline, selected stack, downloaded scenes, tested integrations or validated scientific results exist yet.

## Start here

Every agent must first read the local [`context/START_HERE.md`](context/START_HERE.md), then follow its reading order. [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) and [`GEMINI.md`](GEMINI.md) are tracked entry points to the same shared instructions. Agent discovery varies by tool; when an entry point is not loaded automatically, explicitly provide its path.

`context/` and `prompts/` are intentionally ignored. They remain on this computer and are absent from fresh clones. Copy them through an authorized private channel before using another checkout. If private context is unavailable, report the missing context and use the tracked baseline without inventing local rules or past decisions.

## Product purpose

Extreme rainfall and flooding in Piura can affect homes, roads, agriculture and essential services. Information is distributed across sources, while cloud cover limits optical observation.

NiñoRadar proposes converting SAR observations from the NASA–ISRO NISAR mission into understandable maps of surface-water change, intersecting these with infrastructure and supporting prioritization of field assessments.

The pilot is **Catacaos and Cura Mori, Piura, Peru**. Expansion requires suitable observations and separate validation.

1. **Where has water expanded?** Show changes consistent with flooding between comparable observations.
2. **What might be affected?** Estimate intersections with roads, buildings and agricultural land where appropriate cartography exists.
3. **Where should verification be prioritized?** Explain proposed sectors using transparent rules and visible uncertainty.

## Planned MVP

| Capability | Expected result | Prerequisite |
| --- | --- | --- |
| Detection map | Before/after comparison and detected water extent | Comparable SAR pair and documented method |
| Exposure map | Potentially exposed road segments and agricultural areas; buildings if suitable data exists | Known coverage, source date and license |
| Territorial dashboard | Detected area in ha/km², road length in km and sectors proposed for verification | Reproducible calculations and quality metadata |

Conceptual flow: **satellite observation → change detection → territorial intersection → visualization and assessment support**.

Detected water is preliminary evidence. Potential exposure does not confirm damage, road closure, safe access, water depth or casualties. Always distinguish acquisition dates, missing coverage and uncertainty. NISAR is the primary mission; historical Sentinel-1 must be identified as another mission. Results must not be presented as real-time flood detection.

## Sources and scope

1. [Source narrative in English](docs/SOURCE_CONTEXT.md): translated from the owner's original attachment; authoritative product commitments.
2. [Team research document](https://docs.google.com/document/d/10_RmLBz5asZoEUewSKRS8kkQ9_lA0bDfm1piiPGLaHs/edit?tab=t.flskznlxd0bg): supplementary research read on November 14, 2026.
3. Primary documentation and reproducible evidence: required before claiming technical capabilities or results.

The supplement also proposes Tumbes, forecasts and brigade coordination. Those ideas do not automatically expand the MVP. See [sources and decisions](docs/SOURCES_AND_DECISIONS.md) and [scope and validation](docs/SCOPE_AND_VALIDATION.md).

## Repository structure

```text
hackathon_nasa/
├── .gitattributes
├── .gitignore
├── AGENTS.md
├── CLAUDE.md
├── GEMINI.md
├── CONTRIBUTING.md
├── README.md
├── docs/
│   ├── SOURCE_CONTEXT.md
│   ├── SCOPE_AND_VALIDATION.md
│   └── SOURCES_AND_DECISIONS.md
├── context/                              # Local, ignored
│   ├── START_HERE.md
│   ├── RULES.md
│   ├── PROJECT.md
│   ├── WORKING_STATE.md
│   ├── KNOWLEDGE.md
│   ├── MAINTENANCE.md
│   └── skills/
│       ├── technology-research/
│       └── adversarial-qa/
└── prompts/                              # Local, ignored
    ├── 01_product_logic_and_visual_refactor.md
    ├── 02_architecture_research.md
    └── 03_ux_ui_ar_and_digital_twins_research.md
```

## Local prompts and skills

Each prompt is self-contained, in English, and includes the complete translated narrative, reconciled supplementary context, tasks, deliverables and acceptance criteria. Read the private context first when working in this repository; copied prompts can also be used independently.

| Prompt | Assignment |
| --- | --- |
| `01_product_logic_and_visual_refactor.md` | Product logic, workflows, presentation contracts and visual refactor |
| `02_architecture_research.md` | SAR data, architecture, scalability, concurrency, response time and failures |
| `03_ux_ui_ar_and_digital_twins_research.md` | Geospatial UX/UI, animation, interactive AR and digital twins |

Run architecture and UX research before integrating their decisions into the implementation plan. Analysis is the default; implement only when the accompanying request asks for it.

The local **technology-research** skill covers project reconnaissance, current alternatives, technical evaluation, isolated feasibility checks, ADRs and review triggers. The **adversarial-qa** skill covers independent adversarial review, mandatory property-based testing for executable logic, malformed-input fuzzing, failure minimization and reproducibility. These are portable skill packages, not globally installed agent extensions.

## Working requirements

- **English throughout:** code, comments, documentation, filenames, directories, commits, UX/UI and research outputs. Preserve proper names and external identifiers.
- **One tracked path per commit:** stage and inspect one file at a time. Renames use deletion and addition commits; do not squash multiple files together.
- **Private context:** never force-add `context/` or `prompts/`, or publish their contents indirectly.
- **Evidence before adoption:** novelty, stars and vendor claims do not establish superiority. Include migration cost, ecosystem fit and no-new-dependency alternatives.
- **Adversarial assurance:** derive invariants from contracts, generate unusual inputs, minimize failures and retain reproducible evidence. Do not claim tests or research that were not executed.

See [contribution requirements](CONTRIBUTING.md). Proposed future research outputs may go in `docs/research/`; create that folder only when producing those outputs.

## License and attribution

The code license is undecided. The private repository does not grant an open-source license. Preserve each dataset, map, library and visual asset's terms and attribution. NASA Space Apps participation does not imply institutional endorsement by NASA, ISRO or Peruvian agencies.
