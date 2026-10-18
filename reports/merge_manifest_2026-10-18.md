# SoilSentinel merge manifest — 2026-10-18

Source project: `Datathon (8).zip`
Incoming changes: `SoilSentinel_Website_Improvements(1).zip`

## Applied files
- `README.md` — updated with friend improvement.
- `dashboard-visuals.js` — added from friend improvement.
- `docs/website_visuals_implementation.md` — added from friend improvement.
- `farmer-dashboard.html` — updated with friend improvement.
- `farmer.html` — updated with friend improvement.
- `reports/api_contract.md` — updated with friend improvement.
- `researcher-dashboard.html` — updated with friend improvement.
- `server.js` — updated with friend improvement.
- `src/Model/bridge.py` — updated with friend improvement.
- `styles.css` — updated with friend improvement.
- `tests/test_dashboard_observations.py` — added from friend improvement.

## Preservation decisions
- Existing `logs/audit_log.csv` was preserved from Datathon (8); the incoming copy was not used.
- Existing ML models, preprocessors, SHAP artifacts, datasets, Sentinel-2 rasters, and team/backend modules were not intentionally removed.
- Existing files at paths shared by both ZIPs were updated only where the incoming website-improvement file differed; no second copy was created at the same path.
- Distinct paths containing byte-identical content (for example, versioned model artifacts, backup snapshots, or compatibility mirrors) were retained because they may be intentional and deleting them could break references or erase historical state.

## Packaging exclusions
- `.git/`, `node_modules/`, Python bytecode/cache directories, `.pytest_cache/`, and the live SQLite runtime database/WAL/SHM files were omitted from this portable ZIP. These are generated/runtime or environment-specific artifacts; the project source, data, model artifacts, tests, and configuration examples remain.
- No Git command or operation was performed.
