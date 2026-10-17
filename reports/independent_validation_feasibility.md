# SoilSentinel — Independent Soil Degradation Validation Feasibility Assessment

**Document Status:** Official Forensic Research Report  
**Date:** October 2026  
**Investigators:** Senior Machine Learning Engineer, Soil-Data Scientist & Backend Architect  
**Study Region:** Punjab Agrarian Parcel (`30.7300° N, 76.7700° E` nominal; `30.7392° N, 76.7764° E` sampled pixel)  
**Target Temporal Horizon:** Monthly 2020–2024 (60 continuous monthly timesteps)  

---

## 1. Executive Summary & Core Verdict

The objective of this investigation is to determine whether credible, independent ground-truth data exists to train, validate, or evaluate a machine learning model predicting actual physical soil degradation at the target agricultural parcel in Punjab, India.

### Forensic Conclusion:
> [!IMPORTANT]
> **No public, multi-temporal, laboratory-measured in-situ soil degradation ground-truth dataset exists for the study coordinates across the 2020–2024 evaluation window.**
> 
> In strict compliance with scientific integrity standards and engineering safety rules, **no new machine learning model has been trained or retrained.** Training a model on synthetic degradation labels, or conflating rule-based screening risk scores or satellite vegetation indices with true physical soil degradation, would constitute scientific malpractice.
> 
> **Status:** The backend engineering integration is complete and backward-compatible. Independent physical model training is **BLOCKED PENDING FIELD GROUND-TRUTH DATA ACQUISITION**.

---

## 2. Forensic Investigation of Candidate Datasets

Every candidate data source across national (Indian) and international soil and earth-observation archives was evaluated against strict scientific criteria:
1. Official source and custodial authority
2. Licensing and legal access
3. Geographic coverage and spatial resolution
4. Sampling dates and temporal cadence
5. Sample count and spatial representation
6. Laboratory measurement methods and physical standards
7. Target definitions and physical units
8. Match feasibility with SoilSentinel's 2020–2024 monthly climate, soil, and satellite feature space

---

### Candidate 1: ICAR-NBSS&LUP Bhoomi Geoportal & National Soil Series

| Evaluation Parameter | Verified Specification & Assessment |
| :--- | :--- |
| **Official Source** | ICAR – National Bureau of Soil Survey and Land Use Planning (NBSS&LUP), Nagpur (`https://nbsslup.icar.gov.in/`, `https://bhoomi.icar.gov.in/`) |
| **Licence & Access** | Open Government Data (OGD) India / ICAR research access. Map viewing is public; raw geo-coded soil profile databases require formal institutional data-sharing agreements. |
| **Geographic Coverage** | All-India national coverage. National Soil Series mapping at 1:250,000 scale; select districts mapped at 1:50,000 scale. |
| **Sampling Dates** | Legacy survey campaigns spanning 1975 to 2010; periodic project resurveys up to 2018. |
| **Sample Count** | ~14,000 benchmark soil profile descriptions across India, but only sparse historical profiles in SAS Nagar / Patiala / Chandigarh belt. |
| **Measurement Methods** | Wet-chemical analysis: Walkley-Black chromic acid wet oxidation for Soil Organic Carbon (SOC); Pipette method for particle size distribution; 1:2.5 soil:water suspension for pH; core samplers for bulk density. |
| **Target Definition & Units** | Morphological profile descriptions, taxonomical classification (e.g., Typic Ustochrepts, Typic Haplustalfs), static horizon SOC (%), and texture fractions (%). |
| **Spatial / Temporal Match** | **INCOMPATIBLE TEMPORALLY.** Represents static pedological taxonomy and historical baseline profiles. No continuous monthly or annual repeat sampling exists for 2020–2024 at `30.7300° N, 76.7700° E`. |
| **Decision** | **Unusable as dynamic ground truth.** Serves as valuable qualitative pedological reference for soil series classification, but cannot provide training labels for monthly degradation. |

---

### Candidate 2: ICAR-CSSRI Salt-Affected Soils & Salinity Database

| Evaluation Parameter | Verified Specification & Assessment |
| :--- | :--- |
| **Official Source** | ICAR – Central Soil Salinity Research Institute (CSSRI), Karnal, Haryana (`https://cssri.icar.gov.in/`) |
| **Licence & Access** | Research publications, thematic atlases, and departmental reports under Ministry of Agriculture & Farmers Welfare. |
| **Geographic Coverage** | Salt-affected tracts of the Indo-Gangetic Plains (Punjab, Haryana, Uttar Pradesh). |
| **Sampling Dates** | Decadal reconnaissance surveys and localized reclamation project trials (e.g., Gypsum technology trials). |
| **Sample Count** | Clustered research farm plots and district-level inventory polygons. |
| **Measurement Methods** | Electrical conductivity of saturated soil paste extract ($\text{EC}_e$) at 25°C in $\text{dS/m}$; Exchangeable Sodium Percentage (ESP); Sodium Adsorption Ratio (SAR); pH of saturated paste ($\text{pH}_s$). |
| **Target Definition & Units** | Saline ($\text{EC}_e \ge 4.0\text{ dS/m}$, $\text{ESP} < 15$, $\text{pH} < 8.5$), Sodic ($\text{EC}_e < 4.0\text{ dS/m}$, $\text{ESP} \ge 15$, $\text{pH} > 8.5$), Saline-Sodic ($\text{EC}_e \ge 4.0\text{ dS/m}$, $\text{ESP} \ge 15$). |
| **Spatial / Temporal Match** | **INCOMPATIBLE SPATIALLY & TEMPORALLY.** CSSRI monitoring stations are concentrated in Karnal, Bathinda, and south-western Punjab waterlogged tracts. No micro-plot time series exists for the northern Punjab plain near Chandigarh during 2020–2024. |
| **Decision** | **Unusable as training ground truth.** Establishes critical physical threshold criteria ($\text{EC}_e \ge 4.0\text{ dS/m}$), but lacks local temporal observations. |

---

### Candidate 3: NRSC/ISRO Bhuvan Land Degradation Mapping (1:50,000 Scale)

| Evaluation Parameter | Verified Specification & Assessment |
| :--- | :--- |
| **Official Source** | National Remote Sensing Centre (NRSC), ISRO, Department of Space (`https://bhuvan-app1.nrsc.gov.in/`, `https://www.nrsc.gov.in/`) |
| **Licence & Access** | Government of India Remote Sensing Data Policy (RSDP). Web Map Services (WMS) open for visualization; underlying vector shapefiles and raster grids restricted behind authenticated portal (`bhuvanusername` + OTP). |
| **Geographic Coverage** | National coverage (All-India wall-to-wall). |
| **Sampling Dates** | Cycle 1: 2005–06; Cycle 2: 2015–16. Cycle 3 (2020–21) is in progress/under validation and unpublished as open public GIS layers. |
| **Sample Count** | National spatial polygon inventory (covering 36 degradation classes across 8 processes). |
| **Measurement Methods** | Semi-automated digital interpretation of Resourcesat-1/2 LISS-III imagery (23.5 m resolution) verified by selective ground-truth sample checks across India. |
| **Target Definition & Units** | Classified thematic polygons: Water Erosion (Sheet, Rill, Gully), Wind Erosion, Salinization / Alkalization, Waterlogging, Acidification, Mass Movement. |
| **Spatial / Temporal Match** | **COMPLETELY INCOMPATIBLE WITH MONTHLY HORIZON.** Decadal snapshots (2005 and 2015) cannot be interpolated or matched to dynamic monthly timesteps between 2020-01 and 2024-12. |
| **Decision** | **Unusable for dynamic model training.** Proves that macro-scale land degradation mapping is conducted on decadal scales, further invalidating any claim that monthly meteorological fluctuations represent permanent land degradation. |

---

### Candidate 4: ISRIC World Soil Information Service (WoSIS) & SoilGrids v2.0

| Evaluation Parameter | Verified Specification & Assessment |
| :--- | :--- |
| **Official Source** | International Soil Reference and Information Centre (ISRIC) – World Soil Information, Wageningen (`https://www.isric.org/explore/wosis`, `https://soilgrids.org`) |
| **Licence & Access** | Open Database License (ODbL) / Creative Commons Attribution 4.0 International (CC BY 4.0). Full open access via REST API and WCS/VRT streaming. |
| **Geographic Coverage** | Global. WoSIS profile points; SoilGrids 250 m spatial predictions. |
| **Sampling Dates** | WoSIS: Profile records collected between 1960 and 2015. SoilGrids v2.0: Published in 2020 as a static global baseline representation. |
| **Sample Count** | WoSIS: ~196,000 standardized profiles worldwide. Sparse point density in Punjab, India. SoilGrids: Continuous global raster. |
| **Measurement Methods** | Standardized laboratory profiles; SoilGrids uses quantile Random Forest regressions trained on 240,000 profiles against global remote sensing and climate covariates. |
| **Target Definition & Units** | Bulk density ($\text{cg/cm}^3$), Clay/Sand/Silt ($\text{g/kg}$), Soil Organic Carbon ($\text{dg/kg}$), pH in water $\times 10$, Nitrogen ($\text{cg/kg}$). |
| **Spatial / Temporal Match** | **CIRCULARITY / TARGET LEAKAGE RISK.** SoilSentinel already ingests SoilGrids v2.0 as its baseline static soil vulnerability features (`soc_topsoil_g_kg`, `ph_topsoil`, `clay_fraction_topsoil`, etc.). |
| **Decision** | **STRICTLY PROHIBITED AS GROUND TRUTH.** Treating SoilGrids predictions as ground-truth degradation labels would violate machine learning fundamentals: it would introduce severe target leakage, circular self-training, and confuse a static model prediction with measured empirical reality. |

---

### Candidate 5: Sentinel-2 Multispectral Instrument (MSI) Surface Reflectance & NDVI Pipeline

| Evaluation Parameter | Verified Specification & Assessment |
| :--- | :--- |
| **Official Source** | European Space Agency (ESA) Copernicus Programme / AWS Earth (`sentinel-cogs`) |
| **Licence & Access** | Open Access (Creative Commons CC BY-SA 3.0 IGO). Fully automated, programmatic ingestion. |
| **Geographic Coverage** | Tile `T43SFT` covering Punjab, India at 10-metre spatial resolution. |
| **Sampling Dates** | Continuous observations aligned to SoilSentinel's 60-month horizon (2020-01 to 2024-12). |
| **Sample Count** | 60 aligned monthly composites, 100% complete with valid cloud-masked surface reflectance arrays. |
| **Measurement Methods** | Calibrated Bottom-of-Atmosphere (BOA) surface reflectance: Normalized Difference Vegetation Index ($NDVI = \frac{B8 - B4}{B8 + B4}$). |
| **Target Definition & Units** | Unitless canopy spectral vigor ratio $[-1.0, 1.0]$. |
| **Spatial / Temporal Match** | Perfectly matched to SoilSentinel's coordinates and monthly timesteps. |
| **Decision** | **EXCELLENT COVARIATE, BUT CANNOT BE USED AS A DEGRADATION TARGET.** NDVI measures instantaneous above-ground photosynthetic canopy vigor. In an intensive agricultural parcel (such as Punjab's rice-wheat rotation), low NDVI occurs during normal harvest and fallow periods (May–June and October–November). Conflating temporary low NDVI with permanent soil degradation is a major remote sensing error. |

---

## 3. Comparative Dataset Matrix

| Candidate Dataset | Source | Sampling Cadence | Ground-Truth In-Situ Labs? | Spatial Fit | Temporal Fit (2020–2024) | Scientific Verdict |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **ICAR-NBSS&LUP Bhoomi** | ICAR, India | Historical survey | Yes (Chemical) | Regional | Static legacy (< 2018) | **Rejected** (No 2020–24 series) |
| **ICAR-CSSRI Salinity** | CSSRI, India | Decadal trials | Yes ($\text{EC}_e$, ESP) | Hotspots | Static project | **Rejected** (Wrong region/cadence) |
| **NRSC Land Degradation** | ISRO, India | Decadal (2005, 2015) | Yes (Sample checks) | 23.5 m | Decadal historical | **Rejected** (No 2020–24 data) |
| **ISRIC WoSIS Profiles** | ISRIC, Global | Point legacy | Yes (Standardized) | Sparse | Legacy (< 2015) | **Rejected** (Zero local parcel points) |
| **SoilGrids v2.0** | ISRIC, Global | Static snapshot (2020) | No (ML model output) | 250 m | Static snapshot | **Rejected** (Severe Target Leakage) |
| **Sentinel-2 NDVI** | ESA, Global | 5-day / Monthly | No (Canopy optical) | 10 m | 60 monthly steps | **Rejected as Target** (Valid Covariate) |
| **Local Farm Soil Cores** | Field collection | None documented | N/A | Parcel | None performed | **MISSING GROUND TRUTH** |

---

## 4. Why Synthetic or Proxy Labels Are Strictly Rejected

It is a common pitfall in academic datathons to "synthesize" labels when true ground truth is absent. The following practices are explicitly rejected in SoilSentinel:

1. **Rule-Engine Label Leakage:** Using SoilSentinel's rule-based score (`risk_category` or `score`) as "ground-truth degradation" to train an ML model produces only a *surrogate model* (an emulator of code), NOT a validated predictor of the physical earth.
2. **Thresholded NDVI Binarization:** Classifying months with $NDVI < 0.25$ as "degraded" confuses the agronomic harvest cycle with soil erosion or organic carbon loss.
3. **SoilGrids Interpolated Noise:** Adding random noise to SoilGrids SOC values to generate synthetic degradation labels creates fictitious data with zero empirical validity.

---

## 5. Specification of Missing Data & Field Collection Protocol

To achieve genuine scientific validation in future iterations, the following field data collection protocol must be established:

### A. Georeferenced Field Soil Core Sampling Protocol
- **Sampling Design:** Stratified random sampling across 5 points within the 1-hectare agricultural parcel: 4 quadrant vertices + 1 parcel centroid.
- **Depth Stratification:**
  - Surface layer: $0\text{--}15\text{ cm}$ (topsoil plow layer / active root zone)
  - Subsurface layer: $15\text{--}30\text{ cm}$ (subsoil boundary)
- **Core Collection:** Undisturbed soil core rings of known internal volume ($100\text{ cm}^3$, $5\text{ cm}$ diameter) to determine bulk density alongside chemical properties.
- **Temporal Frequency:** Annual sampling conducted consistently at the end of the post-Rabi fallow (May), prior to monsoon kharif puddle preparation, for a minimum of 3 to 5 consecutive years.

### B. Standard Laboratory Analytical Procedures
1. **Soil Organic Carbon (SOC):**
   - High-temperature dry combustion elemental analysis (ISO 10694) via automated CN elemental analyzer after inorganic carbonate removal via acid pre-treatment.
   - Reference fallback: Walkley-Black wet oxidation with standard recovery correction factor ($f = 1.32$).
   - Units: $\text{g C / kg soil}$ (or $\%$), converted to stock ($\text{t C / ha}$) using measured bulk density.
2. **Soil Salinization & Sodicity:**
   - Saturated soil paste extract electrical conductivity ($\text{EC}_e$) at 25°C in $\text{dS/m}$ (USDA Handbook 60).
   - Exchangeable Sodium Percentage ($\text{ESP} = \frac{\text{Na}^+}{\text{CEC}} \times 100$) and Soil pH (1:2.5 water suspension).
3. **Soil Structural Compaction:**
   - Dry bulk density ($\text{BD} = \frac{M_{dry}}{V_{core}}$ in $\text{g/cm}^3$).
   - Saturated hydraulic conductivity ($K_{sat}$, $\text{mm/hr}$) using constant-head permeameter.

### C. Estimated Resource Requirements
- Sampling kit & core rings: ₹15,000 (~$180 USD)
- Certified NABL-accredited soil laboratory analytical testing (10 samples/year $\times$ 5 years $\times$ ₹1,200/sample): ₹60,000 (~$720 USD)
- Total validation cost over 5-year longitudinal program: ~₹75,000 (~$900 USD).

---

## 6. Engineering & Scientific Conclusion

1. **Independent Ground Truth Status:** Unavailable.
2. **Model Training Decision:** Halted before execution.
3. **Surrogate Model Role:** Preserved strictly as an empirical proxy of the rule-based screening index (`v1.0.0-rf-proxy`).
4. **Backend Status:** Updated to return explicit `PENDING_INDEPENDENT_GROUND_TRUTH` status in the new `independent_degradation_assessment` payload block.
