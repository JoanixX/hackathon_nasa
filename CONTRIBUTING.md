# Contributing to Ayumi

## Read first

Read the local `context/START_HERE.md`, then `AGENTS.md` and the project documents it references. Use the same context regardless of agent vendor. Report missing private context explicitly; it is intentionally excluded from clones.

## English throughout

Use English in source code, comments, variables, files/directories, documentation, commit messages, user-facing copy, errors, accessibility labels, empty states and research artifacts. Preserve proper names, official source URLs and external API/protocol identifiers. Translate explanatory text around them. Existing historical commits are retained.

## Exactly one tracked path per commit

The owner requires each new commit to change one tracked path. Stage and inspect each file separately:

```powershell
git add -- README.md
git diff --cached --name-status
git diff --cached
git commit -m "docs: update the project overview"
```

The staged path list must contain exactly the intended file before committing. Avoid `git add .` and `git commit -a`. Do not squash commits that affect different paths. Publish with a fast-forward update and verify the remote branch afterward.

To rename a tracked file while keeping this rule, commit its old-path deletion separately from its new-path addition. Explain the relocation in both English commit messages. Preserve the old history; temporary broken references between those two commits must be resolved in the completed change set.

Ignored files are not committed. `context/` and `prompts/` stay local; never use `git add -f` to include them or publish their contents through another file. Check with:

```powershell
git check-ignore -v -- context/START_HERE.md prompts/01_product_logic_and_visual_refactor.md
```

## Research and decisions

Use the local technology-research skill when choosing material backend/frontend tools. Inspect the project first, research current primary sources and evaluate security, performance, scaling, ergonomics, maintenance, cost, portability and complexity. Include migration and rollback costs and the complete ecosystem. Compare retaining the current approach and adding no dependency.

Run a small isolated feasibility check when it resolves a material uncertainty. Document an ADR with alternatives, evidence, decision, trade-offs, versions, research date, obsolescence risks and review triggers. Popularity and novelty are signals, not decision proofs. Vendor capability documentation is not independent performance evidence.

## Adversarial assurance

For executable logic changes, property-based testing is mandatory. Define invariants from requirements and independent models, generate valid/invalid/boundary inputs, shrink failures and retain seeds or replay artifacts. Use thousands of unusual cases within explicit time, memory and input-size budgets.

Review another agent's changes with an adversarial mindset: try to falsify assumptions and produce minimal reproducible failures. Fuzz relevant malformed-input boundaries in isolation, including timeout, memory and state-corruption behavior. Larger campaigns require an explicit recorded budget. Do not fuzz production or third-party services without authorization.

For documentation-only changes, validate links, names, instructions, source fidelity and ignored-directory behavior. Do not fabricate application test runs in a repository without executable application logic. Ordinary example-based tests remain useful for regressions but do not replace the owner's property-testing requirement.

## Knowledge and handoff

Update local `context/WORKING_STATE.md` and evidence-backed `context/KNOWLEDGE.md` after meaningful work. Follow `context/MAINTENANCE.md`: retain sources, verification date, scope and review triggers; correct superseded knowledge without erasing decision provenance. Owner rules change only through owner instructions, not through automatic self-editing.

## Data and secrets

Do not commit credentials, `.env` files, Earthdata tokens, personal field-team data or large satellite rasters. `data/`, `outputs/`, `artifacts/` and `.local/` are ignored. Record authorized download locations, metadata, checksums and license terms instead. Redistribute samples only with confirmed rights.

Current product baseline: Ayumi; selected Piura residential–ravine interfaces. See [implementation status](docs/IMPLEMENTATION_STATUS.md). Conversations follow the owner preference for Spanish; deliverables remain in English.
