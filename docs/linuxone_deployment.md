# SoilSentinel — IBM LinuxONE (s390x) Deployment Guide

This guide details the deployment, execution, and verification of the SoilSentinel baseline prediction and audit-logging system on **IBM LinuxONE Community Cloud** (Linux on IBM Z, `s390x` architecture).

---

## 1. Architecture Overview & Core Dependencies

SoilSentinel's scoring, prediction, and audit-logging modules are written in **pure, portable Python 3.10+**. 
To ensure seamless execution on LinuxONE without requiring C/C++ compilation of geospatial libraries (such as GDAL / `rasterio`), dependencies are segregated:

* **Core Runtime (`requirements-core.txt`):**
  * `pandas>=2.0.0`
  * `numpy>=1.24.0`
  * *Standard Library:* `csv`, `datetime`, `argparse`, `pathlib`, `logging`, `typing`, `dataclasses`, `unittest`.
* **Optional Feature Generation (`requirements.txt`):**
  * `PyYAML>=6.0.0` (required only if regenerating `feature_table.csv` from `data/processed/` using `config/settings.yaml`).
* **Raw Ingestion Only:**
  * `rasterio>=1.3.0` (used solely by `src/data_collection/soilgrids.py` to stream remote SoilGrids VRT files; **not required for inference, prediction, scoring, or testing**).

---

## 2. Files Required for Inference on LinuxONE

When transferring the repository to a LinuxONE instance, only the following core files are required for prediction and testing:

```
SoilSentinel/
├── data/
│   └── feature_table.csv          # Pre-processed 60-month feature table (24,705 bytes)
├── src/
│   └── Model/
│       ├── risk_scoring.py         # Deterministic baseline scoring engine
│       ├── predict.py              # Prediction interface (single, batch, CLI)
│       └── audit_log.py            # Lightweight, append-only CSV audit logger
├── tests/
│   ├── test_risk_scoring.py        # 19 tests for scoring logic & boundaries
│   ├── test_predict.py             # 12 tests for prediction interface & CLI
│   └── test_audit_log.py           # 7 tests for audit logging & append safety
└── requirements-core.txt           # Minimal runtime dependencies (numpy, pandas)
```

> [!NOTE]
> **Minimal Inference Test Bundle vs. Complete Repository Test Suite:**  
> The 3 test files above comprise the 38-test minimal inference verification bundle tailored for lightweight deployment on LinuxONE without requiring geospatial or data-collection dependencies. In the full development repository, the complete test suite comprises **112 unit tests** across all pipeline stages (see Section 3.3).

> **Directory Cleanup Status:** The legacy duplicate directory `src/Data Collectiion` has been removed. All data collection modules and pipeline orchestrators are canonicalized under `src/data_collection/`.

---

## 3. Step-by-Step LinuxONE Deployment Instructions

### Step 3.1: Verify Target Architecture
Before running the pipeline, confirm that you are executing on genuine `s390x` hardware:

```bash
python3 -c "import platform, sys; print(f'Arch: {platform.machine()} | OS: {platform.system()} | Byteorder: {sys.byteorder}')"
```

* **On IBM LinuxONE (`s390x`):**
  * `Arch: s390x`
  * `OS: Linux`
  * `Byteorder: big`
* **On Local Development Machine (Windows / x86_64):**
  * `Arch: AMD64` or `x86_64`
  * `OS: Windows` or `Darwin`
  * `Byteorder: little`

> [!IMPORTANT]
> A run on Windows or an x86 Linux machine cannot confirm `s390x` compatibility. Confirmation requires running directly on an active `s390x` host.

---

### Step 3.2: Provision Python Virtual Environment
On your LinuxONE shell (e.g. RHEL, SLES, or Ubuntu on IBM Z):

```bash
# 1. Create a clean virtual environment
python3 -m venv .venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Upgrade pip and install minimal core requirements
pip install --upgrade pip
pip install -r requirements-core.txt
```

---

### Step 3.3: Run the Test Suite

#### Minimal Inference Test Suite (IBM LinuxONE Standalone Deployment)
When running inside the minimal inference deployment package on LinuxONE, execute the 38 unit tests covering input validation, moisture buffering, strict/permissive missing-history handling, determinism, and audit logging:

```bash
python3 -m unittest discover tests
```

**Expected LinuxONE Result (Minimal Package):**
```
Ran 38 tests in ~0.3s
OK
```

#### Complete Repository Test Suite (Local Development & Verification)
The full repository test suite contains **112 passing unit tests** spanning all Member 1 and Member 2 modules across 7 test files (`test_risk_scoring.py` [19], `test_predict.py` [12], `test_audit_log.py` [7], `test_features.py` [23], `test_preprocessing.py` [19], `test_pipeline_orchestration.py` [4], and `test_outlook.py` [28]):

```bash
python -m unittest discover tests
```

**Verified Local Development Result (x86_64 / Windows):**
```
Ran 112 tests in ~2.1s
OK
```

> [!IMPORTANT]
> **Test Scope & Environment Clarity:**  
> The 112 passing tests represent the complete repository suite executed and verified in the local development environment (`x86_64` / Windows). The 38 tests in the minimal package represent the subset verified specifically for standalone inference on LinuxONE (`s390x`). Full 112-test execution on LinuxONE requires deploying the complete repository and provisioning all pipeline dependencies.

---

### Step 3.4: Execute Batch Prediction with Audit Logging

#### Permissive Mode (Default):
Uses single-month fallback for initial sequence boundary records (`2020-01`, `2020-02`) where 3-month rolling rainfall is unobserved:

```bash
python3 src/Model/predict.py \
  --input data/feature_table.csv \
  --output outputs/predictions.csv \
  --audit-log logs/audit_log.csv
```

#### Strict Mode:
Aborts missing-history records with `INSUFFICIENT_HISTORY` and null scores:

```bash
python3 src/Model/predict.py \
  --input data/feature_table.csv \
  --output outputs/predictions_strict.csv \
  --strict \
  --audit-log logs/audit_log.csv
```

---

## 4. Verification and Audit Inspection

After execution, verify the generated artifacts:

```bash
# 1. Verify prediction output (should be 61 lines: 1 header + 60 monthly records)
wc -l outputs/predictions.csv

# 2. Inspect audit trail entries
cat logs/audit_log.csv | head -n 5
```

The resulting `outputs/predictions.csv` contains 30 columns including spatial-temporal identifiers, the composite score, risk category, dynamic environmental stress, static baseline vulnerability, and individual indicator sub-scores. The audit trail records timestamped ISO 8601 entries without storing raw features or credentials.
