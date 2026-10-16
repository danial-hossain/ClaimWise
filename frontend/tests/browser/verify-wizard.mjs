/* UI-only smoke test against a fresh local headless Chrome on port 9235.
 * Uses existing policy records, never mocks analysis/claims or submits a claim. */
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
(async () => {
  const targets = await (await fetch('http://127.0.0.1:9235/json/list')).json();
  const target = targets.find(item => item.type === 'page' && item.url.startsWith('http://localhost:3000/claims/new'));
  assert(target, 'Start a fresh, isolated local preview browser first.');
  const socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let sequence = 0;
  const pending = new Map();
  const exceptions = [];
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails.text);
    const call = pending.get(message.id);
    if (!call) return;
    pending.delete(message.id); clearTimeout(call.timer);
    if (message.error) call.reject(Error(JSON.stringify(message.error)));
    else call.resolve(message.result);
  };
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(Error(`Timeout: ${method}`)); }, 25000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async expression => {
    const response = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (response.exceptionDetails) throw Error(JSON.stringify(response.exceptionDetails));
    return response.result.value;
  };
  const until = async expression => {
    for (let attempt = 0; attempt < 120; attempt++) {
      if (await evaluate(`Boolean(${expression})`)) return;
      await delay(150);
    }
    throw Error(`Condition not reached: ${expression}`);
  };
  const ready = step => until(`document.querySelector('[data-wizard-step="${step}"]') && getComputedStyle(document.querySelector('[data-step-transition]')).opacity === '1'`);
  const output = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../../../docs/screenshots');
  const screenshot = async name => {
    await evaluate('document.fonts.ready.then(() => true)');
    await delay(700);
    await evaluate('window.scrollTo(0,0)');
    const metrics = await send('Page.getLayoutMetrics');
    const image = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: metrics.cssContentSize.width, height: metrics.cssContentSize.height, scale: 1 } });
    fs.writeFileSync(path.join(output, name), Buffer.from(image.data, 'base64'));
  };
  const enterText = (selector, value) => evaluate(`(() => { const input=document.querySelector(${JSON.stringify(selector)}); const prototype=input.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:HTMLInputElement.prototype; Object.getOwnPropertyDescriptor(prototype,'value').set.call(input,${JSON.stringify(value)}); input.dispatchEvent(new Event('input',{bubbles:true})); })()`);
  const report = {};
  try {
    await send('Runtime.enable'); await send('Page.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: 'http://localhost:3000/claims/new?step=policy' });
    await ready('policy');
    await until('document.querySelectorAll("#wizard-policy-select option").length > 1');
    report.futureStepsLocked = await evaluate('[...document.querySelectorAll(".wizard-steps .is-future")].length === 3 && [...document.querySelectorAll(".wizard-steps .is-future")].every(e=>e.disabled && e.tagName==="BUTTON")');
    assert(report.futureStepsLocked);
    // Select an actual option returned by the existing policy API.
    report.policyId = await evaluate(`(() => { const input=document.querySelector('#wizard-policy-select'); const option=[...input.options].find(item=>item.value); Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set.call(input,option.value); input.dispatchEvent(new Event('change',{bubbles:true})); return option.value; })()`);
    await until('!document.querySelector("[data-wizard-primary-action]").disabled');
    await screenshot('wizard-1-policy.png');
    await evaluate(`window.__topbar=document.querySelector('.cw-header'); window.__stepper=document.querySelector('.wizard-stepper'); window.__samples=[]; window.__sampling=true; function sample(){ if(!window.__sampling)return; const panels=[...document.querySelectorAll('[data-step-transition]')]; window.__samples.push(panels.map(p=>({step:Number(p.dataset.stepTransition),x:new DOMMatrixReadOnly(getComputedStyle(p).transform).m41,opacity:Number(getComputedStyle(p).opacity)}))); requestAnimationFrame(sample); } requestAnimationFrame(sample); document.querySelector('[data-wizard-primary-action]').click();`);
    await ready('analysis');
    await until('document.querySelector("#wizard-analysis-form textarea") && !document.querySelector("#wizard-analysis-form textarea").disabled');
    report.forwardTransition = await evaluate(`(() => { window.__sampling=false; return {exitLeft:__samples.some(p=>p.some(x=>x.step===0&&x.x<-.1)),enterRight:__samples.some(p=>p.some(x=>x.step===1&&x.x>.1)),onePanelAtATime:__samples.every(p=>p.length<=1),staticChrome:__topbar===document.querySelector('.cw-header')&&__stepper===document.querySelector('.wizard-stepper')}; })()`);
    assert(report.forwardTransition.exitLeft && report.forwardTransition.enterRight && report.forwardTransition.onePanelAtATime && report.forwardTransition.staticChrome);
    // User-provided example; it is an unsent form input, never an invented analysis.
    const incident = 'My luggage was lost during my trip';
    await enterText('#wizard-analysis-form textarea', incident);
    await until(`document.querySelector('#wizard-analysis-form textarea').value === ${JSON.stringify(incident)}`);
    await until(`JSON.parse(sessionStorage.getItem('claimwise_journey:guest') || '{}').incidentDraft === ${JSON.stringify(incident)}`);
    await send('Page.reload'); await ready('analysis');
    await until(`document.querySelector('#wizard-analysis-form textarea')?.value === ${JSON.stringify(incident)}`);
    report.refreshRestoresScenario = await evaluate(`JSON.parse(sessionStorage.getItem('claimwise_journey:guest')).incidentDraft === ${JSON.stringify(incident)} && new URLSearchParams(location.search).get('policy_id') === ${JSON.stringify(report.policyId)}`);
    assert(report.refreshRestoresScenario);
    await screenshot('wizard-2-analysis.png');
    const history = await send('Page.getNavigationHistory');
    await send('Page.navigateToHistoryEntry', { entryId: history.entries[history.currentIndex - 1].id });
    await ready('policy');
    report.browserBack = await evaluate('new URLSearchParams(location.search).get("step")==="policy"');
    assert(report.browserBack);
    await until('!document.querySelector("[data-wizard-primary-action]").disabled');
    await evaluate('document.querySelector("[data-wizard-primary-action]").click()');
    await ready('analysis');
    await evaluate(`window.__samples=[]; window.__sampling=true; function sampleBack(){if(!window.__sampling)return;__samples.push([...document.querySelectorAll('[data-step-transition]')].map(p=>({step:Number(p.dataset.stepTransition),x:new DOMMatrixReadOnly(getComputedStyle(p).transform).m41})));requestAnimationFrame(sampleBack);}requestAnimationFrame(sampleBack);document.querySelector('.wizard-back').click();`);
    await ready('policy');
    report.footerBack = await evaluate('new URLSearchParams(location.search).get("step")==="policy"');
    report.backwardTransition = await evaluate(`(() => { __sampling=false; return {exitRight:__samples.some(p=>p.some(x=>x.step===1&&x.x>.1)),enterLeft:__samples.some(p=>p.some(x=>x.step===0&&x.x<-.1))}; })()`);
    assert(report.footerBack && report.backwardTransition.exitRight && report.backwardTransition.enterLeft);
    // Direct URLs exercise honest empty guidance/draft screens without bypassing a stepper lock.
    await send('Page.navigate', { url: `http://localhost:3000/claims/new?step=guidance&policy_id=${encodeURIComponent(report.policyId)}` });
    await ready('guidance');
    await until('document.querySelector(".workspace-page input[type=text]") && !document.querySelector(".workspace-page input[type=text]").disabled');
    const question = 'What policy conditions should I check?';
    await enterText('.workspace-page input[type=text]', question);
    await send('Page.reload'); await ready('guidance');
    await until(`document.querySelector('.workspace-page input[type=text]')?.value === ${JSON.stringify(question)}`);
    report.refreshRestoresQuestion = true;
    report.guidanceRequiresAnalysis = await evaluate('document.querySelector("[data-wizard-primary-action]").disabled');
    assert(report.guidanceRequiresAnalysis);
    await screenshot('wizard-3-guidance.png');
    await send('Page.navigate', { url: `http://localhost:3000/claims/new?step=draft&policy_id=${encodeURIComponent(report.policyId)}` });
    await ready('draft');
    await until('document.querySelector("#wizard-claim-form textarea") && !document.querySelector("[data-wizard-primary-action]").disabled');
    report.draftNativeValidation = await evaluate('document.querySelector("[data-wizard-primary-action]").form === document.querySelector("#wizard-claim-form") && !document.querySelector("#wizard-claim-form").checkValidity()');
    assert(report.draftNativeValidation);
    await enterText('#wizard-claim-form textarea', incident);
    await send('Page.reload'); await ready('draft');
    await until(`document.querySelector('#wizard-claim-form textarea')?.value === ${JSON.stringify(incident)}`);
    report.refreshRestoresDraft = true;
    await screenshot('wizard-4-draft.png');
    await evaluate('document.querySelector(".cw-nav a[href^=\\"/claims\\"]").click()');
    await until('location.pathname==="/claims" && document.querySelector("[data-wizard-resume]")');
    await evaluate('document.querySelector("[data-wizard-resume]").click()');
    await ready('draft');
    await until(`document.querySelector('#wizard-claim-form textarea')?.value === ${JSON.stringify(incident)}`);
    report.resumeFromMyClaims = true;
    report.desktopNoOverflow = await evaluate('document.documentElement.scrollWidth<=innerWidth');
    assert(report.desktopNoOverflow);
    await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true, screenWidth: 390, screenHeight: 844 });
    report.mobile = await evaluate(`({noOverflow:innerWidth===document.documentElement.scrollWidth,collapsed:getComputedStyle(document.querySelector('.wizard-steps')).display==='none',counter:document.querySelector('.wizard-mobile-progress').innerText,sticky:getComputedStyle(document.querySelector('.wizard-stepper')).position})`);
    assert(report.mobile.noOverflow && report.mobile.collapsed && report.mobile.sticky==='sticky');
    await screenshot('wizard-mobile.png');
    await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
    await evaluate('document.querySelector(".wizard-back").click()');
    await ready('guidance');
    report.reducedMotion = await evaluate('new DOMMatrixReadOnly(getComputedStyle(document.querySelector("[data-step-transition]")).transform).m41===0 && getComputedStyle(document.querySelector(".wizard-mobile-track span")).transitionDuration==="0s"');
    assert(report.reducedMotion);
    await evaluate('document.querySelector(".wizard-scenario button").click()');
    await ready('policy');
    await until('document.querySelector("#wizard-policy-select") && document.querySelector("#wizard-policy-select").value === ""');
    report.newScenarioResets = await evaluate('document.querySelector("[data-wizard-primary-action]").disabled && [...document.querySelectorAll(".wizard-steps .is-future")].length===3');
    assert(report.newScenarioResets);
    report.runtimeExceptions = exceptions;
    assert.deepEqual(exceptions, []);
    report.backendWrites = 'None: no analysis generation, question submission, claim save, or insurer submission was triggered.';
    report.unverified = 'Authenticated saved-analysis restoration and claim saving require a signed-in session. Guidance/draft screenshots show real empty/authorization states.';
    fs.writeFileSync(path.join(output, 'wizard-verification.json'), JSON.stringify(report, null, 2)+'\n');
    console.log(JSON.stringify(report, null, 2));
  } finally { await send('Browser.close').catch(() => {}); socket.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
