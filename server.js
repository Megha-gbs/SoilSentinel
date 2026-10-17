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
try {
  const Database = require('better-sqlite3');
  db = new Database(dbPath);
  db.pragma('journal_mode = WAL');
  db.pragma('foreign_keys = ON');
} catch (err) {
  const { DatabaseSync } = require('node:sqlite');
  db = new DatabaseSync(dbPath);
  db.exec('PRAGMA journal_mode = WAL');
  db.exec('PRAGMA foreign_keys = ON');
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
app.use(express.json({ limit: '12kb', strict: true }));
app.use(express.urlencoded({ extended: false, limit: '12kb' }));

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

// ---------------------------------------------------------------------------
// Python Backend Bridge Integration (HTTP + CLI Fallback)
// ---------------------------------------------------------------------------
let pythonBridgeProcess = null;

function startPythonBridge() {
  const pythonCmd = process.env.PYTHON_PATH || 'python';
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

    console.info(`[PythonBridge] Spawned background service on port ${PYTHON_PORT}`);
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
      timeout: 3500,
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
    const pythonCmd = process.env.PYTHON_PATH || 'python';
    execFile(pythonCmd, ['-m', 'src.Model.bridge', command, ...args], { cwd: ROOT, timeout: 8000 }, (error, stdout, stderr) => {
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
app.get('/api/assessment/dates', requireAuth, async (req, res) => {
  try {
    const data = await callPythonBridge('/dates', 'dates', []);
    res.json(data);
  } catch (err) {
    console.error('Error fetching assessment dates:', err.message);
    res.status(500).json({ success: false, error: 'Failed to retrieve assessment dates from soil risk service.' });
  }
});

// 2. Request Assessment for a Selected Date
app.get('/api/assessment/evaluate', requireAuth, async (req, res) => {
  const date = req.query.date ? String(req.query.date).trim() : '';
  if (date && !/^\d{4}-\d{2}$/.test(date)) {
    return res.status(400).json({ success: false, error: 'Invalid date format. Expected YYYY-MM.' });
  }

  try {
    const endpoint = date ? `/assessment?date=${encodeURIComponent(date)}` : '/assessment';
    const cliArgs = date ? ['--date', date] : [];
    const data = await callPythonBridge(endpoint, 'assessment', cliArgs);
    res.json(data);
  } catch (err) {
    console.error('Error evaluating assessment:', err.message);
    const status = err.message.includes('not in available') ? 404 : 500;
    res.status(status).json({ success: false, error: err.message || 'Assessment evaluation failed.' });
  }
});

// 3. Interactive What-If Scenario Stress Testing
app.post('/api/assessment/scenario', requireAuth, async (req, res) => {
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
app.get('/farmer-dashboard.html', requireRole('farmer'), (req, res) => res.sendFile(path.join(ROOT, 'farmer-dashboard.html')));
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
