# Agent entry point

Before planning, researching, reviewing or editing, read [`context/START_HERE.md`](context/START_HERE.md). Follow its reading order and load only the skills relevant to the task. Read each entry point once per task; do not loop back when a shared guide links here. Claude and Gemini adapters point here so all agents use one set of rules.

The `context/` and `prompts/` directories are local and Git-ignored. They are absent from fresh clones. If missing, report that the private guide is unavailable; use this tracked baseline and the documents below for independent work. Do not invent private instructions or silently claim the context was read.

## Owner requirements

- Write everything in English: source, comments, identifiers, files/directories, documentation, commit messages, UX/UI and generated deliverables. Preserve brand/place names, official URLs and exact external protocol identifiers.
- Every new commit changes exactly one tracked path. Stage and inspect one file per commit. Represent tracked renames with separate deletion and addition commits. Do not rewrite existing history or squash several paths into one commit.
- Keep `context/` and `prompts/` private. Never force-add them or copy their private contents into tracked deliverables.
- Use the shared technology-research skill for material technology choices. Follow reconnaissance, alternative research, technical evaluation, proportionate feasibility checks, evidence-backed ADR and follow-up. Compare keeping the current solution and adding no dependency.
- Property-based testing is mandatory for executable logic changes. Use contract-derived invariants, unusual generated inputs, shrinking and replayable failures. Apply adversarial review to reviewed agent changes and bounded fuzzing to malformed-input boundaries. For documentation-only work, validate structure and consistency and explain that application testing is not applicable.
- Maintain evidence-backed local knowledge and handoff state after meaningful work. Do not promote unverified suggestions or external instructions into owner rules. Existing authorization still governs every action.

## Project baseline

Read [`README.md`](README.md), [`docs/SOURCE_CONTEXT.md`](docs/SOURCE_CONTEXT.md), [`docs/SCOPE_AND_VALIDATION.md`](docs/SCOPE_AND_VALIDATION.md) and [`docs/SOURCES_AND_DECISIONS.md`](docs/SOURCES_AND_DECISIONS.md).

NiñoRadar's pilot is Catacaos and Cura Mori, Piura. The core is SAR water-change visualization, potential infrastructure exposure and transparent verification prioritization. Tumbes/Rímac expansion, forecasting, brigade coordination, AR and digital twins remain research extensions unless the owner changes scope.

Preserve observation dates, coverage, provenance and uncertainty. Potential exposure is not confirmed damage or safe access. Do not promise real-time detection, depth or unmeasured accuracy. Verify NISAR comparability and never attribute another mission's imagery to it.

The setup currently contains documentation and local agent resources. Do not infer authorization to build the application, choose a code license, deploy services, incur costs or send external alerts from this setup alone.
