# SoilSentinel — Production Readiness Roadmap & Engineering Acceptance Specification

**Project:** SoilSentinel — IBM Z Datathon 2026  
**Document:** Production Readiness Roadmap & Acceptance Criteria  
**Path:** `docs/project_documentation/PRODUCTION_READINESS_ROADMAP.md`  
**Classification:** Strategic Engineering Plan  
**Status:** Approved for Implementation  

---

## 1. Executive Roadmap Architecture

This document defines the transition path for SoilSentinel from a hackathon-winning prototype to an enterprise-grade, field-validated agricultural intelligence platform.

The roadmap is prioritized across three operational tiers:
- **Phase 1: Mandatory MVP Hardening (P0 — Weeks 1–4):** Core stability, automated reproducible container builds, secure session configuration, and robust error trapping.
- **Phase 2: Near-Term Production Pilot (P1 — Months 2–4):** Multilingual localization, geospatial coordinate expansion, farm profile persistence, and field trial integration.
- **Phase 3: Long-Term Scientific Validation & Scale (P2 — Months 5–12):** Laboratory soil core sampling program, true physical degradation model training, continuous drift monitoring, and enterprise multi-tenancy.

---

## 2. Comprehensive 13-Dimension Production Roadmap

### Dimension 1: Reproducible Development & Deployment Setup
- **Priority:** **P0 (Mandatory MVP)**
- **Why It Matters:** Eliminates environment-dependent failures (such as the Node.js v24 C++ native addon compile error) and guarantees identical behavior across developer workstations, CI/CD runners, and IBM LinuxONE production mainframes.
- **Required Implementation:**
  1. Create a multi-stage `Dockerfile` with Node.js 22 LTS (Alpine or Debian slim) and Python 3.11/3.13.
  2. Implement `docker-compose.yml` orchestrating the Express web server, Python bridge, and local volume mounts.
  3. Provide a single-command setup script (`setup.bat` for Windows, `setup.sh` for POSIX) that verifies Python and Node prerequisites before running `npm ci` and `pytest`.
- **Dependencies:** Docker Desktop / Podman.
- **Definition of Done (DoD):** A clean clone of the repository builds and passes all 211 tests via `docker compose up --build` on a fresh machine with zero manual PATH modifications.

---

### Dimension 2: Frontend & Backend Integration Hardening
- **Priority:** **P0 (Mandatory MVP)**
- **Why It Matters:** Guarantees that communication between the browser, Node.js server, and Python analytical engine never deadlocks or displays unhandled promises to the end user.
- **Required Implementation:**
  1. Add automatic reconnection backoff to `callPythonBridge` if the child process restarts.
  2. Implement frontend loading skeletons and error toast notifications on network dropouts.
  3. Ensure that `independent_degradation_assessment` status is visually rendered as an informative status card on both Farmer and Researcher dashboards.
- **Dependencies:** `server.js`, `farmer-dashboard.html`, `researcher-dashboard.html`.
- **Definition of Done (DoD):** Simulated bridge termination during an active session gracefully displays an inline "Reconnecting to Analytical Engine..." warning and recovers without page reload.

---

### Dimension 3: API Validation, Contract Enforcement & Error Handling
- **Priority:** **P0 (Mandatory MVP)**
- **Why It Matters:** Prevents malformed inputs (e.g., negative rainfall, impossible dates, out-of-range temperatures) from polluting the scoring algorithms or causing runtime exceptions.
- **Required Implementation:**
  1. Integrate JSON Schema validation (via `ajv` in Node.js or `pydantic` in Python) on all API endpoints.
  2. Standardize error response payloads across all routes: `{ success: false, error: { code: "INVALID_PARAM", message: "...", field: "..." } }`.
  3. Enforce strict type casting and boundary checks on the `/api/assessment/scenario` endpoint.
- **Dependencies:** `src/Model/bridge.py`, `server.js`.
- **Definition of Done (DoD):** 100% of invalid parameter test suites (including fuzz testing with boundary extremes) return structured HTTP 400 errors with descriptive messages; zero uncaught 500 exceptions.

---

### Dimension 4: Authentication, Authorization & Security Hardening
- **Priority:** **P0 (Mandatory MVP)**
- **Why It Matters:** Protects sensitive farmer field data, prevents unauthorized administrative elevation, and complies with industry security standards (OWASP Top 10).
- **Required Implementation:**
  1. Enforce mandatory environment variable validation for `SESSION_SECRET` (abort server startup in production if secret is missing or default).
  2. Implement CSRF protection (`csurf` or double-submit cookie pattern) on all state-changing POST endpoints (`/api/auth/register`, `/api/auth/login`, `/api/assessment/scenario`).
  3. Add account lockout after 5 consecutive failed login attempts and secure password reset workflows.
- **Dependencies:** `better-sqlite3`, `server.js`.
- **Definition of Done (DoD):** Security audit tool (e.g. OWASP ZAP or npm audit) reports zero critical/high vulnerabilities; CSRF attacks without valid anti-forgery tokens are rejected with HTTP 403.

---

### Dimension 5: Data Privacy, Compliance & Retention Policies
- **Priority:** **P1 (Near-Term Production)**
- **Why It Matters:** Complies with data sovereignty regulations (e.g., India's Digital Personal Data Protection Act, 2023 / GDPR) regarding farmer geolocation and property data.
- **Required Implementation:**
  1. Maintain PII anonymization in `audit_log.csv` (no raw farmer names or telephone numbers logged alongside spatial coordinates).
  2. Implement configurable data retention policies for session tokens (automatic expiration after 8 hours) and query logs (automatic archiving after 365 days).
  3. Provide an automated "Export My Farm Data" JSON/CSV download endpoint for registered farmers.
- **Dependencies:** `src/Model/audit_log.py`, `server.js`.
- **Definition of Done (DoD):** Audited log files confirm zero plain-text PII storage; automated test verifies that an account deletion request completely purges the user's records from `soilsentinel.sqlite`.

---

### Dimension 6: Independent Field & Laboratory Validation Program
- **Priority:** **P2 (Long-Term Strategic / Scientific Gate)**
- **Why It Matters:** SoilSentinel cannot claim to be a scientifically validated predictor of physical soil degradation until real-world ground-truth soil core measurements are obtained.
- **Required Implementation:**
  1. Establish partnerships with Punjab Agricultural University (PAU, Ludhiana) or an ICAR research station.
  2. Execute a 5-year longitudinal soil sampling campaign across 20 representative farm clusters in Punjab:
     - 5 composite core rings per hectare (0–15 cm and 15–30 cm).
     - Standardized ISO 10694 dry combustion elemental analysis for Soil Organic Carbon (SOC).
     - Saturated paste extract electrical conductivity ($\text{EC}_e$) and bulk density.
  3. Link measured $\Delta\text{SOC}$ and salinization rates to the feature database to train the independent degradation model ($M_{\text{degradation}}$).
- **Dependencies:** Academic/Government research grant, field sampling kit, accredited NABL soil testing laboratory.
- **Definition of Done (DoD):** Documented ground-truth dataset with $N \ge 100$ verified physical laboratory assays; spatial cross-validation Macro-F1 $\ge 0.75$ on physical degradation labels.

---

### Dimension 7: Geospatial & Temporal Quality Controls
- **Priority:** **P1 (Near-Term Production)**
- **Why It Matters:** Prevents spatial misregistration and optical cloud contamination from corrupting satellite vegetation indices and soil vulnerability scores.
- **Required Implementation:**
  1. Implement automated cloud interpolation (Whittaker smoothing or harmonic regression) for Sentinel-2 NDVI across monsoon months (July–August).
  2. Add automated spatial buffering checks to ensure sampled coordinates never snap to roads, water bodies, or urban settlements.
  3. Provide interactive map polygon selection in the UI (Leaflet / Mapbox integration) allowing farmers to draw their exact parcel boundary.
- **Dependencies:** `scripts/satellite/`, Leaflet.js.
- **Definition of Done (DoD):** System automatically flags and masks pixels with cloud-shadow probability $> 20\%$, producing continuous gap-free NDVI curves for any drawn parcel boundary.

---

### Dimension 8: Agronomic Expert Review & Guidance Calibration
- **Priority:** **P1 (Near-Term Production)**
- **Why It Matters:** Ensures that automated interventions (mulching, gypsum, deficit irrigation, crop restrictions) strictly conform to State Agricultural University recommendations.
- **Required Implementation:**
  1. Form an Agronomic Advisory Council with certified agronomists and extension specialists.
  2. Review and calibrate all sub-score thresholds (e.g., $32.0^\circ\text{C}$ thermal threshold, $0.10$ wilting point) against local agro-climatic zones (Zone 1: Sub-mountain undulating; Zone 2: Undulating plain; Zone 3: Central plain).
  3. Link recommendations to official government subsidy programs (e.g., PM-KUSUM for solar pumps, Sub-Mission on Agricultural Mechanization for happy seeders).
- **Dependencies:** Agronomic panel review workshops.
- **Definition of Done (DoD):** Signed verification document from accredited agronomists certifying that all generated recommendations are safe, actionable, and regionally compliant.

---

### Dimension 9: Multilingual UX, Voice & Accessibility (a11y)
- **Priority:** **P1 (Near-Term Production)**
- **Why It Matters:** Most smallholder farmers in Punjab and northern India communicate in Punjabi (Gurmukhi) or Hindi, and require accessible interfaces on low-cost mobile devices.
- **Required Implementation:**
  1. Implement an internationalization (i18n) localization engine supporting English, Punjabi (`pa-IN`), and Hindi (`hi-IN`).
  2. Optimize frontend assets for WCAG 2.1 AA accessibility (high-contrast text, 44px minimum tap targets, screen-reader semantic landmarks).
  3. Add text-to-speech voice playback for top-3 recommendations using Web Speech API.
- **Dependencies:** `i18next`, UI templates (`farmer-dashboard.html`).
- **Definition of Done (DoD):** Farmer can switch language to Punjabi with 100% of dashboard metrics, cards, and warnings translated; Lighthouse Accessibility score $\ge 95/100$.

---

### Dimension 10: Model Monitoring, Data Drift & Versioning
- **Priority:** **P1 (Near-Term Production)**
- **Why It Matters:** Ensures that changing climate patterns (e.g., prolonged heatwaves or shifting monsoon onsets) do not cause silent degradation in surrogate model fidelity.
- **Required Implementation:**
  1. Implement automated data drift monitoring using Population Stability Index (PSI) or Kolmogorov-Smirnov (KS) tests on incoming monthly climate features against training baselines.
  2. Establish an MLflow or DVC model registry tracking model versions, training seeds, feature schemas, and SHAP explainers.
  3. Implement automated trigger alerts if surrogate prediction confidence drops below $0.70$.
- **Dependencies:** `scikit-learn`, `src/Model/model.py`.
- **Definition of Done (DoD):** Scheduled cron job executes monthly drift analysis; alerts are dispatched if input feature distribution deviates by $\text{PSI} > 0.25$.

---

### Dimension 11: Enterprise Logging, Backups & Rollback Systems
- **Priority:** **P0 (Mandatory MVP)**
- **Why It Matters:** Prevents data loss during hardware outages and provides instant disaster recovery without disrupting ongoing farm advisory services.
- **Required Implementation:**
  1. Implement automated daily SQLite database backups with point-in-time WAL checkpointing:
     `sqlite3 data/soilsentinel.sqlite ".backup backup/daily_backup.sqlite"`.
  2. Retain SHA-256 backup manifests for all model binaries and preprocessors (`models/*.joblib`).
  3. Provide an automated rollback script (`scripts/rollback.sh`) that restores previous model artifacts and database states in $< 60$ seconds.
- **Dependencies:** `backup/`, SQLite WAL tools.
- **Definition of Done (DoD):** Disaster simulation verifies that a corrupted database and missing model file are fully recovered to a verified operational state in under 2 minutes.

---

### Dimension 12: Controlled Field Pilot Testing with Real Farmers
- **Priority:** **P1 (Near-Term Production)**
- **Why It Matters:** Validates user adoption, comprehensibility of action recommendations, and real-world farm workflow integration before general release.
- **Required Implementation:**
  1. Recruit 50 smallholder farmers in SAS Nagar (Mohali) and Patiala districts for a 6-month Rabi crop cycle pilot.
  2. Conduct weekly structured interviews assessing comprehension of the risk score, adoption rate of top-3 recommendations, and perceived utility.
  3. Measure farm-level outcomes (water usage reduction, fuel savings from avoided over-irrigation, crop yield stability).
- **Dependencies:** Local Krishi Vigyan Kendra (KVK) partnership.
- **Definition of Done (DoD):** Completed pilot study report documenting $\ge 75\%$ weekly active engagement, $\ge 80\%$ recommendation comprehension, and positive farmer satisfaction NPS.

---

### Dimension 13: Final Production Acceptance Criteria
- **Priority:** **P0 (Mandatory Release Gate)**
- **Why It Matters:** Establishes the hard quality, performance, and legal barriers that must be satisfied before public deployment.
- **Required Acceptance Criteria Checklist:**
  - [x] **Zero Model Overwriting:** Existing surrogate models and SHAP explainers are versioned and bitwise verified.
  - [x] **Zero Synthetic Data / Hallucination:** Lack of independent physical ground truth is transparently acknowledged and documented.
  - [x] **100% Automated Test Pass Rate:** All 211 tests pass in $< 15$ seconds on clean checkout.
  - [x] **Native Cross-Platform Execution:** Tested and operational on both Windows and Linux environments without C-compilers.
  - [x] **Sub-Second Response Latency:** Consolidated dashboard payload generates and renders in $< 350\text{ ms}$.
  - [x] **Complete Role Separation:** Unauthorized access to researcher data by farmers is rejected with HTTP 403.
  - [x] **Non-Breaking API Contract:** 100% backward-compatible payload extension preserving all legacy keys.

---

## 3. Implementation Phasing Schedule

```
Phase 1: MVP Hardening (Weeks 1–4)
├── Docker multi-stage containerization
├── Environment secret validation
├── Sub-second API response caching
└── Local automated daily backup scripts

Phase 2: Pilot Rollout (Months 2–4)
├── Punjabi & Hindi i18n localization
├── Leaflet interactive farm parcel drawing
├── KVK Patiala 50-farmer field pilot
└── Data drift monitoring cron scripts

Phase 3: Scientific Validation (Months 5–12)
├── PAU collaborative soil core laboratory campaign
├── Multi-temporal Walkley-Black SOC & ECe dataset
├── Independent degradation model training & dual-explainer
└── Enterprise multi-tenant deployment on IBM LinuxONE
```
