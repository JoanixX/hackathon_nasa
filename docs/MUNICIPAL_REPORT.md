# Ayumi municipal-review report

**Status — November 15, 2026 (Lima):** implemented in `raiz_sar/report.py` / `municipal.py`, served synchronously by `POST /api/reports/preview` and displayed/printed in Report. No model call is required. The existing `/api/reports` job API still supports optional AI-authored narrative; it cannot change deterministic numbers. Report and scene versions must match the saved plan.

## Included material

- Geodesic union of assessed, eligible and funded candidate footprints, in hectares and square metres; overlaps counted once. The funded geometry is a proposed core, not demonstrated protection or an as-built planting survey.
- Per-zone area, slope/evidence, backscatter availability, representative coordinates, allocations and costs. Representative points are not surveyed stakes.
- Capsule/seed counts by funded species; modeled germination and establishment remain distinct from observed survival. Candidate sorties remain non-executable planning artifacts.
- Itemized capsule, delivery, maintenance and monitoring costs, total, budget remainder, all input assumptions and rounding rules.
- Qualitative economic and environmental opportunities per funded species; explicit ecological/altitude/conservation review, no fabricated revenue or avoided-loss valuation.
- Numbered implementation sequence, responsible roles, prerequisites, stop conditions, monitoring and acceptance artifacts.
- Risk register with owners/controls, unpriced resources, source URLs, dates and reproducibility identifiers.

## Budget method

Historical official reference: [OSCE Opinion 040-2021/DTN, sections 2.1.2–2.1.3](https://cdn.www.gob.pe/uploads/document/file/1823405/Opini%C3%B3n%20040-2021%20-%20CONSORCIO%20INTEG.VIAL%20-%20Valorizaci%C3%B3n%20de%20Mayores%20Metrados.pdf.pdf?v=1619026108). It describes direct cost as the sum of measured quantities multiplied by unit prices, with other applicable components treated separately. It addresses a historical regulatory context and does not establish the procurement rules governing a new 2026 project.

`Direct cost = Σ(Q_i × PU_i)`

Ayumi's priced scope is `capsules × capsule rate + prorated delivery/maintenance + applied monitoring`. The allocator rounds capsule unit rates to cents, full-area costs to cents, and each funded fraction of the area cost upward to a cent. The report splits the saved area cost in proportion to the delivery/maintenance rates and assigns the cent residual to maintenance; the breakdown therefore equals the saved total exactly. Displayed funded hectares are rounded and are not used to reconstruct the saved cent allocation.

Defaults and edited rates are **user assumptions**, not official tariffs. A cost engineer must replace them with dated local quotations and resource-based unit-price analyses. Site surveys, professional services, labor/equipment, water, permits, protection, replacements, recurring maintenance, applicable overhead/profit/taxes and contingency must be explicitly priced or documented as included. The shown total is the modeled priced scope; unpriced items prevent treating it as a complete investment budget.

## Benefits and ecological limits

[SERFOR's 2025 algarrobo guide](https://repositorio.serfor.gob.pe/bitstream/SERFOR/977/3/SERFOR%202025%20Guia%20de%20Arboles%20Plus.pdf) documents dry-forest uses and ecosystem services (printed page 10, PDF page 12). It does not quantify local benefits of this proposal. [SERFOR's sapote record](https://repositorio.serfor.gob.pe/handle/SERFOR/558) flags multiple uses and conservation concern. [SERFOR's Piura seed-collection account](https://www.gob.pe/institucion/serfor/noticias/926693-piura-serfor-promueve-recoleccion-de-semillas-en-bosque-seco-del-campus-de-la-universidad-de-piura) supports dry-forest occurrence/seed-source context, not high-altitude suitability.

[FAO's soil-bioengineering discussion](https://www.fao.org/4/x0622e/x0622e0s.htm) distinguishes technique- and site-dependent contributions to erosion/shallow-slope management. It is not a local prescription or evidence that planting prevents channelized debris flows. Seeds do not create mature roots instantly. No carbon tonnes, sediment reduction, protected-house count, revenue, NPV or avoided losses are estimated without independent local evidence and a counterfactual.

## Recreate a defensible implementation

The generated report provides the full numbered sequence. Begin with consent, verified boundaries and a field geotechnical/hydrological/ecological assessment; reject inappropriate channels, runout and unstable sites. Confirm seed identity/provenance, local water needs and permits before quoting resources. Preserve GIS, NISAR acquisition/coverage/evidence run, plan request, assumptions and versions. Review density and budget, calibrate a small field pilot, secure aviation/operational permissions if applicable, then document deposition and maintenance. Monitor germination, establishment and later environmental outcomes separately. Review as-built costs and measured outcomes before municipal technical approval.

Validation evidence and remaining gates are in [AYUMI_DELIVERY.md](AYUMI_DELIVERY.md). A reproducible draft is not an approved technical dossier or an institutional endorsement.
