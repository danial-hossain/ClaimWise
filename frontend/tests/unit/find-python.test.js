const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { findPythonPath } = require('../../scripts/find-python');

test('launcher profiles retain their distinct virtualenv search order', t => {
  const active = process.env.VIRTUAL_ENV;
  delete process.env.VIRTUAL_ENV;
  t.after(() => { if (active !== undefined) process.env.VIRTUAL_ENV = active; });
  const visited = [];
  t.mock.method(fs, 'existsSync', candidate => { visited.push(candidate.replaceAll('\\', '/')); return false; });
  findPythonPath('development');
  assert.equal(visited.length, 8);
  assert.match(visited[0], /backend\/venv\/Scripts\/python.exe$/);
  assert.match(visited[2], /backend\/\.venv\/Scripts\/python.exe$/);
  assert.match(visited[4], /ClaimWise\/\.venv\/Scripts\/python.exe$/);
  assert.match(visited[6], /FinTech\/\.venv\/Scripts\/python.exe$/);
  visited.length = 0;
  findPythonPath('standalone');
  assert.equal(visited.length, 4);
  assert.match(visited[2], /FinTech\/\.venv\/Scripts\/python.exe$/);
});

test('an active virtual environment still wins over project candidates', t => {
  const active = process.env.VIRTUAL_ENV;
  process.env.VIRTUAL_ENV = path.resolve('active-test-environment');
  t.after(() => { if (active === undefined) delete process.env.VIRTUAL_ENV; else process.env.VIRTUAL_ENV = active; });
  t.mock.method(fs, 'existsSync', () => true);
  assert.ok(findPythonPath().startsWith(process.env.VIRTUAL_ENV));
  assert.ok(findPythonPath('standalone').startsWith(process.env.VIRTUAL_ENV));
});
