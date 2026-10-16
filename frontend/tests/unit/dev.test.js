const { test } = require('node:test');
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const { findPythonPath, checkBackendHealth, waitForBackendHealth } = require('../../scripts/dev');

test('importing the runner does not start services; project Python is preferred', (t) => {
  const virtualEnv = process.env.VIRTUAL_ENV;
  delete process.env.VIRTUAL_ENV;
  t.after(() => { if (virtualEnv !== undefined) process.env.VIRTUAL_ENV = virtualEnv; });
  t.mock.method(fs, 'existsSync', () => true);
  assert.match(findPythonPath().replaceAll('\\', '/'), /ClaimWise\/backend\/venv\//);
});

test('stopped or failed backend never waits out the health deadline', async () => {
  const probe = () => { throw new Error('unexpected health request'); };
  assert.equal(await waitForBackendHealth({ exitCode: 1, signalCode: null }, 1000, probe), false);
  assert.equal(await waitForBackendHealth({ exitCode: null, signalCode: null, startupError: new Error('spawn failed') }, 1000, probe), false);
});

test('successful health response releases the frontend immediately', async () => {
  assert.equal(await waitForBackendHealth({ exitCode: null, signalCode: null }, 1000, async () => true), true);
});

test('HTTP health probe distinguishes healthy and failed servers', async (t) => {
  let status = 200;
  const server = http.createServer((request, response) => { response.writeHead(status); response.end('{}'); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const port = server.address().port;
  assert.equal(await checkBackendHealth(port), true);
  status = 503;
  assert.equal(await checkBackendHealth(port), false);
});
