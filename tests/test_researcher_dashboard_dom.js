/**
 * Verification test for researcher-dashboard.html DOM elements and rendering functions.
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

const htmlPath = path.join(__dirname, '..', 'researcher-dashboard.html');
const html = fs.readFileSync(htmlPath, 'utf8');

console.log("=== Testing researcher-dashboard.html DOM elements ===");

const requiredIds = [
  'v6-res-results-box',
  'v6-eval-timestamp',
  'v6-eval-ood-badge',
  'res-soc-pred',
  'res-soc-meta',
  'res-sal-pred',
  'res-sal-meta',
  'res-acid-pred',
  'res-acid-meta',
  'res-sod-pred',
  'res-sod-meta',
  'res-stress-pred',
  'res-stress-meta',
  'btn-eval-soil-test',
  'res-file-upload',
  'btn-export-eval-json',
  'res-depth',
  'res-ph',
  'res-ec',
  'res-soc',
  'res-clay',
  'res-sand',
  'res-silt',
  'res-lat',
  'res-lon'
];

requiredIds.forEach(id => {
  assert(html.includes(`id="${id}"`), `Missing required DOM id: ${id}`);
  console.log(`PASS: Found id="${id}"`);
});

assert(html.includes('renderV6MultiTaskPredictions'), 'renderV6MultiTaskPredictions function missing');
console.log('PASS: Found renderV6MultiTaskPredictions');

assert(html.includes('predicted_soc_g_kg'), 'Field mapping for predicted_soc_g_kg missing');
assert(html.includes('predicted_salinity_class'), 'Field mapping for predicted_salinity_class missing');
assert(html.includes('predicted_acidity_class'), 'Field mapping for predicted_acidity_class missing');
assert(html.includes('proxy_risk_category') || html.includes('predicted_risk_category'), 'Field mapping for surrogate risk category missing');
assert(html.includes('is_in_domain'), 'Domain applicability is_in_domain missing');

console.log("\nALL 25 DOM CHECKS PASSED!");
