// Screenshots of the PDF Report Designer (VinAura) for the landing page, taken from the no-login local test copy
// (application 2099). Copied from the Rounds HMS documentation tool; DOCS_SCALE=2 gives retina-size pictures.
//
//   node tools/shots/shoot.mjs <shot list> <output folder> [name filter]
//   DOCS_SCALE=2 node tools/shots/shoot.mjs tools/shots/landing.mjs local/shots
//
// It starts the installed Google Chrome without a window, with a profile of its own in the temp folder
// (never the user's profile), and drives it through the DevTools protocol - nothing is installed.
// A shot list exports an array of shots:
//   { name, page, steps: [...], mark: [...], clip: 'css selector', full: true, keepFocus: true }
// (keepFocus: an open menu or pop-up closes when the field loses the focus before the picture)
// page: the page number (opens f?p=1298:<page>) or a whole URL. steps run in order:
//   { set: 'P11_PNAME', value: 'X' }           apex.item(...).setValue (fires change, as a user would)
//   { type: 'P11_CONTACTNO', text: '98..', press: 'Tab' }   real key strokes into the field (trusted events)
//   { press: 'Enter' }                         a real key press on the field that has the focus
//   { click: 'css selector' }                  clicks the first match
//   { mouse: target }                          a real mouse click in the middle of the target (see mark)
//   { clickText: 'Save', within: 'selector' }  clicks the button / link / cell with this text
//   { key: 'P11_CONTACTNO', code: 'Enter' }    a key press on an item (jQuery keydown, as the page listens)
//   { eval: 'js' }                             anything else, in the page
//   { wait: 800 }                              milliseconds; every step also waits for the page to settle
//   { waitFor: 'css selector' }
// mark: [{ sel | item | region | button | text, n: 1 }] draws an orange frame with the number n around an
// element: a CSS selector, a page item (its label and field), a region by its title, a button by its label,
// or the smallest visible element with this text. clip takes the same kinds of target.
import { spawn } from 'node:child_process';
import { mkdirSync, writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const BASE = process.env.DOCS_BASE || 'http://localhost:8080/ords/f?p=2099:';
const PORT = 9344;
const WIDTH = +(process.env.DOCS_WIDTH || 1440), HEIGHT = +(process.env.DOCS_HEIGHT || 900), SCALE = +(process.env.DOCS_SCALE || 1);

const [listFile, outDir, only] = process.argv.slice(2);
if (!listFile || !outDir) {
  console.error('usage: node tools/docs/shoot.mjs <shot list> <output folder> [name filter]');
  process.exit(1);
}
const shots = (await import(pathToFileURL(resolve(listFile)).href)).default;
mkdirSync(outDir, { recursive: true });

const profile = mkdtempSync(join(tmpdir(), 'vinaura-shots-chrome-'));
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--force-color-profile=srgb',
  '--lang=en-GB', 'about:blank'], { stdio: 'ignore' });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  await sleep(200);
  try {
    const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
    target = list.find((t) => t.type === 'page');
  } catch { /* not up yet */ }
}
if (!target) throw new Error('Chrome did not start');

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((r) => ws.addEventListener('open', r, { once: true }));
let seq = 0;
const pending = new Map();
const listeners = [];
ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { ok, fail } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? fail(new Error(msg.error.message)) : ok(msg.result);
  } else if (msg.method) {
    listeners.forEach((l) => l(msg));
  }
});
const cdp = (method, params = {}) => new Promise((ok, fail) => {
  const id = ++seq;
  pending.set(id, { ok, fail });
  ws.send(JSON.stringify({ id, method, params }));
});
const once = (method, ms = 20000) => new Promise((ok) => {
  const t = setTimeout(ok, ms);
  const l = (m) => { if (m.method === method) { clearTimeout(t); listeners.splice(listeners.indexOf(l), 1); ok(m); } };
  listeners.push(l);
});
const js = async (expression) => {
  const r = await cdp('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || r.exceptionDetails.text);
  return r.result.value;
};
// the page has settled: loaded, no APEX request running, no spinner
const settle = async () => {
  for (let i = 0; i < 60; i++) {
    const busy = await js(`(document.readyState !== 'complete')
      || !!document.querySelector('.u-Processing, .a-GV-loadMore--loading, .apex_wait_overlay')
      || (window.apex && apex.jQuery && apex.jQuery.active > 0)`).catch(() => true);
    if (!busy) return sleep(250);
    await sleep(150);
  }
};

await cdp('Page.enable');
await cdp('Runtime.enable');
await cdp('Emulation.setDeviceMetricsOverride', { width: WIDTH, height: HEIGHT, deviceScaleFactor: SCALE, mobile: false });
await cdp('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-color-scheme', value: 'light' }] });

const MARK_CSS = `.docs-mark{position:absolute;border:3px solid #f28c28;border-radius:6px;pointer-events:none;z-index:99999;
  box-shadow:0 0 0 3px rgba(242,140,40,.18)}
.docs-mark b{position:absolute;top:-13px;left:-13px;width:24px;height:24px;border-radius:12px;background:#f28c28;color:#fff;
  font:700 13px/24px Arial,sans-serif;text-align:center;box-shadow:0 1px 3px rgba(0,0,0,.3)}`;

const FIND = `window.docsFind = (m) => {
  if (typeof m === 'string') m = { sel: m };
  const vis = (e) => e && e.offsetParent !== null;
  if (m.sel) return document.querySelector(m.sel);
  if (m.item) return document.getElementById(m.item + '_CONTAINER') || document.getElementById(m.item);
  if (m.region) return [...document.querySelectorAll('.t-Region, .t-IRR-region, .a-IRR-container, .t-Card, .t-DialogRegion')]
    .find((r) => vis(r) && ((r.querySelector('.t-Region-title, h2') || {}).textContent || '').trim() === m.region);
  if (m.button) return [...document.querySelectorAll('button, a.t-Button')].find((b) => vis(b) && b.textContent.trim() === m.button);
  if (m.text) return [...document.querySelectorAll('body *')].filter((e) => vis(e) && e.textContent.trim() === m.text)
    .sort((a, b) => a.getElementsByTagName('*').length - b.getElementsByTagName('*').length)[0];
};`;

const KEYS = { Tab: 9, Enter: 13, Escape: 27, ArrowDown: 40 };
async function press(key) {
  const k = { key, code: key, windowsVirtualKeyCode: KEYS[key], nativeVirtualKeyCode: KEYS[key] };
  await cdp('Input.dispatchKeyEvent', { type: 'rawKeyDown', ...k });
  await cdp('Input.dispatchKeyEvent', { type: 'keyUp', ...k });
}

async function step(s) {
  // listening before the action: a fast page is loaded before the action returns
  const loaded = s.navigates ? once('Page.loadEventFired') : null;
  if (s.mouse) {
    await js(FIND);
    const c = await js(`(() => { const e = docsFind(${JSON.stringify(s.mouse)});
      if (!e) throw new Error('no element to click: ' + ${JSON.stringify(JSON.stringify(s.mouse))});
      e.scrollIntoView({ block: 'center' }); const r = e.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; })()`);
    for (const type of ['mouseMoved', 'mousePressed', 'mouseReleased']) {
      await cdp('Input.dispatchMouseEvent', { type, x: c.x, y: c.y, button: 'left', clickCount: 1 });
    }
  } else if (s.type) {
    await js(`(() => { let e = document.getElementById(${JSON.stringify(s.type)});
      if (e && !/^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName)) e = e.querySelector('input, textarea');
      if (!e) throw new Error('no field ' + ${JSON.stringify(s.type)}); e.focus(); if (e.select) e.select(); })()`);
    await cdp('Input.insertText', { text: s.text });
    if (s.press) await press(s.press);
  } else if (s.press) {
    await press(s.press);
  } else if (s.set) {
    await js(`apex.item(${JSON.stringify(s.set)}).setValue(${JSON.stringify(s.value)})`);
  } else if (s.click) {
    await js(`(() => { const e = document.querySelector(${JSON.stringify(s.click)});
      if (!e) throw new Error('no element ' + ${JSON.stringify(s.click)}); e.click(); })()`);
  } else if (s.clickText) {
    await js(`(() => { const root = document.querySelector(${JSON.stringify(s.within || 'body')});
      const want = ${JSON.stringify(s.clickText)};
      const e = [...root.querySelectorAll('button, a, [role=button], td, span, li')]
        .find((x) => x.offsetParent !== null && x.textContent.trim() === want);
      if (!e) throw new Error('no element with the text ' + want); e.click(); })()`);
  } else if (s.key) {
    await js(`apex.jQuery('#' + ${JSON.stringify(s.key)}).trigger(apex.jQuery.Event('keydown',
      { key: ${JSON.stringify(s.code)}, which: ${s.code === 'Enter' ? 13 : 9}, keyCode: ${s.code === 'Enter' ? 13 : 9} }))`);
  } else if (s.eval) {
    await js(`void (${s.eval})`);
  } else if (s.waitFor) {
    for (let i = 0; i < 80; i++) {
      if (await js(`!!document.querySelector(${JSON.stringify(s.waitFor)})`)) break;
      await sleep(150);
    }
  }
  if (s.wait) await sleep(s.wait);
  if (loaded) await loaded;
  await settle();
}



async function mark(marks = []) {
  await js(FIND);
  await js(`(() => {
    document.querySelectorAll('.docs-mark').forEach((m) => m.remove());
    if (!document.getElementById('docs-mark-css')) {
      const st = document.createElement('style'); st.id = 'docs-mark-css'; st.textContent = ${JSON.stringify(MARK_CSS)};
      document.head.appendChild(st);
    }
    for (const m of ${JSON.stringify(marks)}) {
      const e = docsFind(m);
      if (!e) throw new Error('no element to mark: ' + JSON.stringify(m));
      const r = e.getBoundingClientRect(), pad = m.pad ?? 4;
      const d = document.createElement('div'); d.className = 'docs-mark';
      d.style.left = (r.left + scrollX - pad) + 'px'; d.style.top = (r.top + scrollY - pad) + 'px';
      d.style.width = (r.width + pad * 2) + 'px'; d.style.height = (r.height + pad * 2) + 'px';
      if (m.n) d.innerHTML = '<b>' + m.n + '</b>';
      document.body.appendChild(d);
    }
  })()`);
}

let failed = 0;
for (const shot of shots) {
  if (only && !shot.name.includes(only)) continue;
  try {
    const url = typeof shot.page === 'number' ? BASE + shot.page : shot.page;
    if (url) {
      const loaded = once('Page.loadEventFired');
      await cdp('Page.navigate', { url });
      await loaded;
      await settle();
    }
    for (const s of shot.steps || []) await step(s);
    // no caret, no focus ring, no tooltips in the picture
    if (!shot.keepFocus) await js(`document.activeElement && document.activeElement.blur(); window.scrollTo(0, 0)`);
    await mark(shot.mark);
    await sleep(200);
    let clip;
    if (shot.clip) {
      await js(FIND);
      clip = await js(`(() => { const e = docsFind(${JSON.stringify(shot.clip)});
        if (!e) throw new Error('no element to clip: ' + ${JSON.stringify(shot.clip)});
        const r = e.getBoundingClientRect(), p = 12;
        return { x: Math.max(r.left + scrollX - p, 0), y: Math.max(r.top + scrollY - p, 0),
                 width: Math.min(r.width + p * 2, document.documentElement.scrollWidth), height: r.height + p * 2, scale: 1 }; })()`);
    } else if (shot.full) {
      const h = await js('Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)');
      clip = { x: 0, y: 0, width: WIDTH, height: Math.min(h, 6000), scale: 1 };
    }
    const png = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: !!clip, ...(clip ? { clip } : {}) });
    writeFileSync(join(outDir, shot.name + '.png'), Buffer.from(png.data, 'base64'));
    const err = await js(`(document.querySelector('#t_Alert_Notification .t-Alert-body, .a-Notification--error, .t-Alert--danger .t-Alert-body') || {}).innerText || ''`);
    console.log(`ok   ${shot.name}${err ? '   (page message: ' + err.trim().slice(0, 120) + ')' : ''}`);
  } catch (e) {
    failed++;
    console.log(`FAIL ${shot.name}: ${e.message}`);
  }
}
ws.close();
chrome.kill();
process.exit(failed ? 1 : 0);
