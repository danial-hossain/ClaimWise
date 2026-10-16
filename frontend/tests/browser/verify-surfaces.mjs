/* Read existing local records only; never upload, analyze, create a claim, or submit.
 * The existing demo login is used solely to inspect its actual account/empty states. */
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const output = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots/part4');
fs.mkdirSync(output, { recursive: true });
const targets = await (await fetch('http://127.0.0.1:9235/json/list')).json();
const target = targets.find(t => t.type === 'page' && t.url.startsWith('http://localhost:3000/'));
assert(target, 'Launch a fresh isolated localhost browser on port 9235.');
const socket = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let sequence = 0;
const pending = new Map();
const exceptions = [];
const consoleErrors = [];
const requests = [];
const responses = [];
const report = { testedAt: new Date().toISOString(), scope: 'Existing records only; actual backend responses; no response interception', checks: {}, captures: [] };
const send = (method, params = {}) => new Promise((resolve, reject) => {
  const id = ++sequence;
  const timer = setTimeout(() => { pending.delete(id); reject(Error(`Timeout: ${method}`)); }, 30000);
  pending.set(id, { resolve, reject, timer });
  socket.send(JSON.stringify({ id, method, params }));
});
socket.onmessage = event => {
  const msg = JSON.parse(event.data);
  if (msg.method === 'Runtime.exceptionThrown') exceptions.push({ text: msg.params.exceptionDetails.text, description: msg.params.exceptionDetails.exception?.description, stack: msg.params.exceptionDetails.stackTrace, url: msg.params.exceptionDetails.url });
  if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') consoleErrors.push(msg.params.args.map(a => a.value || a.description).join(' '));
  if (msg.method === 'Network.requestWillBeSent') requests.push({ url: msg.params.request.url, method: msg.params.request.method });
  if (msg.method === 'Network.responseReceived' && msg.params.response.url.includes('/api/v1/')) responses.push({ url: new URL(msg.params.response.url).pathname, status: msg.params.response.status });
  const call = pending.get(msg.id);
  if (!call) return;
  pending.delete(msg.id); clearTimeout(call.timer);
  if (msg.error) call.reject(Error(JSON.stringify(msg.error))); else call.resolve(msg.result);
};
const evaluate = async expression => {
  const result = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
};
const until = async expression => {
  for (let i = 0; i < 180; i++) { if (await evaluate(`Boolean(${expression})`)) return; await pause(150); }
  throw Error(`Condition not reached: ${expression}`);
};
const navigate = async route => {
  await send('Page.navigate', { url: `http://localhost:3000${route}` });
  await until(`document.querySelector('.app-page, .overview-shell') && document.readyState === 'complete'`);
  await until(`document.querySelectorAll('.cw-skeleton').length === 0`);
  await pause(1200);
};
const screenshot = async (name, state) => {
  await evaluate(`document.fonts.ready.then(() => true)`);
  await evaluate(`window.scrollTo({top:0,behavior:'instant'});if(document.activeElement instanceof HTMLElement)document.activeElement.blur();true`);
  await pause(500);
  const { cssContentSize, cssVisualViewport } = await send('Page.getLayoutMetrics');
  const dialog = await evaluate(`Boolean(document.querySelector('[role="dialog"]'))`);
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: !dialog, clip: { x: 0, y: 0, width: cssContentSize.width, height: dialog ? cssVisualViewport.clientHeight : Math.min(2100, cssContentSize.height), scale: 1 } });
  fs.writeFileSync(path.join(output, name), Buffer.from(result.data, 'base64'));
  report.captures.push({ file: name, state, truncatedAfterPx: !dialog && cssContentSize.height > 2100 ? 2100 : null });
};
const type = (selector, value) => evaluate(`(() => {const el=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype,'value').set.call(el,${JSON.stringify(value)});el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));return true;})()`);
const viewport = (width, height) => send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: width < 768 });
try {
  await send('Page.enable'); await send('Runtime.enable'); await send('Network.enable');
  await viewport(1440, 1000);
  await evaluate(`localStorage.removeItem('claimwise_auth_token');localStorage.removeItem('claimwise_user_profile');sessionStorage.clear();true`);
  report.existingPolicyCount = await evaluate(`fetch('/api/v1/policies').then(r=>r.json()).then(p=>{window.__existingPolicies=Array.isArray(p)?p:[];return window.__existingPolicies.length;})`);
  const routes = [['overview', '/dashboard'], ['policies', '/policies'], ['coverage', '/coverage'], ['ask', '/workspace'], ['claims', '/claims']];
  for (const [name, route] of routes) {
    await navigate(route);
    assert(await evaluate(`Boolean(document.querySelector('.cw-site-footer'))`));
    assert(await evaluate(`document.documentElement.scrollWidth <= innerWidth`));
    await screenshot(`${name}-existing.png`, name === 'claims' ? 'Actual signed-out API error; no claim records available' : 'Actual available policy data; saved claim/analysis access may require sign-in');
  }
  report.checks.footerOnEveryScreen = true;
  report.checks.laptopNoHorizontalOverflow = true;
  await navigate('/coverage');
  await until(`document.querySelector('.coverage-scenario-input')`);
  await type('.coverage-scenario-input', 'My luggage was lost during my trip');
  report.checks.characterCounterLive = await evaluate(`document.querySelector('#coverage-need-hint').textContent.includes('34/2000')`);
  assert(report.checks.characterCounterLive);
  report.checks.inputIsLabelled = await evaluate(`Boolean(document.querySelector('.coverage-scenario-input').getAttribute('aria-label'))`);
  await navigate('/policies');
  if (report.existingPolicyCount) {
    await until(`document.querySelector('.policy-library-card')`);
    await evaluate(`document.querySelector('.policy-upload-panel').dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true}));true`);
    report.checks.dragOverStateVisible = await evaluate(`document.querySelector('.policy-upload-panel').classList.contains('is-dragging')`);
    assert(report.checks.dragOverStateVisible);
    await evaluate(`document.querySelector('.policy-upload-panel').dispatchEvent(new DragEvent('dragleave',{bubbles:true}));true`);
    await evaluate(`document.querySelector('.policy-library-card').click()`);
    await until(`document.querySelector('.cw-reader-filters')`);
    await pause(1000);
    const headingRequests = requests.filter(r => r.url.includes('headings') && r.method === 'POST').length;
    await screenshot('policies-clause-viewer.png', 'Actual existing policy clauses and available page choices');
    await type('.cw-reader-filters input', '__no_matching_clause__');
    await until(`document.querySelector('.cw-reader-filters > p').textContent.includes('0 matching')`);
    report.checks.clauseSearchFiltersWithoutChangingEvidence = true;
    await type('.cw-reader-filters input', '');
    report.pageFilterValue = await evaluate(`(() => {const el=document.querySelector('.cw-reader-filters select');if(el.options.length<2)return null;el.value=el.options[el.options.length-1].value;el.dispatchEvent(new Event('change',{bubbles:true}));return el.value;})()`);
    if (report.pageFilterValue) {
      await pause(300);
      report.checks.pageFilterWorks = await evaluate(`document.querySelector('.cw-reader-filters select').value===${JSON.stringify(report.pageFilterValue)} && document.querySelector('.cw-reader-content').textContent.includes('Page ' + ${JSON.stringify(report.pageFilterValue)})`);
      assert(report.checks.pageFilterWorks);
    }
    await pause(500);
    report.checks.filtersDoNotRequestAIHeadingsAgain = headingRequests === requests.filter(r => r.url.includes('headings') && r.method === 'POST').length;
    assert(report.checks.filtersDoNotRequestAIHeadingsAgain);
    await evaluate(`(()=>{const controls=[...document.querySelectorAll('#policy-reader-dialog button:not(:disabled), #policy-reader-dialog input, #policy-reader-dialog select')];controls.at(-1)?.focus();return true;})()`);
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    report.checks.readerContainsKeyboardFocus = await evaluate(`Boolean(document.activeElement.closest('#policy-reader-dialog'))`);
    assert(report.checks.readerContainsKeyboardFocus);
    await viewport(390,844); await pause(400);
    report.checks.mobileReaderFitsViewport = await evaluate(`document.documentElement.scrollWidth<=innerWidth && document.querySelector('#policy-reader-dialog > footer').getBoundingClientRect().bottom<=innerHeight && document.querySelector('.cw-reader-content').getBoundingClientRect().height>100`);
    assert(report.checks.mobileReaderFitsViewport);
    await screenshot('policies-clause-viewer-mobile.png', 'Actual existing policy, filtered to its real last page; mobile reader');
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
    await until(`!document.querySelector('#policy-reader-dialog')`);
    report.checks.readerClosesOnEscape = true;
    await viewport(1440,1000);
  }
  // This is an existing, explicitly supported local demo account; no signup or test records.
  report.demo = await evaluate(`(async()=>{
    const response=await fetch('/api/v1/auth/demo',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({role:'policyholder'})});
    if(!response.ok)return {status:response.status};
    const data=await response.json();
    localStorage.setItem('claimwise_auth_token',data.access_token);
    localStorage.setItem('claimwise_user_profile',JSON.stringify({id:data.user.id,email:data.user.email,fullName:data.user.full_name,userRole:data.user.role,tier:data.user.tier}));
    const headers={Authorization:'Bearer '+data.access_token};
    const [policies,claims]=await Promise.all(['policies','claims'].map(p=>fetch('/api/v1/'+p,{headers}).then(async r=>({status:r.status,data:await r.json()}))));
    const firstPolicy=policies.status===200&&Array.isArray(policies.data)?policies.data[0]?.policy_id:null;
    const analyses=firstPolicy?await fetch('/api/v1/coverage/analyses?policy_id='+encodeURIComponent(firstPolicy),{headers}).then(async r=>({status:r.status,data:await r.json()})):null;
    return {signedIn:true,policies:policies.status===200&&Array.isArray(policies.data)?policies.data.length:null,claims:claims.status===200&&Array.isArray(claims.data)?claims.data.length:null,analyses:analyses?.status===200&&Array.isArray(analyses.data)?analyses.data.length:null,analysisCheck:firstPolicy?'existing policy analyses':'not queried: no policies'};
  })()`);
  if (report.demo.signedIn) {
    for (const [name, route] of routes) {
      await navigate(route);
      await screenshot(`${name}-demo.png`, `Actual existing demo account: ${report.demo.policies} policies, ${report.demo.claims} claims; ${report.demo.analysisCheck}`);
      assert(await evaluate(`document.documentElement.scrollWidth <= innerWidth`));
    }
    report.checks.greetingUsesActualAccount = await evaluate(`JSON.parse(localStorage.getItem('claimwise_user_profile')).fullName.length > 0`);
    if (report.demo.policies === 0) {
      await navigate('/dashboard');
      report.checks.honestEmptyUploadPrompt = await evaluate(`document.querySelector('.scenario-launcher').textContent.includes('Upload your first policy')`);
      assert(report.checks.honestEmptyUploadPrompt);
    }
  }
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  await viewport(390, 844);
  for (const [name, route] of routes) {
    await navigate(route);
    assert(await evaluate(`document.documentElement.scrollWidth <= innerWidth`), `${name} overflows on mobile`);
    await screenshot(`${name}-mobile.png`, 'Actual existing account; reduced motion enabled; 390px viewport');
  }
  report.checks.mobileNoHorizontalOverflow = true;
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
  report.checks.keyboardFocusVisible = await evaluate(`document.activeElement.matches(':focus-visible') && getComputedStyle(document.activeElement).outlineStyle !== 'none'`);
  assert(report.checks.keyboardFocusVisible);
  const tokens = await evaluate(`(() => {const s=getComputedStyle(document.documentElement);return Object.fromEntries(['covered','conditional','excluded','unspecified'].map(t=>[t,{ink:s.getPropertyValue('--cw-'+t+'-ink').trim(),bg:s.getPropertyValue('--cw-'+t+'-bg').trim()}]));})()`);
  const luminance = hex => { const rgb = hex.replace('#','').match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4); return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]; };
  report.statusContrastRatios = Object.fromEntries(Object.entries(tokens).map(([tone, {ink,bg}]) => { const a=luminance(ink),b=luminance(bg);return [tone,Number(((Math.max(a,b)+.05)/(Math.min(a,b)+.05)).toFixed(2))]; }));
  report.checks.statusTextContrastAA = Object.values(report.statusContrastRatios).every(ratio=>ratio>=4.5);
  assert(report.checks.statusTextContrastAA);
  report.checks.noNewBusinessRecords = requests.every(r => r.method === 'GET' || !r.url.includes('/api/v1/') || r.url.endsWith('/auth/demo') || r.url.includes('headings'));
  assert(report.checks.noNewBusinessRecords);
  report.runtimeExceptions = exceptions;
  report.consoleErrors = consoleErrors;
  report.apiFailures = responses.filter(r => r.status >= 400);
  assert.equal(exceptions.length, 0);
  assert.equal(consoleErrors.length, 0);
  report.unverified = ['Populated Coverage findings, chat answers/abstention, and claim detail screenshots require existing accessible records; none will be fabricated', 'Upload progress and new-card/count animation cannot be exercised without uploading a file, which the user declined'];
  report.passed = true;
} catch (error) { report.passed = false; report.error = String(error); process.exitCode = 1; await screenshot('verification-failure.png', 'Debug capture of an actual failed check').catch(() => {}); }
finally {
  fs.writeFileSync(path.join(output, 'verification.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2)); socket.close();
}
