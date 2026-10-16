/**
 * ClaimWise Standalone Backend Runner
 */

const { spawn } = require('child_process');
const path = require('path');
const { findPythonPath: resolvePython } = require('./find-python');

const backendDir = path.resolve(__dirname, '../../backend');

function findPythonPath() { return resolvePython('standalone'); }

const pythonPath = findPythonPath();
console.log(`[ClaimWise] Launching FastAPI backend using: ${pythonPath}`);

const proc = spawn(
  pythonPath,
  ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--reload'],
  {
    cwd: backendDir,
    stdio: 'inherit',
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
  }
);

proc.on('exit', (code) => {
  process.exit(code || 0);
});
