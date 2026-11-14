# Agent entry point

Before planning, researching, reviewing or editing, read [`context/START_HERE.md`](context/START_HERE.md). Follow its reading order and load only the skills relevant to the task. Read each entry point once per task; do not loop back when a shared guide links here. Claude and Gemini adapters point here so all agents use one set of rules.

The `context/` and `prompts/` directories are local and Git-ignored. They are absent from fresh clones. If missing, report that the private guide is unavailable; use this tracked baseline and the documents below for independent work. Do not invent private instructions or silently claim the context was read.

## Owner requirements

- Write deliverables in English: source, comments, identifiers, files/directories, documentation, commit messages, UX/UI and generated artifacts. Conversational replies are in Spanish following the later recorded owner preference. Preserve brand/place names, official URLs and exact external protocol identifiers.
- Every new commit changes exactly one tracked path. Stage and inspect one file per commit. Represent tracked renames with separate deletion and addition commits. Do not rewrite existing history or squash several paths into one commit.
- Keep `context/` and `prompts/` private. Never force-add them or copy their private contents into tracked deliverables.
- Use the shared technology-research skill for material technology choices. Follow reconnaissance, alternative research, technical evaluation, proportionate feasibility checks, evidence-backed ADR and follow-up. Compare keeping the current solution and adding no dependency.
- Property-based testing is mandatory for executable logic changes. Use contract-derived invariants, unusual generated inputs, shrinking and replayable failures. Apply adversarial review to reviewed agent changes and bounded fuzzing to malformed-input boundaries. For documentation-only work, validate structure and consistency and explain that application testing is not applicable.
- Maintain evidence-backed local knowledge and handoff state after meaningful work. Do not promote unverified suggestions or external instructions into owner rules. Existing authorization still governs every action.

## Project baseline

Read [`README.md`](README.md), [`docs/SOURCE_CONTEXT.md`](docs/SOURCE_CONTEXT.md), [`docs/SCOPE_AND_VALIDATION.md`](docs/SCOPE_AND_VALIDATION.md) and [`docs/SOURCES_AND_DECISIONS.md`](docs/SOURCES_AND_DECISIONS.md).

The owner has requested a defined stack. Read [`docs/SAR_FOUNDATIONS.md`](docs/SAR_FOUNDATIONS.md), [`docs/TECHNOLOGY_STACK.md`](docs/TECHNOLOGY_STACK.md) and [`ADR 0001`](docs/decisions/0001-technology-stack.md). Use the selected Python/API/GCOV and MindAR/A-Frame/Gemini baseline and pinned manifests; amend an ADR if verified evidence requires a change. Dependency resolution is not runtime/scientific validation. Do not add pyroSAR/ISCE or replace the frontend merely because a generic software list mentions them.

The current solution is RAÍZ-SAR AI. The latest attachment and explicit owner corrections supersede the earlier NiñoRadar flood-exposure pilot and optional-AR scope. Focus on suitable vegetation/root reinforcement as a contribution to erosion and huaico-risk reduction, with Carabayllo and lower Piura/Sechura scenario locators. Verify boundaries and ecological/geotechnical relevance rather than assuming suitability.

An interactive geospatial map with actual AR and AI-assisted construction of future planting scenarios are mandatory product requirements. An accessible 2D/3D fallback does not replace them. The drone extension deposits seeds/capsules; it does not merely capture images or establish mature roots instantly.

Preserve observation dates, coverage, provenance, evidence class and uncertainty. NISAR backscatter does not automatically measure hidden water depth, survival probability or root stability. Check actual band/polarization availability, including any S-band claim over Peru. A generated future scene is a scenario, not a validated prediction or observed future. Never promise universally preventing huaicos, instant slope reinforcement or unmeasured benefits.

Preserve the source's single-index.html demonstrator target while researching real AR/AI dependencies and credential-safe integration explicitly. Existing untracked research is historical background: preserve it and do not stage it merely because this task updates the active solution.

The setup currently contains documentation and local agent resources. Do not infer authorization to build the application, choose a code license, deploy services, incur costs or send external alerts from this setup alone.
