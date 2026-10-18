# Website Visuals Implementation Note

## What changed
- Added `dashboard-visuals.js` for backend-driven SVG time-series charts, risk component bars, depth comparisons, the Leaflet study-area locator, and a bounded assessment helper.
- Added farmer and researcher dashboard visualization sections with consistent card/grid styling.
- Added authenticated `GET /api/assessment/observations` through the existing Python bridge; only an allow-listed set of data fields is returned.
- Added visible assessment failure messages and corrected a broken researcher link in the farmer introduction page.
- Extended shared `styles.css` with responsive visual cards, chart sizing, map fallback, helper form, and layout overrides.

## Truthful scope
- Risk timeline plots the deterministic screening index history returned by the existing assessment payload.
- Climate chart plots actual rows in `data/feature_table.csv` and uses the stored precipitation rate in mm/day.
- Soil depth chart displays SoilGrids depth-specific modeled baseline values, not time-varying field samples.
- Map shows the configured sampled point at approximately 30.7392 N, 76.7764 E, not a farm polygon.
- Assessment helper uses simple intent matching against the loaded payload. It is not a general LLM chatbot.

## Verification performed
- Python bridge CLI command `python -m src.Model.bridge observations` returned 60 monthly rows (2020-01 through 2024-12) with coordinate/source metadata in the current environment.
- `node --check` passed for `server.js`, `dashboard-visuals.js`, and `script.js`.
- Inline JavaScript syntax checks passed for all current HTML pages.
- Full browser interaction, tile availability, authentication flow, and LinuxONE deployment still require testing in the team's target environment.
