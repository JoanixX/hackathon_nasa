# NiñoRadar scope, contracts, and validation

Prepared on November 14, 2026. This document translates the project narrative into working criteria. It does not establish an implemented system or a selected architecture.

## Users and primary task

Potential users include municipalities, regional governments, risk management institutions, humanitarian teams, researchers, and communities. The initial design hypothesis is a municipal territorial analyst comparing observations, examining exposure, and selecting sectors for field verification. Interviews are still required; these roles have not been validated through user research.

## Priorities

| Priority | Work | Required evidence |
| --- | --- | --- |
| P0: MVP | Catacaos/Cura Mori, SAR comparison, road/agricultural exposure, dashboard, uncertainty | Comparable observations, documented methodology and provenance |
| P1: after the core | Exports, stronger accessibility, validation samples, improved low-connectivity states | Demonstrated utility and documented limits |
| P2: research | Tumbes/Rímac, forecasts, field reports, synchronization, AR, digital twins | A specific use case, suitable data, cost analysis and separate validation |

An idea's priority does not establish its feasibility. This setup builds documentation and agent resources only.

## Minimum future demonstration

1. Select the study area and two observations with visible mission, acquisition time and coverage.
2. Check comparability; explain invalid combinations and prevent misleading comparisons.
3. Distinguish reference water, detected changes, exclusions and missing observations.
4. Enable infrastructure layers and inspect intersecting features.
5. Select a sector and inspect indicators, evidence, limitations and reasons for its proposed priority.

## Proposed minimum data contract

The final schema will follow architecture research. Preserve at least:

- **Identity:** observation/product ID, provider, mission, collection, processing level and version.
- **Time:** acquisition, publication when known, ingestion and processing in UTC; display Peru time with an explicit timezone. Represent unknown times as unknown.
- **Geometry:** AOI, CRS, resolution, extent, units, nodata, quality masks and valid coverage.
- **Method:** algorithm version, parameters, inputs, comparability checks and warnings.
- **Result:** masks/classes and quality states; numeric confidence only with a justified meaning and calibration.
- **Provenance:** URL, license/terms, attribution and checksum where appropriate.
- **Exposure:** feature ID, source layer/date, intersection type, computed area/length and originating analysis ID.

Obtain district boundaries from a documented cartographic source and verify CRS and administrative identifiers. Do not invent boundary coordinates or measure hectares and road lengths directly in angular degrees.

## Future MVP acceptance criteria

| ID | Criterion | Expected verification |
| --- | --- | --- |
| MVP-01 | Pilot limited to Catacaos and Cura Mori | AOI geometry and source documented |
| MVP-02 | Valid observation comparison | Mission, product, times, geometry and version recorded |
| MVP-03 | Water, change and unavailable observation distinguished | Legend and cases for nodata, exclusions and permanent water |
| MVP-04 | Reproducible exposure | Verified intersections without duplicate geometry counts |
| MVP-05 | Correct units | Suitable metric CRS or verified geodesic calculations |
| MVP-06 | Responsible communication | Visible dates, source, uncertainty and potential-exposure wording |
| MVP-07 | Understandable failures | Missing pair, missing coverage, unavailable provider and partial result states |
| MVP-08 | Honest demonstration | Real, historical and simulated resources labeled; correct mission attribution |
| MVP-09 | Reproducibility | Inputs, versions and parameters sufficient to regenerate a result |
| MVP-10 | Accessible English interface | Keyboard navigation, contrast, English microcopy and a textual map alternative |

## Scientific validation still required

Compare a baseline method with independent, contemporaneous references when available. Report precision, recall, F1 and IoU with class definitions, sample sizes, dates and limitations. Separate tuning and evaluation by time and space to avoid leakage. Do not treat the model's own mask as independent ground truth or claim an unmeasured accuracy percentage.

Investigate false positives and negatives in rice fields, wet soil, permanent water, urban areas, vegetation, radar shadow and acquisition geometry. Floods predating NISAR cannot be presented as observed by that mission. Historical Sentinel-1 may support methodology validation with explicit mission attribution.

A road intersecting a mask has potential exposure; that does not establish accessibility. Building intersections do not confirm occupancy or damage. Prioritization must disclose rules and uncertainty and must not imply validated casualty probability or rescue instructions.

## Software assurance requirements

Executable logic changes require contract-derived property-based testing, including valid, invalid and boundary input generation, shrinking and reproducible failure artifacts. Reviewers must challenge another agent's implementation independently when reviewing its work. Malformed-input boundaries require bounded fuzzing with documented limits and replayable corpora. Example-based regression tests remain useful after a generated failure is minimized.

These are requirements for future implementation. This repository currently has no application test suite, executed application fuzzing campaign or measured application coverage. Documentation-only changes receive structural, consistency and link validation rather than fabricated application tests. The detailed workflows live in the local `context/` skills.

## Performance and operation still to be measured

Set separate objectives for read APIs, initial map rendering, exposure queries and SAR processing. Include data volume, concurrency, hardware/network, cold/warm cache, percentiles and error rates. There are no measured service-level guarantees, load tests or deployed services yet.

Evaluate heavy SAR processing as asynchronous work. A fast interface response does not make the observation recent. Distinguish orbital revisit, publication latency, computation time and application response time.

## Open risks and decisions

| Risk or decision | Research action | Fallback if unresolved |
| --- | --- | --- |
| No comparable NISAR pair | Search catalog and inspect product metadata | Disclose limitation; historical other-mission demo or labeled simulation |
| Incomplete/outdated cartography | Check coverage, terms and local samples | Restrict indicators to known coverage |
| No independent reference | Seek contemporaneous products or expert interpretation | Exploratory study without operational accuracy claims |
| API access unavailable | Test authorized access and actual formats | Traceable manual import; automated integration remains pending |
| UI/3D appears more precise than data | Compare visualization scale with source resolution | Restrict depiction and communicate uncertainty |
| Undefined budget/environment | Measure a small crop and estimate explicit scenarios | Simple architecture and precomputed artifacts |

AR, digital twins, forecasting, brigade dispatch and external alerts require additional research. They do not block demonstration of the core prototype.
