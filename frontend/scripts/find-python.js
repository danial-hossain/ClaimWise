/** Interpreter discovery shared by both launchers; candidate order is intentional. */
const fs = require('node:fs');
const path = require('node:path');

function environmentPaths(directory) {
  return [path.join(directory, 'Scripts', 'python.exe'), path.join(directory, 'bin', 'python')];
}

function findPythonPath(profile = 'development') {
  const isWindows = process.platform === 'win32';
  const project = path.resolve(__dirname, '../..');
  const candidates = [];
  if (process.env.VIRTUAL_ENV) {
    candidates.push(path.join(process.env.VIRTUAL_ENV, isWindows ? 'Scripts/python.exe' : 'bin/python'));
  }
  candidates.push(...environmentPaths(path.join(project, 'backend', 'venv')));
  if (profile === 'development') {
    candidates.push(...environmentPaths(path.join(project, 'backend', '.venv')));
    candidates.push(...environmentPaths(path.join(project, '.venv')));
  }
  candidates.push(...environmentPaths(path.resolve(project, '../.venv')));
  return candidates.find(candidate => fs.existsSync(candidate)) || (isWindows ? 'python' : 'python3');
}

module.exports = { findPythonPath };
