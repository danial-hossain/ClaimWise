/**
 * ClaimWise Unified Development Server Runner
 *
 * Automatically launches both:
 * 1. FastAPI backend (http://127.0.0.1:8000)
 * 2. Next.js frontend (http://localhost:3000)
 *
 * Ensures the backend is always running whenever `npm run dev` is executed.
 * If backend is already running on port 8000, reuses it without failing.
 */

const { spawn, execSync } = require('child_process');
const http = require('http');
const path = require('path');
const { findPythonPath: resolvePython } = require('./find-python');

const isWindows = process.platform === 'win32';
const backendDir = path.resolve(__dirname, '../../backend');
const frontendDir = path.resolve(__dirname, '..');

// Colors for terminal output
const colors = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  cyan: '\x1b[36m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  magenta: '\x1b[35m',
  red: '\x1b[31m',
};

function log(prefix, color, message) {
  console.log(`${color}${colors.bold}[${prefix}]${colors.reset} ${message}`);
}

/**
 * Detect Python interpreter across virtual environment candidates.
 */
function findPythonPath() { return resolvePython('development'); }

/**
 * Check if the backend is already running on port 8000.
 */
function checkBackendHealth(port = 8000) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/api/v1/health`, { timeout: 1500 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForBackendHealth(backendProc, timeoutMs = 60000, probe = checkBackendHealth) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (backendProc.startupError || backendProc.exitCode !== null || backendProc.signalCode !== null) return false;
    if (await probe()) return true;
    await delay(500);
  }
  return false;
}

async function main() {
  log('ClaimWise', colors.magenta, 'Starting unified development environment...');

  const pythonPath = findPythonPath();
  const alreadyRunning = await checkBackendHealth();

  let backendProc = null;

  if (alreadyRunning) {
    log('Backend', colors.green, 'FastAPI server is already active on http://127.0.0.1:8000 (reusing instance).');
  } else {
    log('Backend', colors.cyan, `Spawning FastAPI backend on http://127.0.0.1:8000 using: ${pythonPath}`);
    
    backendProc = spawn(
      pythonPath,
      ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload'],
      {
        cwd: backendDir,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
        },
        stdio: ['inherit', 'pipe', 'pipe'],
      }
    );

    backendProc.stdout.on('data', (data) => {
      const lines = data.toString().trim().split('\n');
      for (const line of lines) {
        if (line.trim()) {
          console.log(`${colors.cyan}[Backend]${colors.reset} ${line}`);
        }
      }
    });

    backendProc.stderr.on('data', (data) => {
      const lines = data.toString().trim().split('\n');
      for (const line of lines) {
        if (line.trim()) {
          console.error(`${colors.yellow}[Backend]${colors.reset} ${line}`);
        }
      }
    });

    backendProc.on('error', (err) => {
      backendProc.startupError = err;
      log('Backend', colors.red, `Failed to launch FastAPI backend: ${err.message}`);
    });

    backendProc.on('exit', (code, signal) => {
      if (signal !== 'SIGTERM' && signal !== 'SIGINT') {
        log('Backend', colors.yellow, `Backend exited with code ${code || 0} signal ${signal || 'none'}`);
      }
    });

    log('Backend', colors.yellow, 'Waiting for the FastAPI health endpoint...');
    const backendReady = await waitForBackendHealth(backendProc);
    if (!backendReady) {
      log('Backend', colors.red, backendProc.startupError || backendProc.exitCode !== null || backendProc.signalCode !== null
        ? 'Backend stopped before becoming healthy. Check the Python error printed above.'
        : 'Backend did not become healthy within 60 seconds. Check the startup logs above; frontend was not started.');
      if (!backendProc.killed) backendProc.kill();
      process.exit(1);
    }
    log('Backend', colors.green, 'FastAPI is healthy and ready to accept API requests.');
  }

  // Spawn Next.js frontend
  log('Frontend', colors.green, 'Starting Next.js development server on http://localhost:3000...');
  const nextCmd = isWindows ? 'npx.cmd' : 'npx';
  const nextProc = spawn(nextCmd, ['next', 'dev'], {
    cwd: frontendDir,
    stdio: 'inherit',
    shell: isWindows,
  });

  // Cleanup handler for graceful shutdown
  let isCleaningUp = false;
  function cleanup() {
    if (isCleaningUp) return;
    isCleaningUp = true;

    log('ClaimWise', colors.magenta, 'Shutting down services...');

    if (backendProc && !backendProc.killed) {
      if (isWindows && backendProc.pid) {
        try {
          execSync(`taskkill /pid ${backendProc.pid} /T /F`, { stdio: 'ignore' });
        } catch (_) {
          // Process already ended
        }
      } else {
        backendProc.kill('SIGTERM');
      }
    }

    if (nextProc && !nextProc.killed) {
      if (isWindows && nextProc.pid) {
        try {
          execSync(`taskkill /pid ${nextProc.pid} /T /F`, { stdio: 'ignore' });
        } catch (_) {
          // Process already ended
        }
      } else {
        nextProc.kill('SIGTERM');
      }
    }

    process.exit(0);
  }

  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
  process.on('exit', cleanup);

  nextProc.on('exit', (code) => {
    cleanup();
  });
}

if (require.main === module) {
  main().catch((err) => {
    console.error('[ClaimWise Dev Error]:', err);
    process.exit(1);
  });
}
module.exports = { findPythonPath, checkBackendHealth, waitForBackendHealth };
