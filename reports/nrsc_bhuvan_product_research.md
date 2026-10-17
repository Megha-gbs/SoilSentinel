# SoilSentinel — NRSC/Bhuvan Earth Observation Product Research & Feasibility Assessment

**Audit Date:** October 2026  
**Investigator:** Data Engineering & Geospatial Remote Sensing Team  
**Study Area:** Nominal Coordinates `30.7300° N, 76.7700° E` | Sampled Agricultural Coordinates `30.7392° N, 76.7764° E` (Indo-Gangetic Plains, Punjab)  
**Target Horizon:** Monthly 2020–2024 (60 continuous months)  

---

## 1. Executive Summary & Regulatory Investigation

To evaluate the feasibility of integrating genuine Indian satellite remote sensing products into SoilSentinel, a thorough investigation was conducted across official portals of the **National Remote Sensing Centre (NRSC)** and **Indian Space Research Organisation (ISRO)**:
- Bhuvan Geoportal (`https://bhuvan.nrsc.gov.in/`)
- NRSC Corporate Portal (`https://www.nrsc.gov.in/`)
- Bhuvan Open Data Store 1 & 2 (`https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore.php`, `bhuvanstore2.php`)
- Bhuvan NOEDA Download Portal (`https://bhuvan-app3.nrsc.gov.in/data/download/index.php`)
- NRSC Soils Applications & Degradation Mapping (`https://www.nrsc.gov.in/nrscnew/Apps_Soils_Apps.php?lang_code=en`)
- NRSC Soils Portals (`https://www.nrsc.gov.in/nrscnew/Apps_Soils_Portals.php`)
- NRSC Annual Land Use / Land Cover (LULC) Atlas of India (`https://www.nrsc.gov.in/nrscnew/resources_atlas_LULC.php`)

### Key Empirical Findings:
1. **Accessibility & Download Restrictions:** The official raw raster download portal (Bhuvan NOEDA) enforces strict user authentication (`bhuvanusername` session validation, captcha, and OTP verification linked to Indian mobile credentials). **No open, unauthenticated REST API exists for direct script-based batch downloading of raw GeoTIFF rasters from NRSC.**
2. **Visual vs. Analytical Data:** Public Web Map Services (WMS/WMTS) hosted on Bhuvan are designed for rendering visualization tiles (RGB PNG/JPEG). While tile rendering can be captured for mapping, raw digital surface reflectance numbers (DN) and calibrated floating-point NDVI arrays are masked behind the authenticated portal.
3. **Temporal Incompatibility of NRSC LULC & Degradation Mapping:**
   - The *NRSC Annual LULC 1:250,000 (AWiFS 56 m)* dataset has completed 17 annual cycles from 2005–06 to 2022–23. It provides **annual and seasonal snapshots (Kharif/Rabi)**, NOT a 60-month continuous time series.
   - The *NRSC Land Degradation Map 1:50,000 (LISS-III)* was produced in decadal cycles (Cycle 1: 2005–06; Cycle 2: 2015–16). It is a static historical polygon inventory, not a dynamic monthly monitoring series.
4. **Cloud Contamination in Optical Sensors:** Optical sensors (Resourcesat AWiFS, LISS-III, Sentinel-2) suffer from persistent cloud obscuration during the southwest monsoon (July–August), requiring quality masking and composite aggregation rather than raw daily/monthly single-date observations.

---

## 2. In-Depth Technical Specification of Serious Satellite Candidates

Every serious candidate product was evaluated against the 17 authoritative parameters mandated by the execution specification.

---

### Candidate 1: NRSC/ISRO Annual Land Use and Land Cover (LULC 1:250,000 / 56 m)

| # | Parameter | Verified Official Evidence & Specification |
| :-: | :--- | :--- |
| 1 | **Exact Product Name** | Annual Land Use and Land Cover (LULC) 1:250,000 (Natural Resources Census Programme) |
| 2 | **Official Organisation & Page** | NRSC, ISRO, Department of Space: `https://www.nrsc.gov.in/nrscnew/resources_atlas_LULC.php` |
| 3 | **Satellite / Sensor** | Resourcesat-1, Resourcesat-2, Resourcesat-2A / AWiFS (Advanced Wide Field Sensor) |
| 4 | **Geographic Coverage** | National coverage (All-India wall-to-wall), including Punjab |
| 5 | **Observation Dates & Range**| 2005–06 to 2022–23 (17 annual cycles completed) |
| 6 | **Update Frequency** | Annual cycle with seasonal subsets (August–September Kharif, December–January Rabi) |
| 7 | **Spatial Resolution / Scale**| 56 metres spatial resolution / 1:250,000 map scale |
| 8 | **File Format** | GeoTIFF / Shapefile (vector polygons on Bhuvan Thematic portal) |
| 9 | **Access / Download Method** | Bhuvan Thematic Services & formal request through NRSC Data Dissemination Centre |
| 10 | **Data Download vs Visualization**| Visualized openly on Bhuvan; underlying raster download requires authorized credentials |
| 11 | **Licence & Permitted Use** | Government of India Remote Sensing Data Policy (RSDP); educational/academic research permitted with registration |
| 12 | **Required Attribution** | "National Remote Sensing Centre (NRSC), ISRO, Annual LULC Atlas of India, Department of Space, Govt. of India" |
| 13 | **Quality Flags & Cloud Limitations**| Multi-temporal rule-based classification; monsoon months (July–August) subject to cloud interpolation |
| 14 | **Known Restrictions** | 2023–2024 complete national cycles are not yet published in public domain; annual periodicity cannot support monthly time series |
| 15 | **Suitability for Study Area**| Highly suitable spatially (resolves agrarian parcel patterns in Punjab) |
| 16 | **Compatibility with 2020–2024 Monthly**| **INCOMPATIBLE WITH MONTHLY TIME SERIES.** Produces only 1 annual classification per year. |
| 17 | **Supports Intended Analysis?**| Supports static agricultural baseline masking, but **cannot provide monthly dynamic risk variation**. |

---

### Candidate 2: NRSC/ISRO Land Degradation Mapping (1:50,000 Scale)

| # | Parameter | Verified Official Evidence & Specification |
| :-: | :--- | :--- |
| 1 | **Exact Product Name** | Land Degradation Mapping of India (1:50,000 Scale) |
| 2 | **Official Organisation & Page** | NRSC, ISRO: `https://www.nrsc.gov.in/nrscnew/Apps_Soils_Apps.php?lang_code=en` |
| 3 | **Satellite / Sensor** | IRS-P6 (Resourcesat-1) and Resourcesat-2 / LISS-III (Linear Imaging Self-Scanning Sensor) |
| 4 | **Geographic Coverage** | Entire country (All-India), hosted on Bhuvan-Salt Affected and Water Logging portal |
| 5 | **Observation Dates & Range**| Cycle 1: 2005–06; Cycle 2: 2015–16 |
| 6 | **Update Frequency** | Decadal (~10-year cycle) |
| 7 | **Spatial Resolution / Scale**| 23.5 metres resolution / 1:50,000 map scale |
| 8 | **File Format** | OGC WMS visualization layers, ESRI Shapefile vector atlases |
| 9 | **Access / Download Method** | Bhuvan Web GIS / Soil Portals (`Apps_Soils_Portals.php`) |
| 10 | **Data Download vs Visualization**| Visual layer and state atlas report; underlying spatial shapefile restricted |
| 11 | **Licence & Permitted Use** | NRSC / Ministry of Agriculture & Farmers Welfare internal planning; public view on Bhuvan |
| 12 | **Required Attribution** | "NRSC/ISRO, Land Degradation Mapping of India at 1:50,000 Scale" |
| 13 | **Quality Flags & Cloud Limitations**| Visual interpretation coupled with ground truth; 36 degradation classes across 8 processes |
| 14 | **Known Restrictions** | **Static decadal mapping.** No observations exist for 2020–2024. |
| 15 | **Suitability for Study Area**| Spatial scale (23.5 m) covers Punjab plains excellently |
| 16 | **Compatibility with 2020–2024 Monthly**| **COMPLETELY INCOMPATIBLE.** 2015–16 dataset cannot be interpolated to 2020–2024 monthly steps. |
| 17 | **Supports Intended Analysis?**| Invaluable for qualitative historical reference, but prohibited as dynamic monthly input. |

---

### Candidate 3: Bhuvan / NICES Resourcesat AWiFS Normalized Difference Vegetation Index (NDVI)

| # | Parameter | Verified Official Evidence & Specification |
| :-: | :--- | :--- |
| 1 | **Exact Product Name** | Resourcesat AWiFS 15-Day Composite NDVI |
| 2 | **Official Organisation & Page** | Bhuvan NOEDA & NICES (National Information System for Climate and Environment Studies): `https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore.php` |
| 3 | **Satellite / Sensor** | Resourcesat-2 / Resourcesat-2A AWiFS (B2: Green, B3: Red, B4: NIR, B5: SWIR) |
| 4 | **Geographic Coverage** | Indian Landmass (includes Punjab study region) |
| 5 | **Observation Dates & Range**| 2012 to present (periodic releases) |
| 6 | **Update Frequency** | 15-day Maximum Value Composite (MVC) |
| 7 | **Spatial Resolution / Scale**| 56 metres |
| 8 | **File Format** | GeoTIFF / HDF-5 |
| 9 | **Access / Download Method** | Bhuvan NOEDA (`bhuvan-app3.nrsc.gov.in/data/download/index.php`) via authenticated session |
| 10 | **Data Download vs Visualization**| Download restricted behind interactive login frame (`load_video('#LoginFrame')`) |
| 11 | **Licence & Permitted Use** | ISRO Open Data Archive Terms; Indian citizens with registered mobile verification |
| 12 | **Required Attribution** | "National Remote Sensing Centre (NRSC), Indian Space Research Organisation (ISRO)" |
| 13 | **Quality Flags & Cloud Limitations**| Maximum Value Composite (MVC) algorithm reduces cloud contamination, but residual cirrus flags apply |
| 14 | **Known Restrictions** | Script-based automated API queries fail with 401/302 redirect unless authenticated session cookies are injected; periodic archival lags |
| 15 | **Suitability for Study Area**| High agronomic fidelity for Indo-Gangetic wheat-rice phenology |
| 16 | **Compatibility with 2020–2024 Monthly**| Can be temporally aggregated from 15-day MVC to monthly, but archival coverage has historical download bottlenecks |
| 17 | **Supports Intended Analysis?**| Supports vegetation vigour monitoring, contingent on authenticated credentials |

---

### Candidate 4: INSAT-3D / 3DR Imager Land Surface NDVI

| # | Parameter | Verified Official Evidence & Specification |
| :-: | :--- | :--- |
| 1 | **Exact Product Name** | INSAT-3D/3DR Daily / 10-Day Land Surface Vegetation Index |
| 2 | **Official Organisation & Page** | ISRO / MOSDAC (Meteorological & Oceanographic Satellite Data Archival Centre) & Bhuvan |
| 3 | **Satellite / Sensor** | INSAT-3D and INSAT-3DR Geostationary Imager |
| 4 | **Geographic Coverage** | Indian Subcontinent and surrounding oceanic disc |
| 5 | **Observation Dates & Range**| 2014 to present |
| 6 | **Update Frequency** | Daily / 10-day composite |
| 7 | **Spatial Resolution / Scale**| 1.0 km (Visible / NIR bands) to 4.0 km |
| 8 | **File Format** | HDF-5 / GeoTIFF |
| 9 | **Access / Download Method** | MOSDAC Open Data API (`mosdac.gov.in`) and Bhuvan Geoprocessing |
| 10 | **Data Download vs Visualization**| Sourced via MOSDAC REST registration token |
| 11 | **Licence & Permitted Use** | MOSDAC Open Data Policy; registration required |
| 12 | **Required Attribution** | "MOSDAC / SAC / ISRO, INSAT-3D Earth Observation Data" |
| 13 | **Quality Flags & Cloud Limitations**| Geostationary high temporal frequency enables frequent clear-sky slots, but coarse resolution |
| 14 | **Known Restrictions**| **Coarse spatial resolution ($1\text{ km} - 4\text{ km}$)** blends agricultural parcels with urban/water features |
| 15 | **Suitability for Study Area**| Moderate (cell size is larger than average parcel, causing mixed-pixel dilution) |
| 16 | **Compatibility with 2020–2024 Monthly**| Temporally compatible across the 60-month horizon |
| 17 | **Supports Intended Analysis?**| Provides regional vegetation trends, but poor spatial discrimination compared to 56m AWiFS or 10m Sentinel |

---

### Candidate 5: Open Spaceborne Alternative — Sentinel-2 MSI Surface Reflectance NDVI (ESA/Copernicus)

| # | Parameter | Verified Official Evidence & Specification |
| :-: | :--- | :--- |
| 1 | **Exact Product Name** | Sentinel-2 MSI Level-2A (Bottom-of-Atmosphere Surface Reflectance) |
| 2 | **Official Organisation & Page** | European Space Agency (ESA) Copernicus Programme / Open Access Hub / STAC API |
| 3 | **Satellite / Sensor** | Sentinel-2A and Sentinel-2B Multi-Spectral Instrument (MSI) |
| 4 | **Geographic Coverage** | Global landmass including Punjab (Tile: `T43SBR`) |
| 5 | **Observation Dates & Range**| 2015 to present (Continuous full coverage 2020–2024) |
| 6 | **Update Frequency** | 5-day revisit cycle with dual satellites |
| 7 | **Spatial Resolution / Scale**| **10 metres** (Band 4 Red: 665 nm; Band 8 NIR: 842 nm) |
| 8 | **File Format** | Cloud-Optimized GeoTIFF (COG) / SAFE format |
| 9 | **Access / Download Method** | Open access via Planetary Computer STAC, Element84 Earth Search, and AWS S3 open data (`sentinel-cogs`) without CAPTCHA |
| 10 | **Data Download vs Visualization**| **Both fully supported:** Direct analytical pixel streaming and full GeoTIFF download |
| 11 | **Licence & Permitted Use** | Open Access (Creative Commons CC-BY 4.0 / EU Copernicus Open Access Policy) |
| 12 | **Required Attribution** | "Contains modified Copernicus Sentinel data [2020–2024], processed by ESA" |
| 13 | **Quality Flags & Cloud Limitations**| Scene Classification Layer (`SCL`) provides cloud, shadow, and cirrus pixel masks at 20 m |
| 14 | **Known Restrictions**| SCL cloud masking must be applied during monsoon months; computation requires band extraction |
| 15 | **Suitability for Study Area**| **Optimal.** 10 m resolution isolates agricultural fields around `30.7392° N, 76.7764° E` without urban bleeding. |
| 16 | **Compatibility with 2020–2024 Monthly**| **100% COMPATIBLE.** Complete 60-month monthly maximum value composite (MVC) readily derived. |
| 17 | **Supports Intended Analysis?**| **YES.** Provides exact calibrated canopy vigour, phenology tracking, and cross-comparison with NASA POWER moisture. |

---

### Candidate 6: Open Spaceborne Alternative — MODIS MOD13Q1 Vegetation Indices (NASA LP DAAC)

| # | Parameter | Verified Official Evidence & Specification |
| :-: | :--- | :--- |
| 1 | **Exact Product Name** | MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061 (`MOD13Q1`) |
| 2 | **Official Organisation & Page** | NASA Land Processes Distributed Active Archive Center (LP DAAC) |
| 3 | **Satellite / Sensor** | Terra MODIS (Moderate Resolution Imaging Spectroradiometer) |
| 4 | **Geographic Coverage** | Global (Tile `h24v05` covers Punjab) |
| 5 | **Observation Dates & Range**| February 2000 to present (Complete 2020–2024 coverage) |
| 6 | **Update Frequency** | 16-day composite |
| 7 | **Spatial Resolution / Scale**| 250 metres |
| 8 | **File Format** | HDF-4 / Cloud-Optimized GeoTIFF via AppEEARS |
| 9 | **Access / Download Method** | NASA Earthdata Login / LP DAAC DAX / Open API |
| 10 | **Data Download vs Visualization**| Full analytical array download and point extraction API |
| 11 | **Licence & Permitted Use** | Open Access (NASA Open Data Policy) |
| 12 | **Required Attribution** | "NASA LP DAAC, MODIS MOD13Q1 Version 6.1" |
| 13 | **Quality Flags & Cloud Limitations**| Pixel reliability layer (`250m_16_days_pixel_reliability`) and composite day of year |
| 14 | **Known Restrictions**| 250 m pixel is coarser than Sentinel-2, but matches SoilGrids 250 m scale identically |
| 15 | **Suitability for Study Area**| Highly suitable for regional vegetation phenology matching SoilGrids spatial footprint |
| 16 | **Compatibility with 2020–2024 Monthly**| **100% COMPATIBLE.** 23 composites per year aggregated to monthly time series. |
| 17 | **Supports Intended Analysis?**| **YES.** Uninterrupted 60-month monthly series with zero missing intervals. |

---

## 3. Systematic Evidence-Based Comparison Matrix

| Candidate Product | Sensor / Platform | Spatial Resolution | Temporal Coverage | 2020–2024 Monthly Alignment | Actual Access Method | Download Barrier | Recommendation |
| :--- | :--- | :---: | :---: | :---: | :--- | :--- | :---: |
| **NRSC Annual LULC** | AWiFS | 56 m | 2005–2023 | **NO-GO** (Annual only) | Bhuvan Thematic Portal | Restricted raster download | **NO-GO for time series** |
| **NRSC Land Degradation**| LISS-III | 23.5 m | 2005, 2015 | **NO-GO** (Decadal snapshots) | Bhuvan Soils Portals | Restricted shapefile download | **NO-GO for time series** |
| **Bhuvan AWiFS NDVI** | AWiFS | 56 m | Periodic | **CONDITIONAL** | Bhuvan NOEDA | Auth wall (User/OTP required) | **CONDITIONAL GO** |
| **Bhuvan INSAT-3D NDVI** | Imager | 1–4 km | 2014–Present | **YES** | MOSDAC / Bhuvan | Registration required; coarse | **RESERVE BACKUP** |
| **Sentinel-2 MSI NDVI** | MSI | 10 m | 2015–Present | **100% COMPATIBLE** | Open STAC / AWS S3 | **ZERO BARRIER** (Public open data) | **PRIMARY OPERATIONAL GO** |
| **MODIS MOD13Q1 NDVI** | MODIS | 250 m | 2000–Present | **100% COMPATIBLE** | NASA LP DAAC API | **ZERO BARRIER** (Public open data) | **SECONDARY OPERATIONAL GO** |

---

## 4. Source References & Citations

1. NRSC Natural Resources Census (NRC) Project Team (2023). *Annual Land Use and Land Cover Atlas of India (2005-06 to 2022-23)*. National Remote Sensing Centre, Indian Space Research Organisation, Hyderabad, India. URL: `https://www.nrsc.gov.in/nrscnew/resources_atlas_LULC.php`
2. NRSC Soil and Land Degradation Group (2020). *Land Degradation Mapping of India at 1:50,000 Scale (Cycles 1 & 2)*. National Remote Sensing Centre, Department of Space, Government of India. URL: `https://www.nrsc.gov.in/nrscnew/Apps_Soils_Apps.php?lang_code=en`
3. ISRO Bhuvan Team (2024). *Bhuvan — Gateway to Indian Earth Observation: Open EO Data Archive (NOEDA)*. National Remote Sensing Centre. URL: `https://bhuvan-app1.nrsc.gov.in/2dresources/bhuvanstore.php`
4. European Space Agency (2024). *Copernicus Sentinel-2 Level-2A User Handbook*. ESA Directorate of Earth Observation Programmes. URL: `https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi`
5. Didan, K. (2021). *MOD13Q1 MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061*. NASA EOSDIS Land Processes Distributed Active Archive Center. DOI: `10.5067/MODIS/MOD13Q1.061`
