# SAR foundations and software selection

> Current baseline — November 15, 2026 (Lima): **Ayumi** is the locally runnable product. > Work is limited to small residential–ravine/mountain screening windows around Canchaque, El Faique and Huancabamba; the whole Piura department and Tumbes are not offered. > Windows are locators, not official hazard boundaries or planting approvals. See [current implementation status](IMPLEMENTATION_STATUS.md) and [ADR 0006](decisions/0006-ayumi-bounded-workflow-and-municipal-report.md).

Reviewed November 14, 2026 for RAÍZ-SAR AI. **SAR** means Synthetic Aperture Radar. This reference informs implementation; it does not validate a local planting model.

## Earthdata concepts relevant to this project

NASA's [SAR introduction](https://www.earthdata.nasa.gov/learn/earth-observation-data-basics/sar) explains active radar observations, wavelength-dependent interactions, polarization, scattering, geometry, speckle and interferometry. Its L-band range is 15–30 cm; S-band is 7.5–15 cm. Longer wavelength does not establish a fixed soil measurement depth. Co-polarized and cross-polarized returns respond differently to surface, volume and double-bounce scattering; they are not unique labels for moisture or roots. Incidence angle, layover and shadow affect interpretation. Pixel spacing differs from effective resolution. Speckle is intrinsic to coherent imaging. InSAR uses phase, whereas this project's initial path uses calibrated backscatter.

The page's **Data Availability** table also lists processing software, including pyroSAR, PyRAT and ISCE. Some mission wording is historical; use current mission/product documentation for availability, not the introductory page alone.

The page was read directly in the browser after the automated reader returned HTTP 403. This was a reader-access issue, not evidence that Earthdata was unavailable publicly.

## Project processing contract

Use [NISAR GCOV](https://nisar-docs.asf.alaska.edu/gcov/) as the selected initial product family, subject to local acquisition and quality verification. It already contains calibrated, terrain-corrected covariance/backscatter information. Do not repeat raw-data calibration/RTC by default. Available channels depend on acquisition mode; inspect actual HDF5 datasets and quality metadata. Verify current [collection maturity](https://nisar-docs.asf.alaska.edu/availability-overview/) and [mission band/access coverage](https://science.nasa.gov/mission/nisar/mission-overview/) before designing a local S-band or soil-moisture dependency.

1. Discover candidate products with `asf_search`; use `earthaccess` for Earthdata authentication/CMR and ancillary collections. Keep provider credentials server-side.
2. Read only required HDF5 windows/chunks with `h5py`. Extract actual coordinates, CRS, fill values, masks, acquisition/processing version and backscatter normalization.
3. Preserve the documented gamma0/sigma0 convention. A positive power/intensity value converts with `10 * log10(power)`; do not apply the amplitude formula blindly. Mask invalid/nonpositive values before conversion and retain the linear source.
4. Align comparable dates, channels and grids. Use Rasterio for raster masks, transforms, reprojection and derived GeoTIFF/COG; use NumPy/SciPy for bounded array operations. Do not smooth across nodata/exclusion boundaries or filter twice without justification.
5. Use GeoPandas/Shapely for vector eligibility/intersections and pyproj for CRS transformations. Confirm source coordinates; candidate metric CRSs are EPSG:32718 for the supplied Carabayllo locator and EPSG:32717 for lower Piura. Verify every actual AOI rather than assigning one CRS globally.
6. Publish clipped, versioned GeoJSON and small raster overlays with explicit legend/normalization. Keep original pixels, derived indicators, field records and AI scenarios distinct.

This pipeline produces evidence for specialist assessment. It does not automatically retrieve buried water pockets, soil dielectric constant, survival probability, roots or guaranteed slope stability. RVI requires a formula compatible with the available channels and linear units; missing inputs disable that calculation rather than being filled with zero.

## Software from the Earthdata table: decisions

| Tool | Evidence and relevant role | Decision for the initial stack |
| --- | --- | --- |
| [pyroSAR](https://pyrosar.readthedocs.io/en/latest/) | Python orchestration/metadata framework with SNAP/GAMMA integration; [installation](https://pyrosar.readthedocs.io/en/latest/general/installation.html) adds GDAL and processing-environment considerations | Optional isolated Sentinel-1/preprocessing path after actual product support is checked; not a required reader for already corrected GCOV |
| [PyRAT](https://github.com/birgander2/PyRAT) | Python SAR postprocessing with desktop/Qt and block-processing workflow | Specialist exploration only; do not make the API depend on a desktop GUI |
| [ISCE2](https://github.com/isce-framework/isce2) | SAR/InSAR processing environment | Excluded from initial amplitude-only workflow; an interferometric requirement needs a separate ADR |
| [ISCE3](https://github.com/isce-framework/isce3) | NISAR-related SAR processing toolkit, separate from the ISCE2 link in the generic table | Optional for a demonstrated low-level processing requirement; avoid a compiler/processor stack solely to read Level-2 products |
| [SNAP](https://step.esa.int/main/download/snap-download/) | Desktop/batch SAR preprocessing and specialist inspection | Environmental-engineer tool or isolated Sentinel-1 adapter; not proof of automatic NISAR compatibility |
| [HyP3](https://hyp3-docs.asf.alaska.edu/) | Managed SAR processing, depending on supported job/product and access | Optional external preprocessing; credentials, quotas and product support must be verified |
| [PolSARpro](https://step.esa.int/main/download/polsarpro-v6-0-biomass-edition/) | Specialist polarimetric analysis | Research tool, outside the web/API critical path |
| DORIS / GMTSAR / SNAPHU | Interferometric workflows listed by Earthdata | Not selected because the current MVP does not require phase unwrapping or displacement processing |
| h5py / Rasterio / NumPy / GeoPandas | Selected HDF5/raster/numerical/vector libraries; not all are listed in that introductory table | Core implementation libraries, with pinned versions and explicit processing responsibilities |

The choice is based on the selected product level and team/timebox, not a claim that unselected tools are inferior. pyroSAR package metadata reported 0.40.0 while its documentation landing page displayed 0.39 during review; recheck the exact release and dependencies before adopting the optional path.

## Data availability checklist

Record dataset/collection ID, granule ID, access URL, terms, acquisition time, band/channel, orbit/geometry, version/maturity, CRS, grid spacing, normalization, valid coverage and known issues. Distinguish catalog discovery, authorized download, inspection and actual processing. Never use a generic mission table as evidence of a suitable local time series.

No local scene was downloaded or processed during this stack-definition task. The concrete software decision is in [the stack specification](TECHNOLOGY_STACK.md) and [ADR 0001](decisions/0001-technology-stack.md).

## Free real-data sources verified on November 15, 2026

| Source | Access | Over lower Piura | Role |
| --- | --- | --- | --- |
| NISAR L2 GCOV (ASF) | Earthdata Login for download; catalog open | 21 granules 2026-06-21 → 2026-10-31, 20 `DHDH` | Quantitative backscatter after download |
| GIBS `NISAR_L2_Geocoded_Polarimetric_Covariance` | Open WMTS, `Level13` | Valid tiles June–October 2026 | False-colour map display |
| OPERA RTC-S1 (ASF) | Earthdata Login for download | 119 granules January–May 2026 | Rainy-season before/after (C-band) |
| GIBS `OPERA_L2_Radiometric_Terrain_Corrected_SAR_Sentinel-1` | Open WMTS, `Level12` | Valid tiles 2026-02-10/13/22 | Rainy-season display |
| Copernicus DEM GLO-30 | Anonymous COG on AWS | Covered (surface model, includes canopy/buildings) | Slope, terrain, AR mesh |
| NASA POWER daily `PRECTOTCORR` | Open API, no key | Covered (MERRA-2 grid, coarse) | Rain timing, modeled |

GIBS tiles are colour-mapped visualizations, never sampled as backscatter values. See [ADR 0002](decisions/0002-map-first-frontend-and-real-data.md).