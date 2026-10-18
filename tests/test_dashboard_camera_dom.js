const fs = require('fs');
const path = require('path');

const htmlPath = path.join(__dirname, '..', 'farmer-dashboard.html');
const html = fs.readFileSync(htmlPath, 'utf8');

const requiredIds = [
  'btn-mode-crop',
  'btn-mode-soil',
  'v6-scan-btn-text',
  'v6-camera-input',
  'v6-drop-zone',
  'v6-preview-img',
  'v6-zone-prompt',
  'v6-scan-btn',
  'v6-cam-error',
  'v6-cam-error-msg',
  'v6-cam-error-icon',
  'v6-camera-result',
  'v6-cam-badge',
  'v6-cam-conf',
  'v6-cam-diagnosis',
  'v6-cam-explanation',
  'v6-cam-causes',
  'v6-cam-steps',
  'v6-cam-probabilities-container',
  'v6-cam-probabilities',
  'v6-quality-note',
  'v6-voice-btn'
];

const missing = [];
for (const id of requiredIds) {
  if (!html.includes(`id="${id}"`)) {
    missing.push(id);
  }
}

if (missing.length > 0) {
  console.error('Missing required IDs in farmer-dashboard.html:', missing);
  process.exit(1);
}

console.log(`PASS: All ${requiredIds.length} required camera workflow DOM IDs verified in farmer-dashboard.html`);

// Verify essential script patterns
const scriptPatterns = [
  'setupV6Workflows',
  'showCameraError',
  'clearCameraError',
  'formatDiagnosisTitle',
  'handleSelectedFile',
  '/api/camera/analyze',
  'finally {',
  'scanBtn.disabled = false'
];

for (const pattern of scriptPatterns) {
  if (!html.includes(pattern)) {
    console.error(`Missing expected JavaScript pattern: ${pattern}`);
    process.exit(1);
  }
}

console.log('PASS: All JavaScript workflow functions, error handlers, and finally cleanup blocks verified!');
