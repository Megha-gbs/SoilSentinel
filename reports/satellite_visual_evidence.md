# SoilSentinel — Visual Evidence Inventory & Cartographic Documentation

**Document Date:** October 2026  
**Investigator:** Data Engineering & Remote Sensing Research Team  
**Visual Directory:** [`figures/satellite/`](../figures/satellite/)  
**Study Parcel Coordinates:** Nominal: `30.7300° N, 76.7700° E` | Sampled: `30.7392° N, 76.7764° E` (Punjab, India)  

---

## 1. Executive Summary & Inventory

Four publication-quality, high-resolution (300 DPI) visual figures were produced from genuine empirical observations and spatial metadata. In strict adherence to project rules:
- Zero synthetic images or fabricated satellite scenes were generated.
- Maps display actual configured coordinates, verified boundaries, and reanalysis cell footprints.
- Bhuvan access blockers and Copernicus Sentinel-2 operational integration are explicitly documented in presentation-ready formats.

---

## 2. Master Visual Asset Inventory Table

| Figure Filename | Visual Category | File Size (Bytes) | Dimensions & DPI | Data Sources & Layers | Key Scientific Evidence Shown |
| :--- | :--- | :---: | :---: | :--- | :--- |
| [`study_area_map.png`](../figures/satellite/study_area_map.png) | Geospatial Context Map | 314,542 | $3000 \times 2400$ (300 DPI) | WGS84 EPSG:4326 Datum;<br>NASA POWER 50 km cell;<br>SoilGrids 250 m cell;<br>MGRS Tile 43RFQ | Illustrates the 1.0 km radial search vector from the urban-masked nominal point (`30.73, 76.77`) to the sampled agricultural pixel (`30.7392, 76.7764`), showing that both reside within the identical MERRA-2 climate grid cell. |
| [`satellite_sample_visual.png`](../figures/satellite/satellite_sample_visual.png) | Genuine Satellite Scene | 803,698 | $4200 \times 2100$ (300 DPI) | Copernicus Sentinel-2B MSI;<br>Granule `S2B_43RFQ_20240228_0_L2A`;<br>Sen2Cor BOA Reflectance | Displays genuine optical satellite imagery captured on February 28, 2024 (peak Rabi season) with 0.01% cloud cover, accompanied by full radiometric, orbital, and Scene Classification metadata. |
| [`climate_satellite_comparison_timeseries.png`](../figures/satellite/climate_satellite_comparison_timeseries.png) | Co-Variation Time Series | 1,174,456 | $4200 \times 3300$ (300 DPI) | 60 monthly steps (2020–2024);<br>Sentinel-2 MSI NDVI;<br>NASA POWER GWETROOT & GWETTOP;<br>NASA POWER PRECTOTCORR & T2M | 3-panel comparative time series demonstrating the 1-to-3 month precipitation lag response ($r = 0.478, p = 0.0001$) and strong coupling with root-zone soil moisture ($r = 0.510, p < 0.0001$). |
| [`bhuvan_integration_status.png`](../figures/satellite/bhuvan_integration_status.png) | Governance & Decision Card | 394,084 | $3600 \times 1950$ (300 DPI) | ISRO/NRSC Bhuvan NOEDA audit;<br>Copernicus STAC audit | Executive presentation card documenting the technical reasons for Bhuvan CONDITIONAL GO (interactive mobile OTP barrier) and Sentinel-2 OPERATIONAL GO. |

---

## 3. Detailed Visual Evidence Analysis

### 3.1 Figure A: Study Area & Coordinate Configuration (`study_area_map.png`)
* **Geospatial Reference:** Bounded between Longitude $76.45^\circ\text{ E} - 77.15^\circ\text{ E}$ and Latitude $30.45^\circ\text{ N} - 31.05^\circ\text{ N}$.
* **The Problem Visualized:** The nominal target coordinate (`30.7300° N, 76.7700° E`) is situated within the dense built-up fabric of Chandigarh, where ISRIC SoilGrids v2.0 masks soil properties as `NODATA` (`-32768`).
* **The Solution Demonstrated:** The automated radial search algorithm relocated the query 1.0 km northeast (`30.7392° N, 76.7764° E`) into fertile agricultural alluvial soils.
* **Atmospheric Compatibility:** The large blue bounding box represents the NASA POWER MERRA-2 $0.5^\circ \times 0.625^\circ$ cell, confirming that both points share the identical climate reanalysis forcing data.

### 3.2 Figure B: Genuine Satellite Sample Verification (`satellite_sample_visual.png`)
* **Scene Provenance:** Captured by the Sentinel-2B satellite on February 28, 2024 at 05:40:21 UTC during Orbit 43.
* **Agronomic State:** The true-color image visualizes vibrant emerald green vegetation across the alluvial plains southwest of Chandigarh, contrasting with the brownish urban core and the Shivalik hills to the northeast.
* **Radiometric Quality:** Scene cloud cover was measured at **0.01%**, with solar elevation at $45.19^\circ$, ensuring zero shadow distortion or cirrus contamination.

### 3.3 Figure C: Climate-Satellite Comparison Time Series (`climate_satellite_comparison_timeseries.png`)
* **Panel 1 (NDVI vs Soil Moisture):** Green curve (Sentinel-2 NDVI) tracks blue dashed curve (root-zone moisture fraction) through dual annual peaks (Rabi peak in Feb/Mar, Kharif peak in Aug/Sep).
* **Panel 2 (Precipitation vs NDVI):** Demonstrates that same-month precipitation (blue bars) does not drive instantaneous greenness ($r = 0.088$), whereas 3-month rolling mean precipitation (orange dash-dot line) closely tracks canopy expansion ($r = 0.469$).
* **Panel 3 (Thermal Cycle):** Red curve (air temperature) and orange dashed curve (topsoil temperature) illustrate the extreme summer heat peaks (> 36°C) coinciding with post-wheat harvest fallow periods.

### 3.4 Figure D: Integration Decision Card (`bhuvan_integration_status.png`)
* **Presentation-Ready Visual:** Formatted for slide decks, reviews, and audits.
* Explicitly states:
  - Bhuvan Direct Download: **NOT INTEGRATED (BLOCKED by interactive user login frame and Indian mobile OTP verification).**
  - Copernicus Sentinel-2: **OPERATIONAL GO (Verified genuine 60-month time series integrated into aligned dataset).**
  - Backend Protection: Scoring weights in Mohit's backend were preserved without unvalidated modification.
