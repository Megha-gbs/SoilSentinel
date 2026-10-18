require('dotenv').config();
const path = require('path');
const fs = require('fs');
const http = require('http');
const { spawn, execFile } = require('child_process');
const express = require('express');
const helmet = require('helmet');
const session = require('express-session');
const bcrypt = require('bcryptjs');
const { rateLimit } = require('express-rate-limit');

const app = express();
const PORT = Number(process.env.PORT || 3000);
const PYTHON_PORT = Number(process.env.PYTHON_PORT || 5001);
const ROOT = __dirname;
const dbPath = path.resolve(ROOT, process.env.DATABASE_PATH || './data/soilsentinel.sqlite');
fs.mkdirSync(path.dirname(dbPath), { recursive: true });

if (!process.env.SESSION_SECRET || process.env.SESSION_SECRET.length < 32 || process.env.SESSION_SECRET.includes('replace-this')) {
  if (process.env.NODE_ENV === 'production') throw new Error('Set SESSION_SECRET to a unique random value of at least 32 characters.');
  console.warn('WARNING: Set a strong SESSION_SECRET in .env before deployment.');
}

// ---------------------------------------------------------------------------
// Resilient SQLite Database & Session Persistence
// Uses better-sqlite3 if available, or Node.js built-in node:sqlite (Node 22/24)
// ---------------------------------------------------------------------------
let db;
let dbEngine = 'unknown';
try {
  const Database = require('better-sqlite3');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
  dbEngine = 'better-sqlite3';
  console.info('[Database] Initialized via better-sqlite3');
} catch (err) {
  try {
    const { DatabaseSync } = require('node:sqlite');
    db = new DatabaseSync(dbPath);
    db.exec('PRAGMA journal_mode = WAL');
    db.exec('PRAGMA foreign_keys = ON');
    dbEngine = 'node:sqlite (built-in)';
    console.info('[Database] Initialized via Node.js built-in node:sqlite (zero native compilation required)');
  } catch (err2) {
    console.error('[Database FATAL] Neither better-sqlite3 nor node:sqlite could be loaded.');
    console.error('SoilSentinel requires Node.js 22 LTS or Node.js 24 with built-in node:sqlite.');
    process.exit(1);
  }
}

db.exec(`CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL COLLATE NOCASE UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('farmer','researcher')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
)`);

db.exec(`CREATE TABLE IF NOT EXISTS sessions (
  sid TEXT PRIMARY KEY,
  sess TEXT NOT NULL,
  expired INTEGER NOT NULL
)`);

db.exec(`CREATE TABLE IF NOT EXISTS assessments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  assessment_id TEXT UNIQUE NOT NULL,
  user_id INTEGER,
  assessment_type TEXT NOT NULL,
  date_str TEXT,
  latitude REAL,
  longitude REAL,
  crop_type TEXT,
  risk_index REAL,
  risk_category TEXT,
  payload TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  FOREIGN KEY(user_id) REFERENCES users(id)
)`);

class NativeSqliteSessionStore extends session.Store {
  constructor(database) {
    super();
    this.database = database;
    this.getStmt = this.database.prepare('SELECT sess FROM sessions WHERE sid = ? AND expired >= ?');
    this.setStmt = this.database.prepare('INSERT OR REPLACE INTO sessions (sid, sess, expired) VALUES (?, ?, ?)');
    this.destroyStmt = this.database.prepare('DELETE FROM sessions WHERE sid = ?');
    this.cleanupStmt = this.database.prepare('DELETE FROM sessions WHERE expired < ?');
    // Periodic cleanup of expired sessions
    setInterval(() => {
      try { this.cleanupStmt.run(Date.now()); } catch (_) {}
    }, 15 * 60 * 1000).unref();
  }
  get(sid, cb) {
    try {
      const row = this.getStmt.get(sid, Date.now());
      cb(null, row ? JSON.parse(row.sess) : null);
    } catch (e) { cb(e); }
  }
  set(sid, sess, cb) {
    try {
      const maxAge = sess && sess.cookie && sess.cookie.maxAge ? sess.cookie.maxAge : 1000 * 60 * 60 * 8;
      this.setStmt.run(sid, JSON.stringify(sess), Date.now() + maxAge);
      if (cb) cb(null);
    } catch (e) { if (cb) cb(e); }
  }
  destroy(sid, cb) {
    try {
      this.destroyStmt.run(sid);
      if (cb) cb(null);
    } catch (e) { if (cb) cb(e); }
  }
}

const findUserByEmail = db.prepare('SELECT id, name, email, password_hash, role, created_at FROM users WHERE email = ?');
const findUserById = db.prepare('SELECT id, name, email, role, created_at FROM users WHERE id = ?');
const createUser = db.prepare('INSERT INTO users (name,email,password_hash,role) VALUES (?,?,?,?)');

const insertAssessment = db.prepare(`
  INSERT INTO assessments (assessment_id, user_id, assessment_type, date_str, latitude, longitude, crop_type, risk_index, risk_category, payload)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
`);
const findAssessmentsByUser = db.prepare(`
  SELECT id, assessment_id, assessment_type, date_str, latitude, longitude, crop_type, risk_index, risk_category, created_at
  FROM assessments
  WHERE user_id = ?
  ORDER BY id DESC
  LIMIT 50
`);
const findAssessmentById = db.prepare('SELECT * FROM assessments WHERE assessment_id = ?');
const findLatestAssessmentByUser = db.prepare(`
  SELECT * FROM assessments WHERE user_id = ? ORDER BY id DESC LIMIT 1
`);

// Development-only demo accounts for hackathon walkthroughs. Never seed these in production.
if (process.env.NODE_ENV !== 'production' && process.env.ENABLE_DEMO_ACCOUNTS !== 'false') {
  const demoAccounts = [
    { name: 'SoilSentinel Demo Farmer', email: 'farmer.demo@soilsentinel.local', password: 'DemoSoil2026!', role: 'farmer' },
    { name: 'SoilSentinel Demo Researcher', email: 'researcher.demo@soilsentinel.local', password: 'DemoSoil2026!', role: 'researcher' }
  ];
  for (const demo of demoAccounts) {
    if (!findUserByEmail.get(demo.email)) {
      createUser.run(demo.name, demo.email, bcrypt.hashSync(demo.password, 10), demo.role);
    }
  }
  console.info('Development demo accounts enabled (see README.md).');
}

app.disable('x-powered-by');
app.set('trust proxy', process.env.NODE_ENV === 'production' ? 1 : false);
app.use(helmet({ contentSecurityPolicy: false, crossOriginEmbedderPolicy: false }));
app.use('/api/camera/analyze', express.json({ limit: '25mb' }));
app.use('/api/researcher/upload-soil-test', express.json({ limit: '5mb' }));
app.use(express.json({ limit: '64kb', strict: true }));
app.use(express.urlencoded({ extended: false, limit: '64kb' }));

app.use(session({
  name: 'soilsentinel.sid',
  secret: process.env.SESSION_SECRET || 'local-development-only-change-this-secret-now',
  store: new NativeSqliteSessionStore(db),
  resave: false,
  saveUninitialized: false,
  rolling: true,
  cookie: { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production', maxAge: 1000 * 60 * 60 * 8 }
}));

const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 20,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  message: { error: 'Too many authentication attempts. Please wait 15 minutes and try again.' }
});
app.use('/api/auth/register', authLimiter);
app.use('/api/auth/login', authLimiter);

// Browser requests that include an Origin header must come from this same origin.
app.use((req, res, next) => {
  if (['POST','PUT','PATCH','DELETE'].includes(req.method) && req.path.startsWith('/api/')) {
    const origin = req.get('origin');
    if (origin) {
      try {
        if (new URL(origin).host !== req.get('host')) return res.status(403).json({ error: 'Request origin is not allowed.' });
      } catch {
        return res.status(403).json({ error: 'Invalid request origin.' });
      }
    }
  }
  next();
});

const safeUser = user => ({ id: user.id, name: user.name, email: user.email, role: user.role, createdAt: user.created_at });
const roleDashboard = role => role === 'researcher' ? '/researcher-dashboard.html' : '/farmer-dashboard.html';

function establishSession(req, user, res, statusCode=200) {
  req.session.regenerate(err => {
    if (err) return res.status(500).json({ error: 'Could not start a secure session. Please try again.' });
    req.session.userId = user.id;
    req.session.role = user.role;
    req.session.save(saveErr => {
      if (saveErr) return res.status(500).json({ error: 'Could not save your session. Please try again.' });
      res.status(statusCode).json({ user: safeUser(user), redirect: roleDashboard(user.role) });
    });
  });
}

function requireAuth(req, res, next) {
  if (!req.session.userId) return res.status(401).json({ error: 'Authentication required. Please sign in.' });
  const user = findUserById.get(req.session.userId);
  if (!user || user.role !== req.session.role) {
    return req.session.destroy(() => res.status(401).json({ error: 'Session expired. Please sign in again.' }));
  }
  res.locals.currentUser = safeUser(user);
  next();
}

function requireRole(role) {
  return (req, res, next) => {
    if (!req.session.userId) {
      if (req.path.startsWith('/api/')) return res.status(401).json({ error: 'Authentication required. Please sign in.' });
      return res.redirect('/auth.html?mode=login&role=' + role);
    }
    const user = findUserById.get(req.session.userId);
    if (!user) return req.session.destroy(() => {
      if (req.path.startsWith('/api/')) return res.status(401).json({ error: 'Session expired. Please sign in again.' });
      return res.redirect('/auth.html?mode=login');
    });
    if (user.role !== role) {
      if (req.path.startsWith('/api/')) return res.status(403).json({ error: 'Access denied: role mismatch.' });
      return res.redirect(roleDashboard(user.role));
    }
    res.locals.currentUser = safeUser(user);
    next();
  };
}

const guestLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 60,
  standardHeaders: 'draft-7',
  legacyHeaders: false,
  message: { error: 'Guest rate limit reached. Please wait a few minutes or create a free account to continue.' }
});

function allowGuestOrAuth(req, res, next) {
  if (req.session && req.session.userId) {
    const user = findUserById.get(req.session.userId);
    if (user && user.role === req.session.role) {
      res.locals.currentUser = safeUser(user);
      res.locals.isGuest = false;
      return next();
    }
  }
  // Allow guest exploration with non-persistent session isolation & rate-limiting
  guestLimiter(req, res, () => {
    res.locals.isGuest = true;
    res.locals.currentUser = { id: null, name: 'Guest Visitor', role: 'guest' };
    next();
  });
}

// ---------------------------------------------------------------------------
// Python Backend Bridge Integration (HTTP + CLI Fallback)
// ---------------------------------------------------------------------------
let pythonBridgeProcess = null;

function resolvePythonExecutable() {
  if (process.env.PYTHON_PATH && (fs.existsSync(process.env.PYTHON_PATH) || !path.isAbsolute(process.env.PYTHON_PATH))) {
    return process.env.PYTHON_PATH;
  }
  if (process.env.PYTHON_CMD && (fs.existsSync(process.env.PYTHON_CMD) || !path.isAbsolute(process.env.PYTHON_CMD))) {
    return process.env.PYTHON_CMD;
  }
  if (process.env.PYTHON_BIN && (fs.existsSync(process.env.PYTHON_BIN) || !path.isAbsolute(process.env.PYTHON_BIN))) {
    return process.env.PYTHON_BIN;
  }

  const venvs = [
    path.join(ROOT, '.venv', 'Scripts', 'python.exe'),
    path.join(ROOT, 'venv', 'Scripts', 'python.exe'),
    path.join(ROOT, '.venv', 'bin', 'python'),
    path.join(ROOT, 'venv', 'bin', 'python'),
    '/opt/venv/bin/python',
  ];
  for (const venvPath of venvs) {
    if (fs.existsSync(venvPath)) {
      return venvPath;
    }
  }

  return process.platform === 'win32' ? 'python' : 'python3';
}

let pythonEnvInfo = {
  executable: null,
  version: null,
  has_cv2: false,
  cv2_version: null,
  checked: false
};

function checkPythonEnvironment(pythonExe) {
  return new Promise(resolve => {
    const code = "import sys, json\ninfo={'executable': sys.executable, 'version': sys.version.split(' ')[0], 'has_cv2': False, 'cv2_version': None}\ntry:\n import cv2\n info['has_cv2'] = True\n info['cv2_version'] = getattr(cv2, '__version__', 'unknown')\nexcept Exception as e:\n info['cv2_error'] = str(e)\nprint(json.dumps(info))";
    execFile(pythonExe, ['-c', code], { timeout: 8000 }, (err, stdout) => {
      if (!err && stdout) {
        try {
          const parsed = JSON.parse(stdout.trim());
          pythonEnvInfo = { ...parsed, checked: true };
          console.info(`[Python Runtime] Interpreter: ${parsed.executable} (Python ${parsed.version})`);
          if (parsed.has_cv2) {
            console.info(`[Python Runtime] OpenCV ('cv2') verified: v${parsed.cv2_version} (Camera AI ready)`);
          } else {
            console.warn(`[Python Runtime] WARNING: OpenCV ('cv2') is NOT installed in ${parsed.executable}. Camera AI diagnostic will report dependency unavailable.`);
          }
          return resolve(pythonEnvInfo);
        } catch (_) {}
      }
      pythonEnvInfo = { executable: pythonExe, version: 'unknown', has_cv2: false, cv2_version: null, checked: true };
      resolve(pythonEnvInfo);
    });
  });
}

async function startPythonBridge() {
  const pythonCmd = resolvePythonExecutable();
  await checkPythonEnvironment(pythonCmd);
  try {
    pythonBridgeProcess = spawn(pythonCmd, ['-m', 'src.Model.bridge', 'serve', '--port', String(PYTHON_PORT)], {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    pythonBridgeProcess.stdout.on('data', data => {
      console.log(`[PythonBridge stdout] ${data.toString().trim()}`);
    });

    pythonBridgeProcess.stderr.on('data', data => {
      console.log(`[PythonBridge stderr] ${data.toString().trim()}`);
    });

    pythonBridgeProcess.on('exit', (code, signal) => {
      console.warn(`[PythonBridge] Exited with code ${code}, signal ${signal}`);
      pythonBridgeProcess = null;
    });

    console.info(`[PythonBridge] Spawned background service on port ${PYTHON_PORT} using ${pythonCmd}`);
  } catch (err) {
    console.error('[PythonBridge] Failed to spawn bridge process:', err.message);
  }
}

function cleanupPythonBridge() {
  if (pythonBridgeProcess) {
    try {
      pythonBridgeProcess.kill();
      pythonBridgeProcess = null;
    } catch (_) {}
  }
}
process.on('SIGINT', () => { cleanupPythonBridge(); process.exit(0); });
process.on('SIGTERM', () => { cleanupPythonBridge(); process.exit(0); });
process.on('exit', () => { cleanupPythonBridge(); });

function queryBridgeHttp(endpoint, method = 'GET', body = null) {
  return new Promise((resolve, reject) => {
    const postData = body ? JSON.stringify(body) : null;
    const req = http.request({
      hostname: '127.0.0.1',
      port: PYTHON_PORT,
      path: endpoint,
      method: method,
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json',
        ...(postData ? { 'Content-Length': Buffer.byteLength(postData) } : {})
      }
    }, res => {
      let rawData = '';
      res.on('data', chunk => rawData += chunk);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(rawData);
          if (res.statusCode >= 200 && res.statusCode < 300) {
            resolve(parsed);
          } else {
            reject(new Error(parsed.error || `HTTP ${res.statusCode}`));
          }
        } catch (e) {
          reject(new Error(`Invalid JSON response: ${rawData.slice(0, 100)}`));
        }
      });
    });

    req.on('error', err => reject(err));
    req.on('timeout', () => { req.destroy(); reject(new Error('Python bridge HTTP timeout')); });

    if (postData) req.write(postData);
    req.end();
  });
}

function queryBridgeCli(command, args = []) {
  return new Promise((resolve, reject) => {
    const pythonCmd = resolvePythonExecutable();
    execFile(pythonCmd, ['-m', 'src.Model.bridge', command, ...args], { cwd: ROOT, timeout: 25000 }, (error, stdout, stderr) => {
      if (error) {
        let errMessage = error.message;
        try {
          const errJson = JSON.parse(stderr);
          if (errJson.error) errMessage = errJson.error;
        } catch (_) {}
        return reject(new Error(errMessage));
      }
      try {
        const parsed = JSON.parse(stdout);
        resolve(parsed);
      } catch (e) {
        reject(new Error(`Failed to parse CLI output: ${stdout.slice(0, 120)}`));
      }
    });
  });
}

async function callPythonBridge(endpoint, cliCmd, cliArgs, httpMethod = 'GET', httpBody = null) {
  try {
    return await queryBridgeHttp(endpoint, httpMethod, httpBody);
  } catch (httpErr) {
    // Fall back to CLI execution
    return await queryBridgeCli(cliCmd, cliArgs);
  }
}

// ---------------------------------------------------------------------------
// Authentication Routes
// ---------------------------------------------------------------------------
app.post('/api/auth/register', async (req, res) => {
  const name = typeof req.body.name === 'string' ? req.body.name.trim() : '';
  const email = typeof req.body.email === 'string' ? req.body.email.trim().toLowerCase() : '';
  const password = typeof req.body.password === 'string' ? req.body.password : '';
  const role = req.body.role;

  if (name.length < 2 || name.length > 100) return res.status(400).json({ error: 'Enter a name between 2 and 100 characters.' });
  if (email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return res.status(400).json({ error: 'Enter a valid email address.' });
  if (password.length < 10 || password.length > 128) return res.status(400).json({ error: 'Password must be between 10 and 128 characters.' });
  if (!['farmer','researcher'].includes(role)) return res.status(400).json({ error: 'Choose Farmer or Researcher as your account type.' });
  if (findUserByEmail.get(email)) return res.status(409).json({ error: 'An account with this email already exists. Sign in instead.' });

  try {
    const hash = await bcrypt.hash(password, 12);
    const result = createUser.run(name, email, hash, role);
    const newId = Number(result.lastInsertRowid);
    const user = findUserById.get(newId);
    return establishSession(req, user, res, 201);
  } catch (error) {
    if (String(error.code).includes('SQLITE_CONSTRAINT')) return res.status(409).json({ error: 'An account with this email already exists. Sign in instead.' });
    console.error('Registration failed:', error.message);
    return res.status(500).json({ error: 'Account creation failed. Please try again.' });
  }
});

app.post('/api/auth/login', async (req, res) => {
  const email = typeof req.body.email === 'string' ? req.body.email.trim().toLowerCase() : '';
  const password = typeof req.body.password === 'string' ? req.body.password : '';
  if (!email || !password || email.length > 254 || password.length > 128) return res.status(400).json({ error: 'Enter your email and password.' });

  const user = findUserByEmail.get(email);
  const valid = user ? await bcrypt.compare(password, user.password_hash) : false;
  if (!valid) return res.status(401).json({ error: 'Email or password is incorrect.' });
  return establishSession(req, user, res);
});

app.get('/api/auth/me', (req, res) => {
  if (!req.session.userId) return res.status(401).json({ authenticated: false, error: 'Sign in to continue.' });
  const user = findUserById.get(req.session.userId);
  if (!user || user.role !== req.session.role) {
    return req.session.destroy(() => res.status(401).json({ authenticated: false, error: 'Session is no longer valid. Please sign in again.' }));
  }
  res.json({ authenticated: true, user: safeUser(user), redirect: roleDashboard(user.role) });
});

app.post('/api/auth/logout', (req, res) => {
  req.session.destroy(err => {
    res.clearCookie('soilsentinel.sid', { httpOnly: true, sameSite: 'lax', secure: process.env.NODE_ENV === 'production' });
    if (err) return res.status(500).json({ error: 'Could not end the session cleanly.' });
    res.json({ ok: true, redirect: '/index.html' });
  });
});

// ---------------------------------------------------------------------------
// Soil Assessment & Real Python Backend Endpoints (Role-Protected)
// ---------------------------------------------------------------------------

// 1. Retrieve Available Assessment Dates
app.get('/api/assessment/dates', allowGuestOrAuth, async (req, res) => {
  try {
    const data = await callPythonBridge('/dates', 'dates', []);
    res.json(data);
  } catch (err) {
    console.error('Error fetching assessment dates:', err.message);
    res.status(500).json({ success: false, error: 'Failed to retrieve assessment dates from soil risk service.' });
  }
});

// 2. Request Assessment for a Selected Date
app.get('/api/assessment/evaluate', allowGuestOrAuth, async (req, res) => {
  const date = req.query.date ? String(req.query.date).trim() : '';
  if (date && !/^\d{4}-\d{2}$/.test(date)) {
    return res.status(400).json({ success: false, error: 'Invalid date format. Expected YYYY-MM.' });
  }

  try {
    const endpoint = date ? `/assessment?date=${encodeURIComponent(date)}` : '/assessment';
    const cliArgs = date ? ['--date', date] : [];
    const data = await callPythonBridge(endpoint, 'assessment', cliArgs);

    // Persist assessment into database for traceability and historical tracking (authenticated users only)
    if (!res.locals.isGuest && req.session.userId && data && data.success && data.payload) {
      try {
        const p = data.payload;
        const asmId = p.audit_log?.assessment_id || `ASM-${date || 'LATEST'}-${Date.now()}`;
        const riskIdx = p.risk_scoring?.risk_index ?? p.risk_scoring?.baseline_risk_score ?? null;
        const riskCat = p.risk_scoring?.risk_category || 'UNKNOWN';
        insertAssessment.run(
          asmId,
          req.session.userId,
          'date_baseline',
          date || p.evaluation_date || 'latest',
          null,
          null,
          null,
          riskIdx,
          riskCat,
          JSON.stringify(p)
        );
        data.persisted_assessment_id = asmId;
      } catch (eSave) {
        if (!String(eSave).includes('UNIQUE')) {
          console.warn('[Database] Could not persist assessment record:', eSave.message);
        }
      }
    }

    res.json(data);
  } catch (err) {
    console.error('Error evaluating assessment:', err.message);
    const status = err.message.includes('not in available') ? 404 : 500;
    res.status(status).json({ success: false, error: err.message || 'Assessment evaluation failed.' });
  }
});

// 3. Interactive What-If Scenario Stress Testing
app.post(['/api/assessment/scenario', '/api/scenario'], allowGuestOrAuth, async (req, res) => {
  const date = req.body.date ? String(req.body.date).trim() : '';
  const rainfall = parseFloat(req.body.rainfall_mm !== undefined ? req.body.rainfall_mm : req.body.custom_precipitation);
  const temp = parseFloat(req.body.temp_c !== undefined ? req.body.temp_c : req.body.custom_temperature);
  const horizon = parseInt(req.body.horizon_days !== undefined ? req.body.horizon_days : 30, 10);

  if (date && !/^\d{4}-\d{2}$/.test(date)) {
    return res.status(400).json({ success: false, error: 'Invalid date format. Expected YYYY-MM.' });
  }
  if (isNaN(rainfall) || rainfall < 0 || rainfall > 200) {
    return res.status(400).json({ success: false, error: 'Hypothetical rainfall must be between 0.0 and 200.0 mm/day.' });
  }
  if (isNaN(temp) || temp < -50 || temp > 70) {
    return res.status(400).json({ success: false, error: 'Hypothetical temperature must be between -50.0 and 70.0 degrees Celsius.' });
  }
  if (isNaN(horizon) || horizon < 1 || horizon > 365) {
    return res.status(400).json({ success: false, error: 'Horizon must be between 1 and 365 days.' });
  }

  const payload = { date: date || undefined, custom_precipitation: rainfall, custom_temperature: temp, horizon_days: horizon };
  const cliArgs = [
    ...(date ? ['--date', date] : []),
    '--precip', String(rainfall),
    '--temp', String(temp),
    '--horizon', String(horizon)
  ];

  try {
    const data = await callPythonBridge('/scenario', 'scenario', cliArgs, 'POST', payload);
    res.json(data);
  } catch (err) {
    console.error('Error evaluating scenario:', err.message);
    res.status(500).json({ success: false, error: err.message || 'Scenario evaluation failed.' });
  }
});

// Read-only, allow-listed observations for dashboards.
app.get('/api/assessment/observations', allowGuestOrAuth, async (req, res) => {
  try {
    const data = await callPythonBridge('/observations', 'observations', []);
    res.json(data);
  } catch (err) {
    console.error('Error fetching chart observations:', err.message);
    res.status(503).json({
      success: false,
      error: 'Study-area observations are unavailable. Charts are withheld rather than filled with placeholder values.'
    });
  }
});

// 4. One-Click Camera Diagnostic Scan (Crop Symptoms or Soil Surface Morphology)
app.post('/api/camera/analyze', allowGuestOrAuth, async (req, res) => {
  const image = req.body.image || req.body.image_data || req.body.image_base64 || req.body.imageData || '';
  const modality = (req.body.modality || req.body.target_mode || req.body.mode || 'crop').toLowerCase();
  if (!image || typeof image !== 'string' || !image.trim()) {
    return res.status(400).json({ success: false, error: 'Please capture or upload an image.' });
  }
  if (!['crop', 'soil'].includes(modality)) {
    return res.status(400).json({ success: false, error: "Modality must be 'crop' or 'soil'." });
  }

  const payload = {
    image,
    image_data: image,
    image_base64: image,
    modality,
    target_mode: modality
  };
  // For CLI fallback: write large images to temp file to avoid Windows command line length limits
  let tempFilePath = null;
  const cliArgs = ['--modality', modality];
  if (image.length > 500) {
    try {
      tempFilePath = path.join(ROOT, 'data', `temp_cam_${Date.now()}_${process.pid}.txt`);
      fs.writeFileSync(tempFilePath, image, 'utf8');
      cliArgs.push('--image-file', tempFilePath);
    } catch (_) {
      cliArgs.push('--image', image.slice(0, 500));
    }
  } else {
    cliArgs.push('--image', image);
  }

  try {
    const data = await callPythonBridge('/camera-analyze', 'camera-analyze', cliArgs, 'POST', payload);
    res.json(data);
  } catch (err) {
    console.error('Error in camera diagnosis:', err.message);
    const isCv2Error = err.message && (err.message.includes('cv2') || err.message.includes('No module named'));
    const userErrMsg = isCv2Error
      ? "OpenCV ('cv2') is not installed in the backend Python runtime. Please install 'opencv-python-headless' to enable optical camera analysis."
      : (err.message || 'Camera diagnosis failed.');
    res.status(isCv2Error ? 503 : 500).json({ success: false, error: userErrMsg, dependency_missing: isCv2Error });
  } finally {
    if (tempFilePath && fs.existsSync(tempFilePath)) {
      try { fs.unlinkSync(tempFilePath); } catch (_) {}
    }
  }
});

// 5. Global GPS Field Assessment (ISRIC SoilGrids + Open-Meteo/NASA Weather + V6 Multi-Task)
app.post('/api/gps/assess', allowGuestOrAuth, async (req, res) => {
  const lat = parseFloat(req.body.latitude !== undefined ? req.body.latitude : req.body.lat);
  const lon = parseFloat(req.body.longitude !== undefined ? req.body.longitude : req.body.lon);
  const cropType = req.body.crop_type || '';
  const irrigationType = req.body.irrigation_type || '';
  const fieldSoilTest = req.body.field_soil_test || null;

  if (isNaN(lat) || lat < -90 || lat > 90) {
    return res.status(400).json({ success: false, error: 'Latitude must be a valid number between -90 and 90.' });
  }
  if (isNaN(lon) || lon < -180 || lon > 180) {
    return res.status(400).json({ success: false, error: 'Longitude must be a valid number between -180 and 180.' });
  }

  const payload = { latitude: lat, longitude: lon, crop_type: cropType, irrigation_type: irrigationType, field_soil_test: fieldSoilTest };
  const cliArgs = [
    '--lat', String(lat),
    '--lon', String(lon),
    ...(cropType ? ['--crop', cropType] : []),
    ...(irrigationType ? ['--irrigation', irrigationType] : []),
    ...(fieldSoilTest ? ['--soil-data', JSON.stringify(fieldSoilTest)] : [])
  ];

  try {
    const data = await callPythonBridge('/gps-assess', 'gps-assess', cliArgs, 'POST', payload);

    // Persist GPS assessment into database (authenticated users only)
    if (!res.locals.isGuest && req.session.userId && data && data.success) {
      try {
        const asmId = `GPS-${lat.toFixed(4)}-${lon.toFixed(4)}-${Date.now()}`;
        const v6 = data.v6_predictions || {};
        const riskIdx = v6.task_a_soil_organic_carbon?.predicted_soc_g_kg || null;
        const riskCat = v6.task_b_salinity?.predicted_salinity_class || 'GPS_EVALUATED';
        insertAssessment.run(
          asmId,
          req.session.userId,
          'gps_field',
          new Date().toISOString().slice(0, 10),
          lat,
          lon,
          cropType || null,
          riskIdx,
          riskCat,
          JSON.stringify(data)
        );
        data.persisted_assessment_id = asmId;
      } catch (eSave) {
        console.warn('[Database] Could not persist GPS assessment:', eSave.message);
      }
    }

    res.json(data);
  } catch (err) {
    console.error('Error in GPS field assessment:', err.message);
    res.status(500).json({ success: false, error: err.message || 'GPS field assessment failed.' });
  }
});

// 5b. Spatial Layers Endpoint (Sentinel-2 10m NDVI raster, AOI polygon, 250m SoilGrids grid footprint, benchmarks)
app.get('/api/spatial/layers', allowGuestOrAuth, async (req, res) => {
  const lat = req.query.lat !== undefined ? parseFloat(req.query.lat) : 30.7333;
  const lon = req.query.lon !== undefined ? parseFloat(req.query.lon) : 76.7794;
  const date = req.query.date ? String(req.query.date).trim() : '2024-12';
  const cliArgs = ['--lat', String(lat), '--lon', String(lon), '--date', date];
  try {
    const data = await callPythonBridge(`/spatial-layers?lat=${lat}&lon=${lon}&date=${date}`, 'spatial-layers', cliArgs);
    res.json(data);
  } catch (err) {
    console.error('Error fetching spatial layers:', err.message);
    res.status(500).json({ success: false, error: err.message || 'Failed to retrieve spatial layers.' });
  }
});

app.post('/api/spatial/layers', allowGuestOrAuth, async (req, res) => {
  const lat = parseFloat(req.body.latitude !== undefined ? req.body.latitude : (req.body.lat !== undefined ? req.body.lat : 30.7333));
  const lon = parseFloat(req.body.longitude !== undefined ? req.body.longitude : (req.body.lon !== undefined ? req.body.lon : 76.7794));
  const date = req.body.date ? String(req.body.date).trim() : '2024-12';
  const payload = { latitude: lat, longitude: lon, date: date };
  const cliArgs = ['--lat', String(lat), '--lon', String(lon), '--date', date];
  try {
    const data = await callPythonBridge('/spatial-layers', 'spatial-layers', cliArgs, 'POST', payload);
    res.json(data);
  } catch (err) {
    console.error('Error fetching spatial layers:', err.message);
    res.status(500).json({ success: false, error: err.message || 'Failed to retrieve spatial layers.' });
  }
});

// 6. Researcher Laboratory Soil-Test Assessment (V6 Multi-Task & SHAP)
app.post('/api/researcher/upload-soil-test', requireRole('researcher'), async (req, res) => {
  const soilData = req.body.soil_test || req.body.measurements || req.body;
  if (!soilData || typeof soilData !== 'object') {
    return res.status(400).json({ success: false, error: 'Provide valid soil laboratory measurements (pH, EC, texture, SOC).' });
  }

  const payload = { soil_test: soilData };
  const cliArgs = ['--soil-data', JSON.stringify(soilData)];

  try {
    const data = await callPythonBridge('/soil-test-assess', 'soil-test-assess', cliArgs, 'POST', payload);

    // Persist Soil-Test Assessment into database
    if (data && data.success) {
      try {
        const asmId = `LAB-${Date.now()}`;
        insertAssessment.run(
          asmId,
          req.session.userId,
          'soil_lab_test',
          new Date().toISOString().slice(0, 10),
          parseFloat(soilData.latitude || soilData.lat) || null,
          parseFloat(soilData.longitude || soilData.lon) || null,
          null,
          parseFloat(soilData.soil_organic_carbon_g_kg || soilData.organic_carbon_g_kg) || null,
          'LAB_VERIFIED',
          JSON.stringify(data)
        );
        data.persisted_assessment_id = asmId;
      } catch (eSave) {
        console.warn('[Database] Could not persist Lab assessment:', eSave.message);
      }
    }

    res.json(data);
  } catch (err) {
    console.error('Error analyzing soil test:', err.message);
    res.status(500).json({ success: false, error: err.message || 'Soil test evaluation failed.' });
  }
});

// 7. Assessment History (User-Scoped; Guest Isolation)
app.get('/api/assessment/history', (req, res) => {
  if (!req.session || !req.session.userId) {
    return res.json({
      success: true,
      count: 0,
      history: [],
      is_guest: true,
      message: 'Guest session active. Create a free account to permanently persist assessment records.'
    });
  }
  try {
    const rows = findAssessmentsByUser.all(req.session.userId);
    res.json({
      success: true,
      count: rows.length,
      history: rows,
      is_guest: false
    });
  } catch (err) {
    console.error('Error fetching assessment history:', err.message);
    res.status(500).json({ success: false, error: 'Failed to retrieve assessment history.' });
  }
});

// 8. Downloadable Audit Report Export (Role-Protected)
app.get('/api/assessment/export', requireAuth, (req, res) => {
  const asmId = req.query.id ? String(req.query.id).trim() : '';
  const format = (req.query.format || 'text').toLowerCase();

  let record = null;
  if (asmId) {
    record = findAssessmentById.get(asmId);
  } else {
    record = findLatestAssessmentByUser.get(req.session.userId);
  }

  if (!record) {
    return res.status(404).json({ success: false, error: 'No assessment found to export. Run an assessment first.' });
  }

  if (record.user_id !== req.session.userId && req.session.role !== 'researcher') {
    return res.status(403).json({ success: false, error: 'Access denied.' });
  }

  let payloadObj = {};
  try { payloadObj = JSON.parse(record.payload); } catch (_) {}

  const filenameBase = `soilsentinel-report-${record.assessment_id}`;

  if (format === 'json') {
    res.setHeader('Content-Disposition', `attachment; filename="${filenameBase}.json"`);
    res.setHeader('Content-Type', 'application/json; charset=utf-8');
    return res.send(JSON.stringify({
      assessment_id: record.assessment_id,
      assessment_type: record.assessment_type,
      evaluation_date: record.date_str,
      coordinates: record.latitude && record.longitude ? { latitude: record.latitude, longitude: record.longitude } : null,
      crop_type: record.crop_type,
      risk_index: record.risk_index,
      risk_category: record.risk_category,
      created_at: record.created_at,
      details: payloadObj,
      scientific_disclaimer: 'SoilSentinel assessments combine empirical sensor data, NASA POWER agroclimatology, and SoilGrids 250m estimates. Model attributions and risk indices approximate physical stress and do not replace certified laboratory testing.'
    }, null, 2));
  }

  const reportText = `================================================================================
SOILSENTINEL SOIL HEALTH & ENVIRONMENTAL RISK ASSESSMENT REPORT
================================================================================
Assessment ID      : ${record.assessment_id}
Generated Timestamp: ${record.created_at}
Evaluation Window  : ${record.date_str || 'N/A'}
Assessment Type    : ${record.assessment_type}
Location           : ${record.latitude ? `${record.latitude.toFixed(4)}°N, ${record.longitude.toFixed(4)}°E` : 'Regional Baseline (Punjab Study Area)'}
Crop / Context     : ${record.crop_type || 'Unspecified'}

--------------------------------------------------------------------------------
1. ASSESSMENT SUMMARY & RISK METRICS
--------------------------------------------------------------------------------
Baseline Risk Index : ${record.risk_index !== null ? Number(record.risk_index).toFixed(2) : 'N/A'} / 100
Risk Category       : ${record.risk_category || 'N/A'}
Evidence Tier       : ${payloadObj.risk_scoring?.data_quality?.evidence_tier || 'Tier 1 Empirical Ground Data'}
Observation Status  : ${payloadObj.risk_scoring?.data_quality?.status || 'VALID'}

--------------------------------------------------------------------------------
2. PRIMARY RISK DRIVERS & SOIL ESTIMATES
--------------------------------------------------------------------------------
${(payloadObj.risk_scoring?.sorted_indicators || []).map(ind => `• ${ind.indicator_name.padEnd(30)}: Value = ${ind.raw_value !== null ? ind.raw_value.toFixed(2) : 'N/A'} | Weighted Score = ${ind.weighted_score.toFixed(2)}`).join('\n') || '• No specific indicator breakdown available.'}

--------------------------------------------------------------------------------
3. RANKED ACTIONABLE RECOMMENDATIONS
--------------------------------------------------------------------------------
${(payloadObj.recommendations?.top_three_recommendations || []).map((r, i) => `${i + 1}. [${r.urgency || 'MEDIUM'}] ${r.title}
   Expected Benefit: ${r.expected_benefit || 'Improves soil retention and moisture resilience.'}
   Rationale       : ${r.rationale || 'Address elevated risk drivers identified in assessment.'}
   Implementation  : ${r.implementation_timeline || 'Within next crop cycle.'}
`).join('\n') || '1. Maintain balanced soil fertility management.\n2. Monitor topsoil moisture following precipitation events.\n3. Conduct periodic local laboratory soil chemistry verification.'}

--------------------------------------------------------------------------------
4. DATA PROVENANCE & SATELLITE RASTERS
--------------------------------------------------------------------------------
Meteorological Source : NASA POWER Agroclimatology (precipitation, temperature, VPD)
Pedological Source   : ISRIC SoilGrids 250m Spatial Mapped Estimates
Multispectral Rasters: Sentinel-2 L2A BOA Reflectance (B02-B12, NDDI, NDWI)
Historical Baseline  : 60-Month Harmonized Observations (2020-2024)

--------------------------------------------------------------------------------
5. SCIENTIFIC HONESTY & LIMITATIONS NOTICE
--------------------------------------------------------------------------------
Notice: The SoilSentinel Risk Index and surrogate machine-learning models estimate
environmental vulnerability and seasonal stress based on empirical observations and
satellite indicators. Mapped SoilGrids estimates and optical camera diagnoses reflect
surface morphology and regional priors, NOT direct in-situ laboratory measurements.
For definitive agronomic decisions, certified laboratory soil testing is recommended.
================================================================================
`;

  res.setHeader('Content-Disposition', `attachment; filename="${filenameBase}.txt"`);
  res.setHeader('Content-Type', 'text/plain; charset=utf-8');
  res.send(reportText);
});

// 9. Unauthenticated System & API Health Check
app.get(['/api/health', '/health'], async (req, res) => {
  let pyStatus = 'checking';
  let pyError = null;
  try {
    const pyRes = await queryBridgeHttp('/health');
    pyStatus = pyRes && pyRes.status === 'ok' ? 'ok' : 'degraded';
  } catch (e) {
    pyStatus = 'unavailable';
    pyError = e.message;
  }

  let dbOk = false;
  let userCount = 0;
  let asmCount = 0;
  try {
    const uRow = db.prepare('SELECT COUNT(*) as c FROM users').get();
    userCount = uRow ? uRow.c : 0;
    const aRow = db.prepare('SELECT COUNT(*) as c FROM assessments').get();
    asmCount = aRow ? aRow.c : 0;
    dbOk = true;
  } catch (eDb) {
    dbOk = false;
  }

  const isHealthy = dbOk && pyStatus === 'ok';
  res.status(isHealthy ? 200 : 503).json({
    status: isHealthy ? 'healthy' : 'degraded',
    service: 'SoilSentinel Web & ML Backend',
    timestamp: new Date().toISOString(),
    uptime_seconds: Math.floor(process.uptime()),
    node_version: process.version,
    platform: process.platform,
    arch: process.arch,
    database: {
      status: dbOk ? 'connected' : 'error',
      engine: dbEngine,
      users_count: userCount,
      assessments_count: asmCount
    },
    python_bridge: {
      status: pyStatus,
      port: PYTHON_PORT,
      error: pyError
    },
    camera_ai: {
      status: pythonEnvInfo.has_cv2 ? 'ready' : 'dependency_missing',
      opencv_available: pythonEnvInfo.has_cv2,
      opencv_version: pythonEnvInfo.cv2_version,
      interpreter: pythonEnvInfo.executable
    }
  });
});

// Workspace summary endpoints
app.get('/api/farmer/workspace', requireRole('farmer'), async (req, res) => {
  try {
    const assessData = await callPythonBridge('/assessment', 'assessment', []);
    res.json({
      user: res.locals.currentUser,
      latest_assessment: assessData.payload || null,
      modules: ['Soil overview', 'Farm records', 'Assessment history', 'Practical guidance']
    });
  } catch (e) {
    res.json({
      user: res.locals.currentUser,
      latest_assessment: null,
      backend_error: e.message,
      modules: ['Soil overview', 'Farm records', 'Assessment history', 'Practical guidance']
    });
  }
});

app.get('/api/researcher/workspace', requireRole('researcher'), async (req, res) => {
  try {
    const [datesData, assessData] = await Promise.all([
      callPythonBridge('/dates', 'dates', []),
      callPythonBridge('/assessment', 'assessment', [])
    ]);
    res.json({
      user: res.locals.currentUser,
      available_dates: datesData.available_dates || [],
      latest_assessment: assessData.payload || null,
      modules: ['Research overview', 'Dataset explorer', 'Evidence and provenance', 'Assessment history']
    });
  } catch (e) {
    res.json({
      user: res.locals.currentUser,
      available_dates: [],
      latest_assessment: null,
      backend_error: e.message,
      modules: ['Research overview', 'Dataset explorer', 'Evidence and provenance', 'Assessment history']
    });
  }
});

// Page routes
app.get(['/farmer-dashboard.html', '/guest'], (req, res) => {
  if (req.session && req.session.userId) {
    const user = findUserById.get(req.session.userId);
    if (user && user.role === 'researcher') {
      return res.redirect('/researcher-dashboard.html');
    }
  }
  res.sendFile(path.join(ROOT, 'farmer-dashboard.html'));
});
app.get('/researcher-dashboard.html', requireRole('researcher'), (req, res) => res.sendFile(path.join(ROOT, 'researcher-dashboard.html')));

// Keep private files and implementation/database files out of the static web root.
app.use(express.static(ROOT, {
  index: 'index.html',
  dotfiles: 'ignore',
  setHeaders(res, filePath) {
    if (/\.(sqlite|db|env|py|pyc|csv|json)$/i.test(filePath)) {
      res.status(404);
    }
  }
}));

app.use((req, res) => req.path.startsWith('/api/') ? res.status(404).json({ error: 'API endpoint not found.' }) : res.status(404).send('Page not found. <a href="/">Return to SoilSentinel</a>'));

app.listen(PORT, () => {
  console.log(`SoilSentinel running at http://localhost:${PORT}`);
  startPythonBridge();
});
