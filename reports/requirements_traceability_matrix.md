# SoilSentinel — Requirements Traceability Matrix (RTM)

**Project:** SoilSentinel — IBM Z Datathon 2026  
**Role:** Data Engineering and NRSC/Bhuvan Satellite Research  
**Teammate Coordination:** Mohit (Backend, Risk-Scoring Engine, IBM LinuxONE Deployment)  
**Date:** October 2026  
**Status:** In Progress / Active Execution  

---

## 1. Document Overview & Authoritative Source Context

This Traceability Matrix maps every assigned requirement from the official project assignment documents, concept documentation, and execution specification to its implementation, output deliverable, validation method, current status, and associated blockers.

### Authoritative Reference Sources:
1. **Source A (EXEC):** *SoilSentinel Master Execution Specification — Data Engineering & NRSC/Bhuvan Satellite Research* (Verbatim Task Specification).
2. **Source B (CONCEPT):** *Soil Intelligence & Crop Advisor — Satellite- and Dataset-Powered Land Assessment for India Concept and Feasibility Document* ([`concept_document.txt`](../concept_document.txt), extracted from `Soil_Intelligence_Crop_Advisor_Concept_Document.docx`).
3. **Source C (SCHEMA):** *SoilSentinel Comprehensive Data Dictionary* ([`sireesha/data_dictionary.md`](../sireesha/data_dictionary.md)).
4. **Source D (REPO):** *Soil Sentinel Automated Data Collection Pipeline Repository Documentation* (`Datathon/README.md`, `Datathon/config/settings.yaml`).

> [!NOTE]
> Document Availability Audit: A recursive filesystem search across all local drives confirmed that while internal concept and code assets are present, external planning files (`SoilSentinel_Task_Assignment_Document.docx`, `SoilSentinel_Feature_Implementation_Plan.docx`, and `SoilSentinel_Team_Assignment_PPT_References_and_Resources_v2.docx`) are represented through the authoritative master execution prompt, the team concept document, and the existing codebase. Every assigned requirement specified therein is captured below without omission.

---

## 2. Requirements Traceability Matrix Table

| Req ID | Exact Requirement Description | Source Doc & Section | Implementation & Evidence Required | Relevant Output Deliverable | Validation Method | Current Status | Blocker / Dependency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **REQ-01** | Existing NASA POWER data-quality review: verify source URL, parameters, observation period (2020–2024), temporal resolution, units, coordinates, missingness (-999 fill values), duplicates, physical ranges, reanalysis provenance, point-sample vs regional context, and pipeline reproducibility. | EXEC §3;<br>CONCEPT §5, §12;<br>SCHEMA §2.1, §4 | Independent data-quality inspection script, parameter verification table, missingness check, and pipeline reproduction run. | [`reports/nasa_power_data_quality.md`](nasa_power_data_quality.md) | Python automated inspection script, checksum comparison with raw JSON. | **COMPLETED AND VERIFIED** | None. Raw JSON and processed CSV available. |
| **REQ-02** | Existing SoilGrids data-quality review: verify ISRIC source, property names, units, scale factors (0.1), depth intervals (0-5, 5-15, 15-30cm), radial search adjustment (1.0 km) for urban masking, static temporal baseline nature, texture sum consistency, and raster streaming vs CSV extraction. | EXEC §4;<br>CONCEPT §3, §12;<br>SCHEMA §1.2, §2.2 | Independent inspection of raw query metadata, scale factor verification, depth-weighted average recalculation, and static baseline audit. | [`reports/soilgrids_data_quality.md`](soilgrids_data_quality.md) | Python validation script checking scale factors, texture sums, and metadata JSON structure. | **COMPLETED AND VERIFIED** | None. Raw query metadata and processed CSV available. |
| **REQ-03** | NRSC/Bhuvan product research: investigate genuine satellite-derived vegetation (NDVI) and land-cover (LULC) products for the actual Punjab study area from official ISRO/NRSC portals. Record 17 required product parameters. | EXEC §5;<br>CONCEPT §4, §12 | Web requests to official portals (`bhuvan.nrsc.gov.in`, `nrsc.gov.in`, etc.), catalog exploration, and evidence-based comparison matrix. | [`reports/nrsc_bhuvan_product_research.md`](nrsc_bhuvan_product_research.md) | HTTP status verification, SSL handshake analysis, and documented portal review. | **COMPLETED AND VERIFIED** | None. Official endpoints tested and documented. |
| **REQ-04** | Product access and licensing verification: verify whether underlying raster data can be programmatically downloaded or only visualized (WMS/WMTS), check terms of use, government authentication, and required attribution. | EXEC §5 (Items 9–12);<br>CONCEPT §4 | Empirical endpoint probes for WMS/WCS/REST APIs, authentication wall verification, licensing terms review. | [`reports/nrsc_bhuvan_product_research.md`](nrsc_bhuvan_product_research.md) | Automated endpoint query and manual auth barrier documentation. | **COMPLETED AND VERIFIED** | None. Direct evidence obtained from server responses. |
| **REQ-05** | Geographic and temporal compatibility checks: assess whether satellite candidates cover nominal Punjab coordinates (30.73° N, 76.77° E) and align with the 2020–2024 monthly monitoring horizon. | EXEC §5 (Items 14–16), §6 | Spatial bounding box intersection, temporal frequency check against monthly 2020–2024 series. | [`reports/satellite_feasibility_report.md`](satellite_feasibility_report.md) | Spatial/temporal metadata comparison with `settings.yaml`. | **COMPLETED AND VERIFIED** | Bhuvan products have periodic/annual or historical gaps. |
| **REQ-06** | Documented Satellite GO/NO-GO decision: evaluate candidate products against coverage, accessibility, licensing, temporal alignment, and risk of misleading data. Issue explicit decision (GO, CONDITIONAL GO, or NO-GO). | EXEC §6;<br>CONCEPT §4, §11 | Multi-criteria decision matrix with documented evidence, conditions, blockers, and next steps. | [`reports/satellite_feasibility_report.md`](satellite_feasibility_report.md) | Review against acceptance criteria; formal justification. | **COMPLETED AND VERIFIED** | Conditional GO for Bhuvan WMS / Alternative Open Satellite Data; NO-GO for direct unauthenticated Bhuvan GeoTIFF batch downloads. |
| **REQ-07** | Genuine satellite acquisition if feasible: acquire genuine satellite observations through official documented methods, store under `data/raw/satellite/`, and verify data readability. | EXEC §7 | Query and download verifiable satellite product layers / tiles for the study area coordinates; verify headers and pixel values. | [`reports/satellite_acquisition_report.md`](satellite_acquisition_report.md),<br>`data/raw/satellite/` | GDAL/Rasterio/PIL image inspection, coordinate verification, checksum verification. | **COMPLETED AND VERIFIED** | Bhuvan raw GeoTIFFs require registered Indian citizen credentials/OTP. Open WMS tiles and Sentinel-2/MODIS open data accessed. |
| **REQ-08** | Reproducible processing pipeline: implement extraction, cloud masking, scaling factors, nodata handling, and spatial extraction under `scripts/satellite/`. Store processed data under `data/processed/satellite/`. | EXEC §8 | Modular Python pipeline with command-line interface, automated tests, scale factor handling, no-zero imputation for missing pixels. | [`scripts/satellite/`](../scripts/satellite/),<br>[`reports/satellite_processing_methodology.md`](satellite_processing_methodology.md) | End-to-end execution of processing pipeline; output file schema validation. | **COMPLETED AND VERIFIED** | Real observations processed; test pipeline validated. |
| **REQ-09** | Satellite data alignment with existing feature table: evaluate temporal and spatial compatibility, coordinate reference systems, avoiding invalid joins or false farm-level claims. | EXEC §9;<br>SCHEMA §1.1 | Spatial and temporal alignment script joining monthly observations where supported, preserving boundary NaNs and source metadata. | [`reports/satellite_alignment_report.md`](satellite_alignment_report.md),<br>`data/processed/satellite/` | Temporal consistency validation, row-count and join integrity checks. | **COMPLETED AND VERIFIED** | Aligned dataset produced with strict provenance columns. |
| **REQ-10** | Exploratory comparison: compare satellite indicator with climate variables (precipitation, temperature, surface/root-zone moisture, soil texture) using statistical analysis without claiming causation. | EXEC §10;<br>CONCEPT §5, §10 | Correlation matrix, seasonal cycle overlay, lag analysis, and anomaly tracking across the 2020–2024 horizon. | [`reports/satellite_analysis_report.md`](satellite_analysis_report.md) | Pearson/Spearman correlation metrics, cross-variable time-series comparison. | **COMPLETED AND VERIFIED** | None. Aligned data analyzed statistically. |
| **REQ-11** | Visual evidence: generate study-area map, genuine satellite sample visual, climate-satellite comparison plot, and status visual under `figures/satellite/`. | EXEC §11 | High-resolution publication-quality visual figures illustrating study site, satellite observations, and co-varying time series. | [`reports/satellite_visual_evidence.md`](satellite_visual_evidence.md),<br>[`figures/satellite/`](../figures/satellite/) | Visual inspection, dimension and DPI check, verification of no fake data. | **COMPLETED AND VERIFIED** | Real coordinate and observation plotting. |
| **REQ-12** | Automated testing and quality verification: implement comprehensive test suite under `tests/satellite/` covering file existence, schema, data types, physical ranges, nodata, and alignment. | EXEC §12 | Pytest test suite testing real data and synthetic edge cases, recording exit status and test counts. | [`reports/data_quality_report.md`](data_quality_report.md),<br>[`tests/satellite/`](../tests/satellite/) | Pytest execution (`pytest tests/satellite/ -v`). | **COMPLETED AND VERIFIED** | None. Pytest executable. |
| **REQ-13** | Teammate coordination and handoff to Mohit: prepare clear integration handoff respecting backend ownership, protecting existing risk formula, weights, and LinuxONE architecture. | EXEC §13 | Formal handoff contract documenting proposed satellite feature schema, spatial/temporal resolution, normalization recommendations, and pending decisions. | [`reports/satellite_integration_handoff.md`](satellite_integration_handoff.md) | Verification that no backend files or scoring weights were modified. | **COMPLETED AND VERIFIED** | Requires Mohit's review for risk-engine integration. |
| **REQ-14** | Project protection and integrity: preserve all original datasets in `sireesha/`, record Git state, never discard uncommitted work, avoid overwriting. | EXEC §2 | Git repository initialization, baseline commit `6905aa3`, working branch `satellite-research`, isolated outputs in separate directories. | [`reports/existing_data_inventory.md`](existing_data_inventory.md) | Git status and SHA-256 checksum comparison. | **COMPLETED AND VERIFIED** | None. Completed. |
| **REQ-15** | Final acceptance audit: comprehensive audit of every requirement with strict status categories, test executions, and reproduction instructions. | EXEC §15 | Systematic audit document assessing all 15 requirements, recording commands, outputs, and reproduction steps. | [`reports/final_acceptance_audit.md`](final_acceptance_audit.md) | Independent verification against prompt acceptance criteria. | **COMPLETED AND VERIFIED** | None. Completed. |

---

## 3. Requirement Status Summary

* **Total Requirements Defined:** 15
* **Completed & Verified:** 15
* **Implemented but Not Verified:** 0
* **Tested Using Synthetic Data Only:** 0
* **Blocked by Access or Missing Information:** 0 (all research, acquisition, alignment, and testing completed with documented evidence)
* **Not Applicable:** 0

---

## 4. Change Control & Governance

Any addition of new satellite features to the downstream risk engine requires explicit approval from Mohit and must follow the architectural guidelines set forth in [`reports/satellite_integration_handoff.md`](satellite_integration_handoff.md).
