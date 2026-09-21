/*
 * PDF Report Designer for Oracle APEX - the designer page.
 *
 * Queries (Q1..Q10) on the left, the page with its bands in the middle, the properties of what is
 * selected on the right. The layout is kept as JSON (points, from the top-left of each band) and saved
 * with the queries through the application processes of the designer app.
 */
/* global apex */
window.pdfd = (function ($) {
  'use strict';

  var PT = { mm: 72 / 25.4, in: 72, pt: 1 };
  var SIZES = {
    A3: [841.89, 1190.55], A4: [595.28, 841.89], A5: [419.53, 595.28], A6: [297.64, 419.53],
    B5: [498.9, 708.66], Letter: [612, 792], Legal: [612, 1008], Tabloid: [792, 1224],
    Executive: [522, 756], 'Envelope DL': [311.81, 623.62], 'Envelope #10': [297, 684]
  };
  var REPORT_BANDS = [
    ['pageHeader', 'Page Header', 'Printed at the top of every page (logo, company, document title).'],
    ['reportHeader', 'Report Header', 'Printed once, at the start of the report (bill-to and invoice boxes).'],
    ['body', 'Body', 'Flows: its tables grow and continue on the next pages; whatever is below a table moves down with it.'],
    ['summary', 'Summary', 'Printed once after the body (totals, amount in words, signature).'],
    ['pageFooter', 'Page Footer', 'Printed at the bottom of every page (page numbers, terms).']
  ];
  var LABEL_BANDS = [['label', 'Label', 'One label. It is repeated for every row of the labels query, across then down.']];
  var FONTS = {
    helvetica: 'Helvetica, Arial, sans-serif',
    arial: 'Arial, Helvetica, sans-serif',
    arialnarrow: '"Arial Narrow", "Helvetica Neue Condensed", Arial, sans-serif',
    arialblack: '"Arial Black", "Helvetica Neue", Arial, sans-serif',
    times: '"Times New Roman", Times, serif',
    courier: '"Courier New", Courier, monospace'
  };
  // the fonts of the PDF (the Arial ones are look-alikes made from Helvetica: no font files needed)
  var FONT_OPTIONS = [['helvetica', 'Helvetica'], ['arial', 'Arial'], ['arialnarrow', 'Arial Narrow'],
    ['arialblack', 'Arial Black'], ['times', 'Times'], ['courier', 'Courier']];
  var MASKS = ['FM999G999G990D00', 'FM999G999G990', 'FM990D00', 'FM990D0', 'DD-MON-YYYY', 'DD-Mon-YYYY',
    'DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD', 'DD-MON-YYYY HH24:MI', 'fmMonth DD, YYYY'];
  // type, name, icon, what it is for (shown on hover)
  var PALETTE = [
    ['text', 'Text / Field', 'fa-font',
     'Fixed text, a field of a query, or both: "Invoice No.", {Q1.INVOICE_NO}, "Invoice No. {Q1.INVOICE_NO}". Fonts, colours, alignment, border and background.'],
    ['box', 'Box', 'fa-square-o', 'A rectangle: a frame or a coloured background behind other elements.'],
    ['rbox', 'Rounded box', 'fa-square-o pdfd-rounded-ico', 'A rectangle with rounded corners.'],
    ['ellipse', 'Circle / ellipse', 'fa-circle-o', 'A circle or an ellipse, e.g. a PAID stamp.'],
    ['hline', 'Horizontal line', 'fa-minus', 'A horizontal line: a separator or an underline.'],
    ['vline', 'Vertical line', 'fa-minus fa-rotate-90', 'A vertical line.'],
    ['image', 'Image', 'fa-image', 'A logo, a stamp or a signature you upload, or an image from a BLOB column.'],
    ['table', 'Table', 'fa-table', 'The rows of a query (e.g. the lines of an invoice): columns, totals, groups. It continues on the next pages.'],
    ['barcode', 'Barcode', 'fa-barcode', 'A Code 128 barcode of fixed text or a field, e.g. {Q1.SKU}.']
  ];

  var S = null;          // the state of the designer
  var root = null;       // the designer element
  var els = {};          // parts of the page: canvas, left, props, ...
  var imageCache = {};   // image name -> data URL

  // ------------------------------------------------------------------ small helpers
  function h(tag, attrs, kids) {
    var e = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        var v = attrs[k];
        if (v === null || v === undefined || v === false) { return; }
        if (k === 'class') { e.className = v; }
        else if (k === 'text') { e.textContent = v; }
        else if (k === 'html') { e.innerHTML = v; }
        else if (k === 'style' && typeof v === 'object') { Object.assign(e.style, v); }
        else if (k.slice(0, 2) === 'on' && typeof v === 'function') { e.addEventListener(k.slice(2), v); }
        else { e.setAttribute(k, v === true ? '' : v); }
      });
    }
    (kids || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) { return; }
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    });
    return e;
  }
  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function clone(o) { return JSON.parse(JSON.stringify(o)); }
  function round(v, d) { var f = Math.pow(10, d === undefined ? 2 : d); return Math.round(v * f) / f; }
  function num(v, d) { var n = parseFloat(v); return isNaN(n) ? d : n; }
  function icon(cls) { return h('span', { class: 'fa ' + cls, 'aria-hidden': 'true' }); }

  function unit() { return (S.layout.page && S.layout.page.unit) || 'mm'; }
  function toUnit(pt) { return round(pt / PT[unit()], unit() === 'pt' ? 1 : 2); }
  function fromUnit(v) { return num(v, 0) * PT[unit()]; }

  function snap(v) {
    if (!S.snap) { return round(v, 1); }
    return round(Math.round(v / S.grid) * S.grid, 2);
  }

  function ajax(name, data) {
    return apex.server.process(name, data, { dataType: 'json' }).then(function (r) {
      if (r && r.problem) { return $.Deferred().reject(r.problem).promise(); }
      return r;
    }, function (xhr, status, err) {
      return $.Deferred().reject((xhr && xhr.responseText && xhr.responseText.slice(0, 300)) || err || status).promise();
    });
  }

  function toast(msg, isError) {
    var t = h('div', { class: 'pdfd-toast' + (isError ? ' is-error' : ''), role: isError ? 'alert' : 'status' }, [msg]);
    root.appendChild(t);
    setTimeout(function () { t.classList.add('is-gone'); }, isError ? 6000 : 2500);
    setTimeout(function () { t.remove(); }, isError ? 6600 : 3100);
  }

  // ------------------------------------------------------------------ layout model
  function bandDefs() { return S.layout.type === 'labels' ? LABEL_BANDS : REPORT_BANDS; }
  function band(name) { return S.layout.bands[name]; }
  function contentWidth() {
    if (S.layout.type === 'labels') { return S.layout.labels.width; }
    var p = S.layout.page;
    return p.width - p.margin.left - p.margin.right;
  }

  function normalize(l) {
    l = l || {};
    l.version = 1;
    l.type = l.type === 'labels' ? 'labels' : 'report';
    l.repeat = l.repeat || '';
    l.page = l.page || {};
    var p = l.page;
    p.size = p.size || 'A4';
    p.orientation = p.orientation || 'portrait';
    if (!p.width || !p.height) {
      var sz = SIZES[p.size] || SIZES.A4;
      p.width = p.orientation === 'landscape' ? sz[1] : sz[0];
      p.height = p.orientation === 'landscape' ? sz[0] : sz[1];
    }
    p.unit = p.unit || 'mm';
    p.margin = p.margin || {};
    ['top', 'right', 'bottom', 'left'].forEach(function (k) { if (p.margin[k] === undefined) { p.margin[k] = 28.35; } });
    l.font = l.font || { family: 'helvetica', size: 9, color: '#000000' };
    l.params = l.params || {};
    l.bands = l.bands || {};
    if (l.type === 'labels') {
      l.labels = l.labels || { query: 'Q1', across: 3, down: 8, width: 180, height: 96, gapX: 7, gapY: 0, outline: true };
    }
    (l.type === 'labels' ? LABEL_BANDS : REPORT_BANDS).forEach(function (b) {
      var bd = l.bands[b[0]] = l.bands[b[0]] || {};
      if (bd.height === undefined) { bd.height = b[0] === 'body' ? 120 : (b[0] === 'reportHeader' ? 0 : 60); }
      bd.elements = bd.elements || [];
      if (b[0] === 'pageHeader' || b[0] === 'pageFooter') { bd.printOn = bd.printOn || 'all'; }
    });
    if (l.type === 'labels') { l.bands.label.height = l.labels.height; }
    return l;
  }

  function allElements() {
    var out = [];
    bandDefs().forEach(function (b) {
      band(b[0]).elements.forEach(function (e) { out.push({ el: e, band: b[0] }); });
    });
    return out;
  }
  function find(id) {
    var all = allElements();
    for (var i = 0; i < all.length; i++) { if (all[i].el.id === id) { return all[i]; } }
    return null;
  }
  function selected() {
    return S.sel.map(find).filter(Boolean);
  }
  function newId() {
    var max = 0;
    allElements().forEach(function (x) { var n = parseInt(String(x.el.id).replace(/\D/g, ''), 10); if (n > max) { max = n; } });
    return 'e' + (max + 1);
  }

  function tableHeight(t) {
    var size = t.size || S.layout.font.size || 9;
    var pad = t.padding === undefined ? 3 : t.padding;
    var rowH = t.rowHeight || round(size * 1.2 + 2 * pad, 1);
    var hdr = t.header || {};
    var hh = hdr.show === false ? 0 : (hdr.height || rowH);
    var tot = (t.columns || []).some(function (c) { return c.total; }) && !(t.totals && t.totals.show === false);
    return round(hh + rowH * 2 + (tot ? rowH : 0), 1);
  }

  // ------------------------------------------------------------------ undo / redo / dirty
  function snapshot() { return JSON.stringify({ layout: S.layout, queries: S.queries }); }
  function checkpoint() {
    var s = snapshot();
    if (S.undo.length && S.undo[S.undo.length - 1] === s) { return; }
    S.undo.push(s);
    if (S.undo.length > 150) { S.undo.shift(); }
    S.redo = [];
  }
  function restore(s) {
    var o = JSON.parse(s);
    S.layout = o.layout;
    S.queries = o.queries;
    S.sel = S.sel.filter(function (id) { return !!find(id); });
    setDirty();
    renderAll();
  }
  function undo() {
    if (!S.undo.length) { return; }
    S.redo.push(snapshot());
    restore(S.undo.pop());
  }
  function redo() {
    if (!S.redo.length) { return; }
    S.undo.push(snapshot());
    restore(S.redo.pop());
  }
  function setDirty(v) {
    S.dirty = v !== false;
    if (els.saveBtn) { els.saveBtn.classList.toggle('is-dirty', S.dirty); }
    if (els.status) { els.status.textContent = S.dirty ? 'Not saved' : (S.savedAt ? 'Saved ' + S.savedAt : ''); }
  }

  // ------------------------------------------------------------------ shell
  function buildShell() {
    root.innerHTML = '';
    root.classList.add('pdfd');

    var tb = h('div', { class: 'pdfd-toolbar', role: 'toolbar', 'aria-label': 'Designer toolbar' });
    els.title = h('div', { class: 'pdfd-title' });
    tb.appendChild(h('a', { class: 'pdfd-btn pdfd-btn--quiet', href: S.opts.listUrl || '#', 'data-tip': 'Back to the reports|Unsaved changes are asked about first.', 'aria-label': 'Back to the reports' }, [icon('fa-chevron-left')]));
    tb.appendChild(els.title);
    els.saveBtn = tbtn('fa-save', 'Save', save, 'Save|Saves the layout and the queries (Ctrl+S).', 'pdfd-btn--hot');
    tb.appendChild(els.saveBtn);
    tb.appendChild(tbtn('fa-file-pdf-o', 'Preview', preview, 'Preview|Makes the PDF with the test values of the Parameters tab; nothing needs saving first (Ctrl+P).'));
    tb.appendChild(tbtn('fa-file-o', 'Page', pageSetup, 'Page setup|Page size (A4, Letter, custom ...), portrait or landscape, margins; for labels the label size.'));
    tb.appendChild(sep());
    tb.appendChild(tbtn('fa-undo', null, undo, 'Undo|Ctrl+Z'));
    tb.appendChild(tbtn('fa-repeat', null, redo, 'Redo|Ctrl+Y'));
    tb.appendChild(sep());
    var pal = h('div', { class: 'pdfd-palette', role: 'group', 'aria-label': 'Add an element' });
    pal.appendChild(h('span', { class: 'pdfd-tb-caption', text: 'Add', 'aria-hidden': 'true' }));
    PALETTE.forEach(function (p) {
      var b = tbtn(p[2], null, function () { addElement(p[0]); }, p[1] + '|' + p[3] + ' Click: add it to the selected band. Or drag it onto a band.');
      b.setAttribute('draggable', 'true');
      b.addEventListener('dragstart', function (ev) {
        ev.dataTransfer.setData('text/plain', JSON.stringify({ kind: 'new', type: p[0] }));
        ev.dataTransfer.effectAllowed = 'copy';
      });
      pal.appendChild(b);
    });
    tb.appendChild(pal);
    tb.appendChild(sep());
    var al = h('div', { class: 'pdfd-align', role: 'group', 'aria-label': 'Align' });
    [['left', 'fa-align-left', 'Align left edges'], ['center', 'fa-align-center', 'Align centres'],
      ['right', 'fa-align-right', 'Align right edges'], ['top', 'fa-long-arrow-up', 'Align top edges'],
      ['middle', 'fa-arrows-v', 'Align middles'], ['bottom', 'fa-long-arrow-down', 'Align bottom edges'],
      ['width', 'fa-arrows-h', 'Same width'], ['height', 'fa-text-height', 'Same height']
    ].forEach(function (a) {
      al.appendChild(tbtn(a[1], null, function () { align(a[0]); }, a[2] + '|Select two or more elements first (Shift+click); ' +
        (a[0] === 'width' || a[0] === 'height' ? 'they take the size of the first one.' : 'they line up with each other.')));
    });
    tb.appendChild(al);
    tb.appendChild(sep());
    tb.appendChild(tbtn('fa-clone', null, duplicate, 'Duplicate|A copy of the selected elements (Ctrl+D).'));
    tb.appendChild(tbtn('fa-trash-o', null, removeSelected, 'Delete|Removes the selected elements (Del).'));
    tb.appendChild(h('span', { class: 'pdfd-spacer' }));
    els.status = h('span', { class: 'pdfd-status', 'aria-live': 'polite' });
    tb.appendChild(els.status);
    tb.appendChild(tbtn('fa-search-minus', null, function () { zoom(-0.1); }, 'Zoom out'));
    els.zoom = h('button', { type: 'button', class: 'pdfd-btn pdfd-zoom', 'data-tip': 'Zoom to 100%', 'aria-label': 'Zoom to 100%', onclick: function () { S.zoom = 1; renderCanvas(); updateZoom(); } });
    tb.appendChild(els.zoom);
    tb.appendChild(tbtn('fa-search-plus', null, function () { zoom(0.1); }, 'Zoom in'));
    els.snapBtn = tbtn('fa-th', null, function () { S.snap = !S.snap; els.snapBtn.classList.toggle('is-on', S.snap); renderCanvas(); }, 'Snap to grid|Elements move and resize in steps of 5 pt. Click to turn it on or off.');
    els.snapBtn.classList.toggle('is-on', S.snap);
    tb.appendChild(els.snapBtn);

    var main = h('div', { class: 'pdfd-main' });
    els.left = h('aside', { class: 'pdfd-left', 'aria-label': 'Queries and fields' });
    els.scroll = h('div', { class: 'pdfd-scroll' });
    els.canvas = h('div', { class: 'pdfd-canvas' });
    els.scroll.appendChild(els.canvas);
    els.props = h('aside', { class: 'pdfd-props', 'aria-label': 'Properties' });
    main.appendChild(els.left);
    main.appendChild(els.scroll);
    main.appendChild(els.props);
    root.appendChild(tb);
    root.appendChild(main);

    els.scroll.addEventListener('mousedown', function (ev) {
      if (ev.target === els.scroll || ev.target === els.canvas) { select([]); }
    });
  }

  // tip: 'Name' or 'Name|what it does' - shown at once on hover and on keyboard focus (see showTip)
  function tbtn(ic, label, fn, tip, extra) {
    var t = tip || label;
    return h('button', { type: 'button', class: 'pdfd-btn' + (extra ? ' ' + extra : ''), 'data-tip': t,
      'aria-label': t.replace('|', ': '), onclick: fn },
      [icon(ic), label ? h('span', { class: 'pdfd-btn-label', text: label }) : null]);
  }

  // the tooltip of the toolbar: one element, placed under the button the mouse or the keyboard is on
  function bindTips() {
    var tip = h('div', { class: 'pdfd-tip', role: 'tooltip', 'aria-hidden': 'true' });
    root.appendChild(tip);
    function show(ev) {
      var b = ev.target.closest && ev.target.closest('[data-tip]');
      if (!b || !root.contains(b)) { return; }
      var parts = b.getAttribute('data-tip').split('|');
      tip.innerHTML = '';
      tip.appendChild(h('strong', { text: parts[0] }));
      if (parts[1]) { tip.appendChild(h('span', { text: parts[1] })); }
      var r = b.getBoundingClientRect();
      tip.classList.add('is-on');
      var left = Math.min(Math.max(8, r.left + r.width / 2 - tip.offsetWidth / 2), window.innerWidth - tip.offsetWidth - 8);
      tip.style.left = left + 'px';
      tip.style.top = (r.bottom + 6) + 'px';
    }
    function hide(ev) {
      var b = ev.target.closest && ev.target.closest('[data-tip]');
      if (b && ev.relatedTarget && b.contains(ev.relatedTarget)) { return; }
      tip.classList.remove('is-on');
    }
    root.addEventListener('mouseover', show);
    root.addEventListener('mouseout', hide);
    root.addEventListener('focusin', show);
    root.addEventListener('focusout', hide);
    root.addEventListener('mousedown', function () { tip.classList.remove('is-on'); });
  }
  function sep() { return h('span', { class: 'pdfd-sep', 'aria-hidden': 'true' }); }

  function updateZoom() { els.zoom.textContent = Math.round(S.zoom * 100) + '%'; }
  function zoom(d) {
    S.zoom = Math.min(3, Math.max(0.4, round(S.zoom + d, 1)));
    updateZoom();
    renderCanvas();
  }

  function renderAll() {
    els.title.innerHTML = '';
    els.title.appendChild(h('strong', { text: S.name }));
    els.title.appendChild(h('span', { class: 'pdfd-code', text: S.code }));
    renderLeft();
    renderCanvas();
    renderProps();
    updateZoom();
  }

  // ------------------------------------------------------------------ left: queries, fields, parameters
  function renderLeft() {
    var tabs = [['queries', 'Queries'], ['fields', 'Fields'], ['params', 'Parameters']];
    els.left.innerHTML = '';
    var bar = h('div', { class: 'pdfd-tabs', role: 'tablist' });
    tabs.forEach(function (t) {
      bar.appendChild(h('button', {
        type: 'button', role: 'tab', class: 'pdfd-tab' + (S.tab === t[0] ? ' is-active' : ''),
        'aria-selected': S.tab === t[0] ? 'true' : 'false',
        onclick: function () { S.tab = t[0]; renderLeft(); }
      }, [t[1]]));
    });
    els.left.appendChild(bar);
    var body = h('div', { class: 'pdfd-tabbody', role: 'tabpanel' });
    els.left.appendChild(body);
    if (S.tab === 'queries') { renderQueries(body); }
    else if (S.tab === 'fields') { renderFields(body); }
    else { renderParams(body); }
  }

  function renderQueries(body) {
    body.appendChild(h('p', { class: 'pdfd-hint', text: 'Write a SELECT for every part of the document. Page items (:P11_INVOICE_ID) are bind variables: they take the values of the page that prints.' }));
    S.qstatus = {};
    S.queries.forEach(function (q, idx) {
      var status = h('div', { class: 'pdfd-qstatus', 'aria-live': 'polite' });
      S.qstatus[q.alias] = status;
      showStatus(q.alias);
      var ta = h('textarea', { class: 'pdfd-sql', spellcheck: 'false', rows: 7, 'aria-label': q.alias + ' SQL' });
      ta.value = q.sql || '';
      ta.addEventListener('focus', checkpoint);
      ta.addEventListener('input', function () { q.sql = ta.value; setDirty(); });
      ta.addEventListener('change', function () { describe(q); });
      ta.addEventListener('keydown', function (ev) {
        if (ev.key === 'Tab') {
          ev.preventDefault();
          var s = ta.selectionStart;
          ta.value = ta.value.slice(0, s) + '  ' + ta.value.slice(ta.selectionEnd);
          ta.selectionStart = ta.selectionEnd = s + 2;
          q.sql = ta.value;
        }
      });
      var title = h('input', { type: 'text', class: 'pdfd-qtitle', placeholder: 'What it returns', 'aria-label': q.alias + ' title' });
      title.value = q.title || '';
      title.addEventListener('focus', checkpoint);
      title.addEventListener('input', function () { q.title = title.value; setDirty(); });
      body.appendChild(h('div', { class: 'pdfd-query' }, [
        h('div', { class: 'pdfd-qhead' }, [
          h('span', { class: 'pdfd-alias', text: q.alias }), title,
          h('button', { type: 'button', class: 'pdfd-btn pdfd-btn--small', 'data-tip': 'Check the query|Reads its columns (the Fields tab) and its bind variables (the Parameters tab).', 'aria-label': 'Check ' + q.alias, onclick: function () { describe(q, true); } }, [icon('fa-check')]),
          h('button', { type: 'button', class: 'pdfd-btn pdfd-btn--small', 'data-tip': 'Remove ' + q.alias, 'aria-label': 'Remove ' + q.alias, onclick: function () { removeQuery(idx); } }, [icon('fa-times')])
        ]),
        ta, status
      ]));
    });
    if (S.queries.length < 10) {
      body.appendChild(h('button', { type: 'button', class: 'pdfd-btn pdfd-btn--block', onclick: addQuery }, [icon('fa-plus'), ' Add query']));
    }
  }

  function showStatus(alias) {
    var status = S.qstatus && S.qstatus[alias];
    if (!status) { return; }
    var info = S.cols[alias];
    status.classList.toggle('is-error', !!(info && info.error));
    if (info && info.error) { status.textContent = info.error; }
    else if (info) {
      status.textContent = info.columns.length + ' columns' + (info.binds.length ? ' · binds: ' + info.binds.join(', ') : '');
    } else { status.textContent = 'Not checked yet'; }
  }

  function addQuery() {
    checkpoint();
    var used = S.queries.map(function (q) { return q.alias; });
    for (var i = 1; i <= 10; i++) {
      if (used.indexOf('Q' + i) < 0) {
        S.queries.push({ alias: 'Q' + i, title: '', sql: 'select *\n  from dual' });
        S.queries.sort(function (a, b) { return parseInt(a.alias.slice(1), 10) - parseInt(b.alias.slice(1), 10); });
        break;
      }
    }
    setDirty();
    renderLeft();
  }

  function removeQuery(idx) {
    var q = S.queries[idx];
    if (!window.confirm('Remove query ' + q.alias + '? Elements that use its fields stay and print nothing.')) { return; }
    checkpoint();
    S.queries.splice(idx, 1);
    delete S.cols[q.alias];
    setDirty();
    renderLeft();
  }

  function describe(q, announce) {
    if (!q.sql || !q.sql.trim()) { delete S.cols[q.alias]; renderLeft(); return $.Deferred().resolve().promise(); }
    return ajax('DESCRIBE_QUERY', { p_clob_01: q.sql }).then(function (r) {
      S.cols[q.alias] = { columns: r.columns || [], binds: r.binds || [] };
      if (announce) { toast(q.alias + ': ' + r.columns.length + ' columns'); }
    }, function (err) {
      S.cols[q.alias] = { error: String(err), columns: [], binds: [] };
    }).always(function () {
      // on the Queries tab only the status line changes: the user may be typing in another query
      if (S.tab === 'queries' && S.qstatus && S.qstatus[q.alias] && document.body.contains(S.qstatus[q.alias])) { showStatus(q.alias); }
      else { renderLeft(); }
      if (!els.props.contains(document.activeElement)) { renderProps(); }
    });
  }

  function renderFields(body) {
    body.appendChild(h('p', { class: 'pdfd-hint', text: 'Drag a field onto a band to print it, or onto a table to add a column. Double-click adds it to the selected band.' }));
    S.queries.forEach(function (q) {
      var info = S.cols[q.alias];
      var grp = h('div', { class: 'pdfd-fgroup' }, [h('div', { class: 'pdfd-fgroup-head' }, [
        h('span', { class: 'pdfd-alias', text: q.alias }), ' ' + (q.title || '')])]);
      if (!info || info.error) {
        grp.appendChild(h('div', { class: 'pdfd-qstatus' + (info ? ' is-error' : ''), text: info ? info.error : 'Check the query to see its fields.' }));
      } else {
        info.columns.forEach(function (c) {
          grp.appendChild(fieldChip('{' + q.alias + '.' + c.name + '}', c.name, c.type, { alias: q.alias, col: c.name, type: c.type }));
        });
      }
      body.appendChild(grp);
    });
    var sys = h('div', { class: 'pdfd-fgroup' }, [h('div', { class: 'pdfd-fgroup-head', text: 'Page and system' })]);
    [['Page {PAGE} of {PAGES}', 'Page X of Y'], ['{TODAY|DD-MON-YYYY}', 'Today'], ['{NOW}', 'Date and time'],
      ['{APP_USER}', 'User'], ['{REPORT}', 'Report name']].forEach(function (t) {
      sys.appendChild(fieldChip(t[0], t[1], 'TEXT', { token: t[0] }));
    });
    body.appendChild(sys);
    body.appendChild(h('div', { class: 'pdfd-hint' }, [h('strong', { text: 'Tokens: ' }),
      '{Q1.COL} a column · {Q2.AMOUNT|FM999G990D00} with a format · {SUM(Q2.AMOUNT)} {COUNT(Q2)} {AVG(..)} {MIN(..)} {MAX(..)} · {WORDS(Q3.TOTAL)} amount in words (lakh / crore; |INTL for million) · {P11_ITEM} a parameter']));
  }

  function fieldChip(token, label, type, data) {
    var chip = h('div', { class: 'pdfd-chip pdfd-chip--' + String(type).toLowerCase(), draggable: 'true', tabindex: '0', title: token + ' - drag onto a band or a table' }, [
      h('span', { class: 'pdfd-chip-type', text: type === 'NUMBER' ? '#' : (type === 'DATE' ? 'D' : (type === 'BLOB' ? 'B' : 'A')) }), label]);
    chip.addEventListener('dragstart', function (ev) {
      ev.dataTransfer.setData('text/plain', JSON.stringify($.extend({ kind: 'field', token: token }, data)));
      ev.dataTransfer.effectAllowed = 'copy';
    });
    chip.addEventListener('dblclick', function () { addField($.extend({ token: token }, data), S.activeBand); });
    chip.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { addField($.extend({ token: token }, data), S.activeBand); } });
    return chip;
  }

  function allBinds() {
    var out = [];
    S.queries.forEach(function (q) {
      var info = S.cols[q.alias];
      (info && info.binds || []).forEach(function (b) { if (out.indexOf(b) < 0) { out.push(b); } });
    });
    return out;
  }

  function renderParams(body) {
    body.appendChild(h('p', { class: 'pdfd-hint', text: 'Test values for the bind variables, used by Preview. In your application the values come from the page items (session state) or from the parameters of pdf_api.generate.' }));
    var binds = allBinds();
    var rep = S.layout.repeat;
    if (!binds.length) { body.appendChild(h('p', { class: 'pdfd-hint', text: 'The queries have no bind variables (check the queries first).' })); }
    binds.forEach(function (b) {
      var auto = rep && b.indexOf(rep + '_') === 0;
      var inp = h('input', { type: 'text', class: 'pdfd-input', id: 'pdfd-p-' + b, disabled: auto ? 'disabled' : null, placeholder: auto ? 'from each row of ' + rep : '' });
      inp.value = auto ? '' : (S.layout.params[b] || '');
      inp.addEventListener('focus', checkpoint);
      inp.addEventListener('input', function () { S.layout.params[b] = inp.value; setDirty(); });
      body.appendChild(h('div', { class: 'pdfd-field' }, [h('label', { for: 'pdfd-p-' + b, text: ':' + b }), inp]));
    });
  }

  // ------------------------------------------------------------------ canvas
  function renderCanvas() {
    var z = S.zoom;
    var p = S.layout.page;
    var labels = S.layout.type === 'labels';
    var cw = contentWidth();
    var ml = labels ? 0 : p.margin.left;
    var mr = labels ? 0 : p.margin.right;
    els.canvas.innerHTML = '';
    var page = h('div', { class: 'pdfd-page', style: { width: ((cw + ml + mr) * z) + 'px' } });
    els.canvas.appendChild(page);
    var info = labels
      ? 'Label ' + toUnit(S.layout.labels.width) + ' × ' + toUnit(S.layout.labels.height) + ' ' + unit() + ' · ' + S.layout.labels.across + ' across × ' + S.layout.labels.down + ' down on ' + p.size
      : p.size + ' ' + p.orientation + ' · ' + toUnit(p.width) + ' × ' + toUnit(p.height) + ' ' + unit() + ' · margins ' + [p.margin.top, p.margin.right, p.margin.bottom, p.margin.left].map(toUnit).join(' / ');
    page.appendChild(h('div', { class: 'pdfd-pageinfo', text: info }));
    if (!labels) { page.appendChild(h('div', { class: 'pdfd-margin', style: { height: (p.margin.top * z) + 'px' } })); }

    bandDefs().forEach(function (b) {
      var bd = band(b[0]);
      var active = S.activeBand === b[0];
      var wrap = h('div', { class: 'pdfd-band' + (active ? ' is-active' : '') + (bd.height > 0 ? '' : ' is-empty'), 'data-band': b[0],
        title: bd.height > 0 ? null : b[1] + ' is empty (height 0): drag its lower edge to open it' });
      var label = h('button', {
        type: 'button', class: 'pdfd-band-label' + (S.bandSel === b[0] ? ' is-selected' : ''), title: b[2],
        onclick: function () { S.activeBand = b[0]; S.bandSel = b[0]; S.sel = []; renderCanvas(); renderProps(); }
      }, [b[1], h('span', { class: 'pdfd-band-h', text: toUnit(bd.height) + ' ' + unit() }),
        bd.printOn && bd.printOn !== 'all' ? h('span', { class: 'pdfd-band-tag', text: bd.printOn }) : null,
        b[0] === 'summary' && bd.position === 'bottom' ? h('span', { class: 'pdfd-band-tag', text: 'bottom' }) : null]);
      var bodyEl = h('div', {
        class: 'pdfd-band-body' + (S.snap ? ' has-grid' : ''), 'data-band': b[0],
        style: {
          marginLeft: (ml * z) + 'px', width: (cw * z) + 'px', height: (Math.max(bd.height, 0) * z) + 'px',
          backgroundSize: (S.grid * z * 2) + 'px ' + (S.grid * z * 2) + 'px'
        }
      });
      bd.elements.forEach(function (e) { bodyEl.appendChild(renderElement(e, b[0])); });
      bindBand(bodyEl, b[0]);
      wrap.appendChild(label);
      wrap.appendChild(bodyEl);
      if (!labels) {
        var rz = h('div', { class: 'pdfd-band-resize', title: 'Drag to change the height of the band', 'data-band': b[0] });
        rz.addEventListener('mousedown', function (ev) { startBandResize(ev, b[0]); });
        wrap.appendChild(rz);
      }
      page.appendChild(wrap);
    });
    if (!labels) { page.appendChild(h('div', { class: 'pdfd-margin', style: { height: (p.margin.bottom * z) + 'px' } })); }
    renderHandles();
  }

  function fontCss(e, dflt) {
    var z = S.zoom;
    var f = e.font || S.layout.font.family || 'helvetica';
    return {
      fontFamily: FONTS[f] || FONTS.helvetica,
      fontSize: ((e.size || (dflt && dflt.size) || S.layout.font.size || 9) * z) + 'px',
      color: e.color || S.layout.font.color || '#000',
      fontWeight: e.bold ? '700' : '400',
      fontStyle: e.italic ? 'italic' : 'normal',
      textDecoration: e.underline ? 'underline' : 'none'
    };
  }

  // a field on the canvas: {Q1.AMOUNT} in the colour of its element; a format ({Q1.AMOUNT|FM990D00}) is
  // left out of the text and shown on hover
  function tokenHtml(text) {
    return esc(text).replace(/\{([^}|]+)(\|([^}]*))?\}/g, function (m, name, x, mask) {
      return '<span class="pdfd-tok"' + (mask ? ' title="Format: ' + mask + '"' : '') + '>{' + name + '}</span>';
    });
  }

  function frameCss(e) {
    var z = S.zoom;
    var css = {};
    if (e.bg) { css.background = e.bg; }
    if (e.borderWidth > 0) {
      css.border = Math.max(e.borderWidth * z, 1) + 'px ' + (e.dash === 'dashed' ? 'dashed' : e.dash === 'dotted' ? 'dotted' : 'solid') + ' ' + (e.borderColor || '#000');
    }
    if (e.radius) { css.borderRadius = (e.radius * z) + 'px'; }
    return css;
  }

  function renderElement(e, bandName) {
    var z = S.zoom;
    var isSel = S.sel.indexOf(e.id) >= 0;
    var div = h('div', {
      class: 'pdfd-el pdfd-el--' + e.type + (isSel ? ' is-selected' : '') + (e.printWhen ? ' has-cond' : ''),
      'data-id': e.id, 'data-band': bandName, tabindex: '-1',
      title: [e.format ? 'Format: ' + e.format : null, e.printWhen ? 'Printed when ' + e.printWhen : null].filter(Boolean).join('\n') || null
    });
    var x = e.x, y = e.y, w = e.w, hh = e.h;
    if (e.type === 'line') {
      x = Math.min(e.x, e.x + e.w); y = Math.min(e.y, e.y + e.h);
      w = Math.abs(e.w); hh = Math.abs(e.h);
      var pad = 4;
      Object.assign(div.style, { left: (x * z - pad) + 'px', top: (y * z - pad) + 'px', width: (w * z + 2 * pad) + 'px', height: (hh * z + 2 * pad) + 'px' });
      var svg = '<svg width="100%" height="100%" style="overflow:visible"><line x1="' + ((e.x - x) * z + pad) + '" y1="' + ((e.y - y) * z + pad) +
        '" x2="' + ((e.x + e.w - x) * z + pad) + '" y2="' + ((e.y + e.h - y) * z + pad) + '" stroke="' + esc(e.color || '#000') +
        '" stroke-width="' + Math.max((e.lineWidth || 1) * z, 1) + '"' + (e.dash === 'dashed' ? ' stroke-dasharray="6 4"' : e.dash === 'dotted' ? ' stroke-dasharray="1.5 3"' : '') + '/></svg>';
      div.innerHTML = svg;
    } else {
      if (e.type === 'table') { e.h = tableHeight(e); hh = e.h; }
      Object.assign(div.style, { left: (x * z) + 'px', top: (y * z) + 'px', width: (w * z) + 'px', height: (hh * z) + 'px' });
    }
    if (e.type === 'text') {
      Object.assign(div.style, frameCss(e), fontCss(e));
      var inner = h('div', { class: 'pdfd-text', html: tokenHtml(e.text || '') });
      Object.assign(inner.style, {
        padding: ((e.padding === undefined ? 2 : e.padding) * z) + 'px',
        textAlign: e.align || 'left',
        justifyContent: e.valign === 'middle' ? 'center' : e.valign === 'bottom' ? 'flex-end' : 'flex-start',
        whiteSpace: e.wrap === false ? 'pre' : 'pre-wrap',
        lineHeight: e.lineHeight || 1.2
      });
      div.appendChild(inner);
    } else if (e.type === 'box') {
      Object.assign(div.style, frameCss(e));
    } else if (e.type === 'ellipse') {
      Object.assign(div.style, frameCss($.extend({}, e, { borderWidth: e.borderWidth === undefined ? 1 : e.borderWidth })), { borderRadius: '50%' });
    } else if (e.type === 'image') {
      Object.assign(div.style, frameCss(e));
      if (e.src && /^\{/.test(e.src)) {
        div.appendChild(h('div', { class: 'pdfd-imgph' }, [icon('fa-image'), h('span', { text: e.src })]));
      } else if (e.src) {
        var img = h('img', { alt: e.src, class: 'pdfd-img', style: { objectFit: e.fit === 'stretch' ? 'fill' : 'contain' } });
        loadImage(e.src, img);
        div.appendChild(img);
      } else {
        div.appendChild(h('div', { class: 'pdfd-imgph' }, [icon('fa-image'), h('span', { text: 'Choose an image' })]));
      }
    } else if (e.type === 'barcode') {
      Object.assign(div.style, frameCss(e));
      div.appendChild(h('div', { class: 'pdfd-bars', style: { bottom: e.showText === false ? '0' : ((e.size || 8) * 1.3 * z) + 'px' } }));
      if (e.showText !== false) {
        div.appendChild(h('div', { class: 'pdfd-bartext', html: tokenHtml(e.text || ''), style: { fontSize: ((e.size || 8) * z) + 'px', height: ((e.size || 8) * 1.3 * z) + 'px' } }));
      }
    } else if (e.type === 'table') {
      div.appendChild(renderTablePreview(e));
    }
    div.addEventListener('mousedown', function (ev) { startDrag(ev, e, bandName); });
    div.addEventListener('dblclick', function () {
      if (e.type === 'text' || e.type === 'barcode') {
        var t = els.props.querySelector('textarea[data-key="text"]');
        if (t) { t.focus(); t.select(); }
      }
    });
    return div;
  }

  function renderTablePreview(t) {
    var z = S.zoom;
    var size = (t.size || S.layout.font.size || 9);
    var pad = t.padding === undefined ? 3 : t.padding;
    var rowH = t.rowHeight || round(size * 1.2 + 2 * pad, 1);
    var hdr = t.header || {};
    var cols = t.columns || [];
    var sum = cols.reduce(function (a, c) { return a + (c.width || 60); }, 0) || 1;
    var tbl = h('div', { class: 'pdfd-table grid-' + (t.grid || 'all') });
    tbl.style.setProperty('--grid', t.gridColor || '#999');
    var mk = function (cls, height, bg, color, bold, getText) {
      var row = h('div', { class: 'pdfd-trow ' + cls, style: { height: (height * z) + 'px', background: bg || 'transparent' } });
      cols.forEach(function (c, i) {
        row.appendChild(h('div', {
          class: 'pdfd-tcell', html: getText(c, i),
          style: {
            width: ((c.width || 60) / sum * 100) + '%', textAlign: (cls === 'is-head' ? (c.headerAlign || c.align) : c.align) || 'left',
            padding: '0 ' + (pad * z) + 'px', fontWeight: bold ? '700' : '400', color: color || t.color || S.layout.font.color,
            fontSize: ((cls === 'is-head' && hdr.size ? hdr.size : size) * z) + 'px', fontFamily: FONTS[t.font || S.layout.font.family] || FONTS.helvetica
          }
        }));
      });
      return row;
    };
    if (!cols.length) {
      tbl.appendChild(h('div', { class: 'pdfd-tempty', text: 'Table of ' + (t.query || '?') + ': drag fields here or add columns in the properties' }));
      return tbl;
    }
    if (hdr.show !== false) {
      tbl.appendChild(mk('is-head', hdr.height || rowH, hdr.bg, hdr.color, hdr.bold !== false, function (c) { return tokenHtml(c.title || ''); }));
    }
    tbl.appendChild(mk('is-row', rowH, null, null, false, function (c) { return tokenHtml(/\{/.test(c.field || '') ? c.field : '{' + (c.field || '') + '}'); }));
    tbl.appendChild(mk('is-row', rowH, t.zebra, null, false, function () { return '<span class="pdfd-dim">…</span>'; }));
    var hasTot = cols.some(function (c) { return c.total; }) && !(t.totals && t.totals.show === false);
    if (hasTot) {
      var labelDone = false;
      tbl.appendChild(mk('is-tot', rowH, t.totals && t.totals.bg, null, !(t.totals && t.totals.bold === false), function (c) {
        if (c.total) { return '<span class="pdfd-tok">' + esc(c.total.toUpperCase()) + '</span>'; }
        if (!labelDone) { labelDone = true; return esc((t.totals && t.totals.label) || 'Total'); }
        return '';
      }));
    }
    tbl.appendChild(h('div', { class: 'pdfd-tquery', text: t.query || '?' }));
    return tbl;
  }

  function loadImage(name, img) {
    if (imageCache[name]) { img.src = imageCache[name]; return; }
    ajax('IMAGE_DATA', { x01: name }).then(function (r) {
      imageCache[name] = r.data;
      img.src = r.data;
    }, function () { img.alt = 'Image "' + name + '" not found'; });
  }

  // ------------------------------------------------------------------ selection and handles
  function select(ids, keepBand) {
    S.sel = ids;
    if (!keepBand) { S.bandSel = null; }
    if (ids.length) {
      var f = find(ids[0]);
      if (f) { S.activeBand = f.band; }
    }
    renderCanvas();
    renderProps();
  }

  function elDiv(id) { return els.canvas.querySelector('.pdfd-el[data-id="' + id + '"]'); }

  function renderHandles() {
    els.canvas.querySelectorAll('.pdfd-handle').forEach(function (x) { x.remove(); });
    if (S.sel.length !== 1) { return; }
    var f = find(S.sel[0]);
    if (!f) { return; }
    var div = elDiv(f.el.id);
    if (!div) { return; }
    var e = f.el;
    var list;
    if (e.type === 'line') { list = ['p1', 'p2']; }
    else if (e.type === 'table') { list = ['w', 'e']; }
    else { list = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']; }
    list.forEach(function (k) {
      var hd = h('div', { class: 'pdfd-handle pdfd-handle--' + k, 'data-h': k });
      if (e.type === 'line') {
        var z = S.zoom, pad = 4;
        var x0 = Math.min(e.x, e.x + e.w), y0 = Math.min(e.y, e.y + e.h);
        var px = (k === 'p1' ? e.x : e.x + e.w) - x0, py = (k === 'p1' ? e.y : e.y + e.h) - y0;
        Object.assign(hd.style, { left: (px * z + pad - 4) + 'px', top: (py * z + pad - 4) + 'px' });
      }
      hd.addEventListener('mousedown', function (ev) { startResize(ev, f.el, k); });
      div.appendChild(hd);
    });
  }

  // ------------------------------------------------------------------ dragging
  function bandUnder(clientY) {
    var bodies = els.canvas.querySelectorAll('.pdfd-band-body');
    for (var i = 0; i < bodies.length; i++) {
      var r = bodies[i].getBoundingClientRect();
      if (clientY >= r.top && clientY <= r.bottom) { return bodies[i]; }
    }
    return null;
  }

  function startDrag(ev, e, bandName) {
    if (ev.button !== 0 || ev.target.classList.contains('pdfd-handle')) { return; }
    ev.stopPropagation();
    ev.preventDefault();
    if (ev.shiftKey || ev.metaKey || ev.ctrlKey) {
      var i = S.sel.indexOf(e.id);
      if (i >= 0) { S.sel.splice(i, 1); } else { S.sel.push(e.id); }
      select(S.sel.slice());
      return;
    }
    if (S.sel.indexOf(e.id) < 0) { select([e.id]); }
    S.activeBand = bandName;
    var z = S.zoom;
    var sx = ev.clientX, sy = ev.clientY;
    var items = selected().map(function (f) { return { f: f, x: f.el.x, y: f.el.y, div: elDiv(f.el.id) }; });
    var moved = false;
    var srcBody = els.canvas.querySelector('.pdfd-band-body[data-band="' + bandName + '"]');
    var srcTop = srcBody.getBoundingClientRect().top;
    function move(m) {
      var dx = (m.clientX - sx) / z, dy = (m.clientY - sy) / z;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 2 / z) { return; }
      if (!moved) { checkpoint(); moved = true; }
      items.forEach(function (it) {
        var nx = snap(it.x + dx), ny = snap(it.y + dy);
        it.nx = nx; it.ny = ny;
        var lx = it.f.el.type === 'line' ? Math.min(nx, nx + it.f.el.w) : nx;
        var ly = it.f.el.type === 'line' ? Math.min(ny, ny + it.f.el.h) : ny;
        var pad = it.f.el.type === 'line' ? 4 : 0;
        it.div.style.left = (lx * z - pad) + 'px';
        it.div.style.top = (ly * z - pad) + 'px';
      });
      var target = bandUnder(m.clientY);
      els.canvas.querySelectorAll('.pdfd-band-body.is-droptarget').forEach(function (b) { b.classList.remove('is-droptarget'); });
      if (target && target !== srcBody) { target.classList.add('is-droptarget'); }
    }
    function up(m) {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      if (!moved) { return; }
      var target = bandUnder(m.clientY);
      var sameBand = items.every(function (it) { return it.f.band === bandName; });
      if (target && target.getAttribute('data-band') !== bandName && sameBand) {
        var tb = target.getAttribute('data-band');
        var off = (srcTop - target.getBoundingClientRect().top) / z;
        items.forEach(function (it) {
          var src = band(it.f.band).elements;
          src.splice(src.indexOf(it.f.el), 1);
          it.f.el.x = it.nx;
          it.f.el.y = snap(it.ny + off);
          band(tb).elements.push(it.f.el);
        });
        S.activeBand = tb;
      } else {
        items.forEach(function (it) { it.f.el.x = it.nx; it.f.el.y = it.ny; });
      }
      setDirty();
      renderCanvas();
      renderProps();
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }

  function startResize(ev, e, k) {
    ev.stopPropagation();
    ev.preventDefault();
    var z = S.zoom;
    var sx = ev.clientX, sy = ev.clientY;
    var o = { x: e.x, y: e.y, w: e.w, h: e.h };
    var moved = false;
    function move(m) {
      var dx = (m.clientX - sx) / z, dy = (m.clientY - sy) / z;
      if (!moved) { checkpoint(); moved = true; }
      if (k === 'p1') { e.x = snap(o.x + dx); e.y = snap(o.y + dy); e.w = round(o.x + o.w - e.x, 2); e.h = round(o.y + o.h - e.y, 2); }
      else if (k === 'p2') { e.w = round(snap(o.x + o.w + dx) - o.x, 2); e.h = round(snap(o.y + o.h + dy) - o.y, 2); }
      else {
        if (k.indexOf('e') >= 0) { e.w = Math.max(2, snap(o.x + o.w + dx) - o.x); }
        if (k.indexOf('s') >= 0) { e.h = Math.max(2, snap(o.y + o.h + dy) - o.y); }
        if (k.indexOf('w') >= 0) { var nx = Math.min(snap(o.x + dx), o.x + o.w - 2); e.w = round(o.x + o.w - nx, 2); e.x = nx; }
        if (k.indexOf('n') >= 0) { var ny = Math.min(snap(o.y + dy), o.y + o.h - 2); e.h = round(o.y + o.h - ny, 2); e.y = ny; }
        if (e.type === 'table') { fitColumns(e); }
      }
      var f = find(e.id);
      var old = elDiv(e.id);
      var nd = renderElement(e, f.band);
      old.parentNode.replaceChild(nd, old);
      renderHandles();
    }
    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      if (moved) { setDirty(); renderProps(); }
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }

  function startBandResize(ev, name) {
    ev.preventDefault();
    var z = S.zoom, sy = ev.clientY, o = band(name).height, moved = false;
    var bodyEl = els.canvas.querySelector('.pdfd-band-body[data-band="' + name + '"]');
    function move(m) {
      if (!moved) { checkpoint(); moved = true; }
      band(name).height = Math.max(0, snap(o + (m.clientY - sy) / z));
      bodyEl.style.height = (band(name).height * z) + 'px';
    }
    function up() {
      document.removeEventListener('mousemove', move);
      document.removeEventListener('mouseup', up);
      if (moved) { setDirty(); renderCanvas(); renderProps(); }
    }
    document.addEventListener('mousemove', move);
    document.addEventListener('mouseup', up);
  }

  function bindBand(bodyEl, name) {
    // rubber band selection on the empty band
    bodyEl.addEventListener('mousedown', function (ev) {
      if (ev.target !== bodyEl || ev.button !== 0) { return; }
      ev.preventDefault();
      S.activeBand = name;
      var r = bodyEl.getBoundingClientRect();
      var sx = ev.clientX, sy = ev.clientY;
      var box = h('div', { class: 'pdfd-marquee' });
      bodyEl.appendChild(box);
      function move(m) {
        var x1 = Math.min(sx, m.clientX) - r.left, y1 = Math.min(sy, m.clientY) - r.top;
        Object.assign(box.style, { left: x1 + 'px', top: y1 + 'px', width: Math.abs(m.clientX - sx) + 'px', height: Math.abs(m.clientY - sy) + 'px' });
      }
      function up(m) {
        document.removeEventListener('mousemove', move);
        document.removeEventListener('mouseup', up);
        box.remove();
        var z = S.zoom;
        var x1 = (Math.min(sx, m.clientX) - r.left) / z, x2 = (Math.max(sx, m.clientX) - r.left) / z;
        var y1 = (Math.min(sy, m.clientY) - r.top) / z, y2 = (Math.max(sy, m.clientY) - r.top) / z;
        if (x2 - x1 < 2 && y2 - y1 < 2) { S.bandSel = null; select([]); return; }
        var ids = band(name).elements.filter(function (e) {
          var ex = Math.min(e.x, e.x + (e.type === 'line' ? e.w : 0)), ey = Math.min(e.y, e.y + (e.type === 'line' ? e.h : 0));
          var ew = Math.abs(e.w), eh = Math.abs(e.h);
          return ex < x2 && ex + ew > x1 && ey < y2 && ey + eh > y1;
        }).map(function (e) { return e.id; });
        select(ids);
      }
      document.addEventListener('mousemove', move);
      document.addEventListener('mouseup', up);
    });
    // drops from the palette and the field list
    bodyEl.addEventListener('dragover', function (ev) { ev.preventDefault(); bodyEl.classList.add('is-droptarget'); });
    bodyEl.addEventListener('dragleave', function () { bodyEl.classList.remove('is-droptarget'); });
    bodyEl.addEventListener('drop', function (ev) {
      ev.preventDefault();
      bodyEl.classList.remove('is-droptarget');
      var d;
      try { d = JSON.parse(ev.dataTransfer.getData('text/plain')); } catch (x) { return; }
      var r = bodyEl.getBoundingClientRect();
      var x = snap((ev.clientX - r.left) / S.zoom), y = snap((ev.clientY - r.top) / S.zoom);
      // onto a table: a new column
      var tEl = ev.target.closest && ev.target.closest('.pdfd-el--table');
      if (d.kind === 'field' && tEl && d.alias) {
        var t = find(tEl.getAttribute('data-id'));
        if (t) { addColumn(t.el, d); return; }
      }
      if (d.kind === 'new') { addElement(d.type, name, x, y); }
      else if (d.kind === 'field') { addField(d, name, x, y); }
    });
  }

  // ------------------------------------------------------------------ adding and changing elements
  function freeSpot(bandName) {
    var n = band(bandName).elements.length;
    return { x: snap(10 + (n % 6) * 12), y: snap(6 + (n % 6) * 10) };
  }

  function firstQueryWithCols(forRows) {
    // the rows of a table are rarely those of Q1 (usually the one-row header): prefer the next query
    var list = S.queries.filter(function (q) { var c = S.cols[q.alias]; return c && c.columns && c.columns.length; });
    if (forRows && list.length > 1) { list = list.filter(function (q) { return q.alias !== 'Q1'; }); }
    return list.length ? list[0].alias : (S.queries.length ? S.queries[0].alias : 'Q1');
  }

  // a table's columns for the first fields of its query
  function defaultColumns(t) {
    var info = S.cols[t.query];
    t.columns = [];
    if (info && info.columns) {
      info.columns.filter(function (c) { return c.type !== 'BLOB'; }).slice(0, 7).forEach(function (c) { t.columns.push(newColumn(c.name, c.type)); });
      fitColumns(t);
    }
  }

  function addElement(type, bandName, x, y) {
    bandName = bandName || S.activeBand || (S.layout.type === 'labels' ? 'label' : 'body');
    var spot = x === undefined ? freeSpot(bandName) : { x: x, y: y };
    var cw = contentWidth();
    var e = { id: newId(), x: spot.x, y: spot.y };
    switch (type) {
      case 'text': $.extend(e, { type: 'text', w: 160, h: 16, text: 'Text or {' + firstQueryWithCols() + '.FIELD}' }); break;
      case 'box': $.extend(e, { type: 'box', w: 140, h: 60, borderWidth: 1, borderColor: '#000000' }); break;
      case 'rbox': $.extend(e, { type: 'box', w: 140, h: 60, borderWidth: 1, borderColor: '#000000', radius: 8 }); break;
      case 'ellipse': $.extend(e, { type: 'ellipse', w: 70, h: 44, borderWidth: 1, borderColor: '#000000' }); break;
      case 'hline': $.extend(e, { type: 'line', w: Math.min(200, cw - spot.x), h: 0, color: '#000000', lineWidth: 1 }); break;
      case 'vline': $.extend(e, { type: 'line', w: 0, h: 60, color: '#000000', lineWidth: 1 }); break;
      case 'image': $.extend(e, { type: 'image', w: 80, h: 60, src: '', fit: 'contain' }); break;
      case 'barcode': $.extend(e, { type: 'barcode', w: 150, h: 50, text: '12345678', showText: true, size: 8 }); break;
      case 'table':
        $.extend(e, {
          type: 'table', x: 0, w: cw, query: firstQueryWithCols(true), columns: [], size: S.layout.font.size || 9,
          header: { show: true, bg: '#E8EDF3', bold: true, repeat: true }, padding: 3, grid: 'all', gridColor: '#999999', gridWidth: 0.5,
          totals: { show: true, label: 'Total', bold: true }
        });
        defaultColumns(e);
        break;
      default: return;
    }
    checkpoint();
    if (e.type === 'table') { e.h = tableHeight(e); }
    band(bandName).elements.push(e);
    S.activeBand = bandName;
    setDirty();
    select([e.id]);
  }

  function newColumn(name, type) {
    return {
      title: name.replace(/_/g, ' ').toLowerCase().replace(/(^|\s)\S/g, function (s) { return s.toUpperCase(); }),
      field: name, width: 60, align: type === 'NUMBER' ? 'right' : 'left',
      format: type === 'DATE' ? 'DD-MON-YYYY' : ''
    };
  }

  function fitColumns(t) {
    var cols = t.columns || [];
    var sum = cols.reduce(function (a, c) { return a + (c.width || 60); }, 0);
    if (!sum) { return; }
    cols.forEach(function (c) { c.width = round((c.width || 60) * t.w / sum, 2); });
  }

  function addColumn(t, d) {
    checkpoint();
    if (!t.query) { t.query = d.alias; }
    var c = newColumn(d.col, d.type);
    if (d.alias !== t.query) { c.field = '{' + d.alias + '.' + d.col + '}'; }
    t.columns = t.columns || [];
    t.columns.push(c);
    fitColumns(t);
    setDirty();
    select([t.id]);
  }

  function addField(d, bandName, x, y) {
    bandName = bandName || S.activeBand || 'body';
    var spot = x === undefined ? freeSpot(bandName) : { x: x, y: y };
    var e = { id: newId(), type: 'text', x: spot.x, y: spot.y, w: 140, h: 14, text: d.token };
    if (d.type === 'NUMBER') { e.align = 'right'; e.format = 'FM999G999G990D00'; }
    if (d.type === 'DATE') { e.format = 'DD-MON-YYYY'; }
    if (d.type === 'BLOB') { e = { id: e.id, type: 'image', x: spot.x, y: spot.y, w: 80, h: 60, src: d.token, fit: 'contain' }; }
    checkpoint();
    band(bandName).elements.push(e);
    S.activeBand = bandName;
    setDirty();
    select([e.id]);
  }

  function removeSelected() {
    if (!S.sel.length) { return; }
    checkpoint();
    selected().forEach(function (f) {
      var list = band(f.band).elements;
      list.splice(list.indexOf(f.el), 1);
    });
    setDirty();
    select([]);
  }

  function duplicate() {
    if (!S.sel.length) { return; }
    checkpoint();
    var ids = [];
    selected().forEach(function (f) {
      var c = clone(f.el);
      c.id = newId();
      c.x = snap(c.x + 10);
      c.y = snap(c.y + 10);
      band(f.band).elements.push(c);
      ids.push(c.id);
    });
    setDirty();
    select(ids);
  }

  function nudge(dx, dy) {
    if (!S.sel.length) { return; }
    checkpoint();
    selected().forEach(function (f) { f.el.x = round(f.el.x + dx, 2); f.el.y = round(f.el.y + dy, 2); });
    setDirty();
    renderCanvas();
    renderProps();
  }

  function align(kind) {
    var sel = selected();
    if (sel.length < 2) { toast('Select two or more elements (Shift+click) to align them.'); return; }
    checkpoint();
    var first = sel[0].el;
    var box = sel.reduce(function (b, f) {
      var e = f.el;
      return { l: Math.min(b.l, e.x), t: Math.min(b.t, e.y), r: Math.max(b.r, e.x + e.w), b: Math.max(b.b, e.y + e.h) };
    }, { l: 1e9, t: 1e9, r: -1e9, b: -1e9 });
    sel.forEach(function (f) {
      var e = f.el;
      if (kind === 'left') { e.x = box.l; }
      if (kind === 'right') { e.x = round(box.r - e.w, 2); }
      if (kind === 'center') { e.x = round((box.l + box.r) / 2 - e.w / 2, 2); }
      if (kind === 'top') { e.y = box.t; }
      if (kind === 'bottom') { e.y = round(box.b - e.h, 2); }
      if (kind === 'middle') { e.y = round((box.t + box.b) / 2 - e.h / 2, 2); }
      if (kind === 'width' && e.type !== 'line') { e.w = first.w; }
      if (kind === 'height' && e.type !== 'line' && e.type !== 'table') { e.h = first.h; }
    });
    setDirty();
    renderCanvas();
    renderProps();
  }

  function order(front) {
    if (!S.sel.length) { return; }
    checkpoint();
    selected().forEach(function (f) {
      var list = band(f.band).elements;
      list.splice(list.indexOf(f.el), 1);
      if (front) { list.push(f.el); } else { list.unshift(f.el); }
    });
    setDirty();
    renderCanvas();
  }

  // ------------------------------------------------------------------ properties
  function renderProps() {
    var p = els.props;
    var keepScroll = p.scrollTop;
    p.innerHTML = '';
    var sel = selected();
    if (sel.length === 1) { elementProps(p, sel[0].el, sel[0].band); }
    else if (sel.length > 1) { multiProps(p, sel); }
    else if (S.bandSel) { bandProps(p, S.bandSel); }
    else { reportProps(p); }
    p.scrollTop = keepScroll;
  }

  function section(p, title, open) {
    var body = h('div', { class: 'pdfd-sec-body' });
    var d = h('details', { class: 'pdfd-sec', open: open === false ? null : 'open' }, [h('summary', { text: title }), body]);
    p.appendChild(d);
    return body;
  }

  // one property: an input bound to obj[key]
  function field(parent, label, obj, key, kind, opt) {
    opt = opt || {};
    var id = 'pdfd-f-' + (++S.fieldSeq);
    var inp;
    var val = obj[key];
    var after = function () {
      setDirty();
      if (opt.onChange) { opt.onChange(); }
      if (opt.rerender) { renderProps(); }
      refreshSelected();
    };
    if (kind === 'select') {
      inp = h('select', { id: id, class: 'pdfd-input' });
      opt.options.forEach(function (o) {
        var ov = Array.isArray(o) ? o[0] : o, ol = Array.isArray(o) ? o[1] : o;
        var oe = h('option', { value: ov, text: ol });
        if (String(val === undefined || val === null ? (opt.dflt !== undefined ? opt.dflt : '') : val) === String(ov)) { oe.selected = true; }
        inp.appendChild(oe);
      });
      inp.addEventListener('change', function () { checkpoint(); obj[key] = inp.value; after(); });
    } else if (kind === 'check') {
      inp = h('input', { id: id, type: 'checkbox', class: 'pdfd-check' });
      inp.checked = val === undefined ? !!opt.dflt : !!val;
      inp.addEventListener('change', function () { checkpoint(); obj[key] = inp.checked; after(); });
      var row = h('div', { class: 'pdfd-field pdfd-field--check' }, [inp, h('label', { for: id, text: label })]);
      parent.appendChild(row);
      return inp;
    } else if (kind === 'color') {
      return colorField(parent, label, obj, key, opt, after);
    } else if (kind === 'textarea') {
      inp = h('textarea', { id: id, class: 'pdfd-input pdfd-textarea', rows: opt.rows || 3, 'data-key': key, spellcheck: 'false' });
      inp.value = val || '';
      inp.addEventListener('focus', checkpoint);
      inp.addEventListener('input', function () { obj[key] = inp.value; setDirty(); refreshSelected(); });
      inp.addEventListener('focus', function () { S.lastText = inp; });
    } else {
      var isLen = kind === 'len';
      inp = h('input', {
        id: id, class: 'pdfd-input', type: kind === 'text' ? 'text' : 'number', step: isLen ? (unit() === 'pt' ? 0.5 : 0.1) : (opt.step || 'any'),
        list: opt.list || null, placeholder: opt.placeholder || null, 'data-key': key
      });
      inp.value = val === undefined || val === null ? '' : (isLen ? toUnit(val) : val);
      inp.addEventListener('focus', checkpoint);
      inp.addEventListener('focus', function () { if (kind === 'text') { S.lastText = inp; } });
      inp.addEventListener('input', function () {
        if (kind === 'text') { obj[key] = inp.value; }
        else if (inp.value === '') { delete obj[key]; }
        else { obj[key] = isLen ? round(fromUnit(inp.value), 2) : num(inp.value, 0); }
        setDirty();
        if (opt.onChange) { opt.onChange(); }
        refreshSelected();
      });
      if (opt.rerender) { inp.addEventListener('change', renderProps); }
    }
    parent.appendChild(h('div', { class: 'pdfd-field' + (opt.half ? ' pdfd-field--half' : '') }, [
      h('label', { for: id, text: label + (kind === 'len' ? ' (' + unit() + ')' : '') }), inp,
      opt.hint ? h('div', { class: 'pdfd-fhint', text: opt.hint }) : null]));
    return inp;
  }

  function colorField(parent, label, obj, key, opt, after) {
    var id = 'pdfd-f-' + (++S.fieldSeq);
    var on = h('input', { type: 'checkbox', class: 'pdfd-check', title: 'Use a colour', 'aria-label': label + ': on' });
    var col = h('input', { id: id, type: 'color', class: 'pdfd-color' });
    var cur = obj[key];
    on.checked = !!cur || !!opt.required;
    col.value = /^#[0-9a-f]{6}$/i.test(cur || '') ? cur : (opt.dflt || '#000000');
    col.disabled = !on.checked;
    if (opt.required) { on.style.display = 'none'; }
    on.addEventListener('change', function () {
      checkpoint();
      col.disabled = !on.checked;
      if (on.checked) { obj[key] = col.value; } else { delete obj[key]; }
      after();
    });
    col.addEventListener('focus', checkpoint);
    col.addEventListener('input', function () { obj[key] = col.value; setDirty(); refreshSelected(); });
    parent.appendChild(h('div', { class: 'pdfd-field pdfd-field--color' + (opt.half ? ' pdfd-field--half' : '') }, [
      h('label', { for: id, text: label }), h('div', { class: 'pdfd-colorwrap' }, [on, col])]));
    return col;
  }

  function buttonsRow(parent, list) {
    var row = h('div', { class: 'pdfd-btnrow' });
    list.forEach(function (b) { row.appendChild(h('button', { type: 'button', class: 'pdfd-btn pdfd-btn--small', title: b[2] || b[1], onclick: b[3] }, [b[0] ? icon(b[0]) : null, b[1] ? ' ' + b[1] : null])); });
    parent.appendChild(row);
    return row;
  }

  function segField(parent, label, obj, key, opts, dflt) {
    var row = h('div', { class: 'pdfd-seg', role: 'radiogroup', 'aria-label': label });
    opts.forEach(function (o) {
      var b = h('button', {
        type: 'button', class: 'pdfd-btn pdfd-btn--small' + ((obj[key] || dflt) === o[0] ? ' is-on' : ''), title: o[2], 'aria-label': o[2], role: 'radio',
        'aria-checked': (obj[key] || dflt) === o[0] ? 'true' : 'false',
        onclick: function () { checkpoint(); obj[key] = o[0]; setDirty(); refreshSelected(); renderProps(); }
      }, [icon(o[1])]);
      row.appendChild(b);
    });
    parent.appendChild(h('div', { class: 'pdfd-field pdfd-field--half' }, [h('label', { text: label }), row]));
  }

  // what the properties panel calls an element: a text holding one field only is "Field Q1.COLUMN"
  function elementName(e) {
    var t = (e.text || '').trim();
    if (e.type === 'text') { return /^\{Q[0-9]+\.[^}|]+(\|[^}]*)?\}$/.test(t) ? 'Field ' + t.slice(1, -1).split('|')[0] : 'Text / Field'; }
    return { box: e.radius ? 'Rounded box' : 'Box', ellipse: 'Ellipse', line: 'Line', image: 'Image', table: 'Table', barcode: 'Barcode' }[e.type] || e.type;
  }

  function refreshSelected() {
    var head = els.props.querySelector('.pdfd-props-head strong');
    if (head && S.sel.length === 1 && find(S.sel[0])) { head.textContent = elementName(find(S.sel[0]).el); }
    // redraw only the selected elements (keeps the focus in the properties)
    S.sel.forEach(function (id) {
      var f = find(id);
      var old = elDiv(id);
      if (f && old) { old.parentNode.replaceChild(renderElement(f.el, f.band), old); }
    });
    renderHandles();
  }

  function positionProps(p, e) {
    var s = section(p, 'Position and size');
    field(s, 'X', e, 'x', 'len', { half: true });
    field(s, 'Y', e, 'y', 'len', { half: true });
    if (e.type === 'line') {
      field(s, 'Length X', e, 'w', 'len', { half: true });
      field(s, 'Length Y', e, 'h', 'len', { half: true });
      buttonsRow(s, [['fa-arrows-h', 'Horizontal', 'Make it horizontal', function () { checkpoint(); e.w = e.w || e.h; e.h = 0; setDirty(); renderCanvas(); renderProps(); }],
        ['fa-arrows-v', 'Vertical', 'Make it vertical', function () { checkpoint(); e.h = e.h || e.w; e.w = 0; setDirty(); renderCanvas(); renderProps(); }]]);
    } else {
      field(s, 'Width', e, 'w', 'len', { half: true, onChange: function () { if (e.type === 'table') { fitColumns(e); } } });
      if (e.type !== 'table') { field(s, 'Height', e, 'h', 'len', { half: true }); }
    }
    buttonsRow(s, [['fa-level-up', 'Front', 'Bring to front', function () { order(true); }],
      ['fa-level-down', 'Back', 'Send to back', function () { order(false); }],
      ['fa-arrows-h', 'Full width', 'Stretch across the band', function () { checkpoint(); e.x = 0; if (e.type === 'line') { e.w = contentWidth(); } else { e.w = contentWidth(); } if (e.type === 'table') { fitColumns(e); } setDirty(); renderCanvas(); renderProps(); }]]);
  }

  function fontProps(s, e) {
    field(s, 'Font', e, 'font', 'select', { half: true, options: [['', 'Default']].concat(FONT_OPTIONS) });
    field(s, 'Size (pt)', e, 'size', 'number', { half: true, placeholder: String(S.layout.font.size || 9), step: 0.5 });
    var tg = h('div', { class: 'pdfd-seg' });
    [['bold', 'fa-bold', 'Bold'], ['italic', 'fa-italic', 'Italic'], ['underline', 'fa-underline', 'Underline']].forEach(function (t) {
      if (e.type !== 'text' && t[0] === 'underline') { return; }
      tg.appendChild(h('button', {
        type: 'button', class: 'pdfd-btn pdfd-btn--small' + (e[t[0]] ? ' is-on' : ''), title: t[2], 'aria-pressed': e[t[0]] ? 'true' : 'false',
        onclick: function () { checkpoint(); e[t[0]] = !e[t[0]]; setDirty(); refreshSelected(); renderProps(); }
      }, [icon(t[1])]));
    });
    s.appendChild(h('div', { class: 'pdfd-field pdfd-field--half' }, [h('label', { text: 'Style' }), tg]));
    field(s, 'Colour', e, 'color', 'color', { half: true, dflt: S.layout.font.color || '#000000' });
  }

  function frameProps(p, e, open) {
    var s = section(p, e.type === 'box' || e.type === 'ellipse' ? 'Fill and border' : 'Background and border', open);
    field(s, 'Fill', e, 'bg', 'color', { half: true, dflt: '#EEEEEE' });
    field(s, 'Border colour', e, 'borderColor', 'color', { half: true, dflt: '#000000' });
    field(s, 'Border width (pt)', e, 'borderWidth', 'number', { half: true, step: 0.25, placeholder: '0' });
    field(s, 'Border style', e, 'dash', 'select', { half: true, options: [['', 'Solid'], ['dashed', 'Dashed'], ['dotted', 'Dotted']] });
    if (e.type !== 'ellipse') { field(s, 'Corner radius (pt)', e, 'radius', 'number', { half: true, step: 1, placeholder: '0' }); }
  }

  function condProps(p, e) {
    var s = section(p, 'Print when', !!e.printWhen);
    field(s, 'Condition', e, 'printWhen', 'text', {
      placeholder: '{Q1.STATUS} = PAID',
      hint: 'Empty: always. {Q1.DISCOUNT} alone: when it has a value (not 0). Or compare with = != > < >= <=.'
    });
  }

  function elementProps(p, e, bandName) {
    p.appendChild(h('div', { class: 'pdfd-props-head' }, [h('strong', { text: elementName(e) }), h('span', { text: ' in ' + bandLabel(bandName) })]));
    if (e.type === 'text') {
      var s = section(p, 'Text and fields');
      field(s, 'Text', e, 'text', 'textarea', { rows: 3 });
      s.appendChild(h('div', { class: 'pdfd-fhint', text: 'Fixed text, fields and tokens, mixed as you like: Invoice No. {Q1.INVOICE_NO}, Page {PAGE} of {PAGES}, {SUM(Q2.AMOUNT)}. While typing here, click a field in the Fields tab to insert it.' }));
      field(s, 'Format mask', e, 'format', 'text', { list: 'pdfd-masks', placeholder: 'e.g. FM999G990D00', hint: 'For a single token: a number or date format.' });
      fontProps(s, e);
      segField(s, 'Align', e, 'align', [['left', 'fa-align-left', 'Left'], ['center', 'fa-align-center', 'Centre'], ['right', 'fa-align-right', 'Right']], 'left');
      segField(s, 'Vertical', e, 'valign', [['top', 'fa-long-arrow-up', 'Top'], ['middle', 'fa-arrows-v', 'Middle'], ['bottom', 'fa-long-arrow-down', 'Bottom']], 'top');
      field(s, 'Wrap long text', e, 'wrap', 'check', { dflt: true });
      field(s, 'Padding (pt)', e, 'padding', 'number', { half: true, placeholder: '2', step: 0.5 });
      field(s, 'Line height', e, 'lineHeight', 'number', { half: true, placeholder: '1.2', step: 0.05 });
      frameProps(p, e, false);
    } else if (e.type === 'box' || e.type === 'ellipse') {
      frameProps(p, e, true);
    } else if (e.type === 'line') {
      var sl = section(p, 'Line');
      field(sl, 'Colour', e, 'color', 'color', { half: true, required: true, dflt: '#000000' });
      field(sl, 'Width (pt)', e, 'lineWidth', 'number', { half: true, step: 0.25, placeholder: '1' });
      field(sl, 'Style', e, 'dash', 'select', { half: true, options: [['', 'Solid'], ['dashed', 'Dashed'], ['dotted', 'Dotted']] });
    } else if (e.type === 'image') {
      imageProps(p, e);
      frameProps(p, e, false);
    } else if (e.type === 'barcode') {
      var sb = section(p, 'Barcode (Code 128)');
      field(sb, 'Value', e, 'text', 'textarea', { rows: 2 });
      sb.appendChild(h('div', { class: 'pdfd-fhint', text: 'A token like {Q1.SKU}, or fixed text. Digits only (even count) are encoded compactly.' }));
      field(sb, 'Show the value below', e, 'showText', 'check', { dflt: true });
      field(sb, 'Text size (pt)', e, 'size', 'number', { half: true, placeholder: '8' });
      field(sb, 'Colour', e, 'color', 'color', { half: true, required: true, dflt: '#000000' });
      frameProps(p, e, false);
    } else if (e.type === 'table') {
      tableProps(p, e);
    }
    positionProps(p, e);
    condProps(p, e);
  }

  function bandLabel(name) {
    var d = bandDefs().filter(function (b) { return b[0] === name; })[0];
    return d ? d[1] : name;
  }

  function imageProps(p, e) {
    var s = section(p, 'Image');
    var sel = h('select', { class: 'pdfd-input', id: 'pdfd-imgsel' });
    var dyn = /^\{/.test(e.src || '');
    sel.appendChild(h('option', { value: '', text: '- choose -' }));
    (S.images || []).forEach(function (im) {
      var o = h('option', { value: im.name, text: im.name + ' (' + im.width + ' × ' + im.height + ')' });
      if (im.name === e.src) { o.selected = true; }
      sel.appendChild(o);
    });
    var o2 = h('option', { value: '__dyn', text: 'From a query column (BLOB) ...' });
    if (dyn) { o2.selected = true; }
    sel.appendChild(o2);
    sel.addEventListener('change', function () {
      checkpoint();
      e.src = sel.value === '__dyn' ? '{' + firstQueryWithCols() + '.IMAGE}' : sel.value;
      setDirty();
      refreshSelected();
      renderProps();
    });
    s.appendChild(h('div', { class: 'pdfd-field' }, [h('label', { for: 'pdfd-imgsel', text: 'Image' }), sel]));
    if (dyn) { field(s, 'Column token', e, 'src', 'text', { hint: 'A BLOB column holding a JPEG, e.g. {Q1.PHOTO}.' }); }
    field(s, 'Fit', e, 'fit', 'select', { half: true, options: [['contain', 'Keep proportions'], ['stretch', 'Stretch']] });
    var file = h('input', { type: 'file', accept: 'image/*', class: 'pdfd-hidden' });
    file.addEventListener('change', function () { if (file.files[0]) { uploadImage(file.files[0], e); } });
    s.appendChild(file);
    buttonsRow(s, [['fa-upload', 'Upload image', 'Upload a PNG or JPEG (it is stored as JPEG)', function () { file.click(); }]]);
  }

  function uploadImage(f, target) {
    var name = window.prompt('Name of the image (used by the layouts):', f.name.replace(/\.[^.]+$/, '').toLowerCase().replace(/[^a-z0-9]+/g, '-'));
    if (!name) { return; }
    var reader = new FileReader();
    reader.onload = function () {
      var img = new Image();
      img.onload = function () {
        var max = 1600, w = img.naturalWidth, hh = img.naturalHeight;
        if (Math.max(w, hh) > max) { var r = max / Math.max(w, hh); w = Math.round(w * r); hh = Math.round(hh * r); }
        var c = document.createElement('canvas');
        c.width = w; c.height = hh;
        var ctx = c.getContext('2d');
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, w, hh);
        ctx.drawImage(img, 0, 0, w, hh);
        var data = c.toDataURL('image/jpeg', 0.92);
        ajax('SAVE_IMAGE', { x01: name, p_clob_01: data }).then(function (r) {
          imageCache[r.name] = data;
          toast('Image "' + r.name + '" saved');
          loadImages().then(function () {
            if (target) { checkpoint(); target.src = r.name; setDirty(); refreshSelected(); }
            renderProps();
          });
        }, function (err) { toast(err, true); });
      };
      img.onerror = function () { toast('This file is not an image the browser can read.', true); };
      img.src = reader.result;
    };
    reader.readAsDataURL(f);
  }

  function loadImages() {
    return ajax('LIST_IMAGES', {}).then(function (r) { S.images = r || []; });
  }

  function queryOptions(withEmpty) {
    var out = withEmpty ? [['', '- none -']] : [];
    S.queries.forEach(function (q) { out.push([q.alias, q.alias + (q.title ? ' - ' + q.title : '')]); });
    return out;
  }
  function columnOptions(alias) {
    var info = S.cols[alias];
    return (info && info.columns || []).map(function (c) { return [c.name, c.name]; });
  }

  function tableProps(p, t) {
    var s = section(p, 'Data');
    var oldQuery = t.query;
    field(s, 'Rows of query', t, 'query', 'select', {
      options: queryOptions(), rerender: true,
      onChange: function () {
        // columns that were plain fields of the old query make no sense for the new one
        var old = (S.cols[oldQuery] && S.cols[oldQuery].columns || []).map(function (c) { return c.name; });
        var fromOld = (t.columns || []).every(function (c) { return old.indexOf(c.field) >= 0; });
        if (fromOld) { defaultColumns(t); delete t.groupBy; }
        oldQuery = t.query;
      }
    });
    var cs = section(p, 'Columns');
    var cols = t.columns = t.columns || [];
    var fieldOpts = columnOptions(t.query);
    cols.forEach(function (c, i) {
      var box = h('div', { class: 'pdfd-colcard' });
      var head = h('div', { class: 'pdfd-colhead' }, [h('span', { class: 'pdfd-colno', text: String(i + 1) })]);
      var title = h('input', { type: 'text', class: 'pdfd-input', 'aria-label': 'Column ' + (i + 1) + ' heading', placeholder: 'Heading' });
      title.value = c.title || '';
      title.addEventListener('focus', checkpoint);
      title.addEventListener('input', function () { c.title = title.value; setDirty(); refreshSelected(); });
      head.appendChild(title);
      [['fa-arrow-up', 'Move left', function () { if (i > 0) { checkpoint(); cols.splice(i - 1, 0, cols.splice(i, 1)[0]); setDirty(); refreshSelected(); renderProps(); } }],
        ['fa-arrow-down', 'Move right', function () { if (i < cols.length - 1) { checkpoint(); cols.splice(i + 1, 0, cols.splice(i, 1)[0]); setDirty(); refreshSelected(); renderProps(); } }],
        ['fa-times', 'Remove the column', function () { checkpoint(); cols.splice(i, 1); fitColumns(t); setDirty(); refreshSelected(); renderProps(); }]
      ].forEach(function (b) { head.appendChild(h('button', { type: 'button', class: 'pdfd-btn pdfd-btn--small', title: b[1], 'aria-label': b[1], onclick: b[2] }, [icon(b[0])])); });
      box.appendChild(head);
      var grid = h('div', { class: 'pdfd-colgrid' });
      var fsel = h('select', { class: 'pdfd-input', 'aria-label': 'Column ' + (i + 1) + ' field' });
      var known = false;
      fieldOpts.forEach(function (o) {
        var oe = h('option', { value: o[0], text: o[1] });
        if (o[0] === c.field) { oe.selected = true; known = true; }
        fsel.appendChild(oe);
      });
      var custom = h('option', { value: '__expr', text: 'Text with tokens ...' });
      if (!known) { custom.selected = true; }
      fsel.appendChild(custom);
      var expr = h('input', { type: 'text', class: 'pdfd-input', placeholder: '{Q2.QTY} x {Q2.UNIT}', 'aria-label': 'Column ' + (i + 1) + ' text' });
      expr.value = known ? '' : (c.field || '');
      expr.style.display = known ? 'none' : '';
      expr.addEventListener('focus', checkpoint);
      expr.addEventListener('input', function () { c.field = expr.value; setDirty(); refreshSelected(); });
      fsel.addEventListener('change', function () {
        checkpoint();
        if (fsel.value === '__expr') { c.field = expr.value || ''; expr.style.display = ''; }
        else { c.field = fsel.value; expr.style.display = 'none'; }
        setDirty(); refreshSelected();
      });
      grid.appendChild(h('div', { class: 'pdfd-cg-wide' }, [fsel, expr]));
      var wIn = h('input', { type: 'number', class: 'pdfd-input', step: '1', 'aria-label': 'Column ' + (i + 1) + ' width (pt)', title: 'Width (pt, relative)' });
      wIn.value = round(c.width || 60, 1);
      wIn.addEventListener('focus', checkpoint);
      wIn.addEventListener('change', function () { c.width = num(wIn.value, 60); fitColumns(t); setDirty(); refreshSelected(); renderProps(); });
      var aSel = h('select', { class: 'pdfd-input', 'aria-label': 'Column ' + (i + 1) + ' alignment' });
      [['left', 'Left'], ['center', 'Centre'], ['right', 'Right']].forEach(function (o) { var oe = h('option', { value: o[0], text: o[1] }); if ((c.align || 'left') === o[0]) { oe.selected = true; } aSel.appendChild(oe); });
      aSel.addEventListener('change', function () { checkpoint(); c.align = aSel.value; setDirty(); refreshSelected(); });
      var fIn = h('input', { type: 'text', class: 'pdfd-input', list: 'pdfd-masks', placeholder: 'Format', 'aria-label': 'Column ' + (i + 1) + ' format mask' });
      fIn.value = c.format || '';
      fIn.addEventListener('focus', checkpoint);
      fIn.addEventListener('input', function () { c.format = fIn.value; setDirty(); });
      var tSel = h('select', { class: 'pdfd-input', 'aria-label': 'Column ' + (i + 1) + ' total' });
      [['', 'No total'], ['sum', 'Sum'], ['count', 'Count'], ['avg', 'Average'], ['min', 'Min'], ['max', 'Max']].forEach(function (o) { var oe = h('option', { value: o[0], text: o[1] }); if ((c.total || '') === o[0]) { oe.selected = true; } tSel.appendChild(oe); });
      tSel.addEventListener('change', function () { checkpoint(); if (tSel.value) { c.total = tSel.value; } else { delete c.total; } setDirty(); refreshSelected(); });
      grid.appendChild(labeled('Width', wIn));
      grid.appendChild(labeled('Align', aSel));
      grid.appendChild(labeled('Format', fIn));
      grid.appendChild(labeled('Total', tSel));
      box.appendChild(grid);
      cs.appendChild(box);
    });
    buttonsRow(cs, [
      ['fa-plus', 'Column', 'Add a column', function () { checkpoint(); cols.push({ title: 'Column', field: fieldOpts.length ? fieldOpts[0][0] : '', width: 60 }); fitColumns(t); setDirty(); refreshSelected(); renderProps(); }],
      ['fa-list', 'All fields', 'A column for every field of the query', function () {
        var info = S.cols[t.query];
        if (!info || !info.columns.length) { toast('Check query ' + t.query + ' first (Queries tab).'); return; }
        checkpoint();
        info.columns.forEach(function (c) { if (!cols.some(function (x) { return x.field === c.name; }) && c.type !== 'BLOB') { cols.push(newColumn(c.name, c.type)); } });
        fitColumns(t); setDirty(); refreshSelected(); renderProps();
      }]]);

    var sh = section(p, 'Header row', false);
    t.header = t.header || {};
    field(sh, 'Show the header', t.header, 'show', 'check', { dflt: true });
    field(sh, 'Repeat on every page', t.header, 'repeat', 'check', { dflt: true });
    field(sh, 'Bold', t.header, 'bold', 'check', { dflt: true });
    field(sh, 'Background', t.header, 'bg', 'color', { half: true, dflt: '#E8EDF3' });
    field(sh, 'Text colour', t.header, 'color', 'color', { half: true, dflt: '#000000' });
    field(sh, 'Height (pt)', t.header, 'height', 'number', { half: true, placeholder: 'as rows' });
    field(sh, 'Text size (pt)', t.header, 'size', 'number', { half: true, placeholder: 'as rows', step: 0.5 });

    var sr = section(p, 'Rows', false);
    field(sr, 'Font', t, 'font', 'select', { half: true, options: [['', 'Default']].concat(FONT_OPTIONS) });
    field(sr, 'Size (pt)', t, 'size', 'number', { half: true, placeholder: String(S.layout.font.size || 9), step: 0.5 });
    field(sr, 'Text colour', t, 'color', 'color', { half: true, dflt: '#000000' });
    field(sr, 'Alternate rows', t, 'zebra', 'color', { half: true, dflt: '#F3F6FA' });
    field(sr, 'Min. row height (pt)', t, 'rowHeight', 'number', { half: true, placeholder: 'auto' });
    field(sr, 'Cell padding (pt)', t, 'padding', 'number', { half: true, placeholder: '3', step: 0.5 });
    field(sr, 'Wrap long text (rows grow)', t, 'wrap', 'check', { dflt: true });
    field(sr, 'Lines', t, 'grid', 'select', { half: true, options: [['all', 'All cells'], ['horizontal', 'Between rows'], ['outer', 'Outer border'], ['none', 'None']] });
    field(sr, 'Line colour', t, 'gridColor', 'color', { half: true, required: true, dflt: '#999999' });
    field(sr, 'Line width (pt)', t, 'gridWidth', 'number', { half: true, step: 0.25, placeholder: '0.5' });
    field(sr, 'When there are no rows', t, 'noData', 'text', { placeholder: 'e.g. No items' });

    var st = section(p, 'Totals', false);
    t.totals = t.totals || {};
    field(st, 'Show the totals row', t.totals, 'show', 'check', { dflt: true, hint: '' });
    st.appendChild(h('div', { class: 'pdfd-fhint', text: 'A column shows a total when its Total is set (Columns).' }));
    field(st, 'Label', t.totals, 'label', 'text', { placeholder: 'Total' });
    field(st, 'Background', t.totals, 'bg', 'color', { half: true, dflt: '#E8EDF3' });
    field(st, 'Bold', t.totals, 'bold', 'check', { dflt: true });

    var sg = section(p, 'Groups', !!t.groupBy);
    field(sg, 'Group by', t, 'groupBy', 'select', { options: [['', '- no groups -']].concat(columnOptions(t.query)), rerender: true, hint: 'Order the query by this column. A heading row starts every group.' });
    if (t.groupBy) {
      field(sg, 'Group heading', t, 'groupLabel', 'text', { placeholder: '{VALUE}' });
      field(sg, 'Group background', t, 'groupBg', 'color', { half: true, dflt: '#EEF2F7' });
      field(sg, 'Sub-totals per group', t, 'groupTotals', 'check', { dflt: true });
      field(sg, 'Sub-total label', t, 'groupTotalLabel', 'text', { placeholder: 'Sub-total' });
    }
  }

  function labeled(label, input) {
    return h('div', { class: 'pdfd-cg' }, [h('span', { class: 'pdfd-cg-label', text: label }), input]);
  }

  function multiProps(p, sel) {
    p.appendChild(h('div', { class: 'pdfd-props-head' }, [h('strong', { text: sel.length + ' elements' })]));
    var s = section(p, 'Change them all');
    var proxy = {};
    var apply = function (k, v) { checkpoint(); sel.forEach(function (f) { if (v === undefined || v === '') { delete f.el[k]; } else { f.el[k] = v; } }); setDirty(); renderCanvas(); };
    var fsel = h('select', { class: 'pdfd-input', id: 'pdfd-m-font' }, [['', '-']].concat(FONT_OPTIONS).map(function (o) { return h('option', { value: o[0], text: o[1] }); }));
    fsel.addEventListener('change', function () { if (fsel.value) { apply('font', fsel.value); } });
    s.appendChild(h('div', { class: 'pdfd-field pdfd-field--half' }, [h('label', { for: 'pdfd-m-font', text: 'Font' }), fsel]));
    var size = h('input', { type: 'number', class: 'pdfd-input', id: 'pdfd-m-size', step: '0.5' });
    size.addEventListener('change', function () { apply('size', size.value ? num(size.value, 9) : undefined); });
    s.appendChild(h('div', { class: 'pdfd-field pdfd-field--half' }, [h('label', { for: 'pdfd-m-size', text: 'Size (pt)' }), size]));
    buttonsRow(s, [['fa-bold', 'Bold', 'Bold on', function () { apply('bold', true); }], [null, 'Regular', 'Bold off', function () { apply('bold', false); }]]);
    var col = h('input', { type: 'color', class: 'pdfd-color', id: 'pdfd-m-color' });
    col.addEventListener('change', function () { apply('color', col.value); });
    s.appendChild(h('div', { class: 'pdfd-field pdfd-field--half' }, [h('label', { for: 'pdfd-m-color', text: 'Text colour' }), col]));
    proxy.x = null;
    s.appendChild(h('p', { class: 'pdfd-hint', text: 'Use the toolbar to align them, the arrow keys to move them (Shift: 10 pt).' }));
  }

  function bandProps(p, name) {
    var bd = band(name);
    var def = bandDefs().filter(function (b) { return b[0] === name; })[0];
    p.appendChild(h('div', { class: 'pdfd-props-head' }, [h('strong', { text: def[1] }), h('span', { text: ' band' })]));
    p.appendChild(h('p', { class: 'pdfd-hint', text: def[2] }));
    var s = section(p, 'Band');
    if (S.layout.type !== 'labels') {
      field(s, 'Height', bd, 'height', 'len', { onChange: renderCanvas });
    }
    if (name === 'pageHeader' || name === 'pageFooter') {
      field(s, 'Print on', bd, 'printOn', 'select', {
        options: [['all', 'Every page'], ['first', 'First page only'], ['notFirst', 'All but the first page'], ['last', 'Last page only'], ['notLast', 'All but the last page']],
        onChange: renderCanvas
      });
    }
    if (name === 'summary') {
      field(s, 'Position', bd, 'position', 'select', { options: [['', 'Right after the body'], ['bottom', 'At the bottom of the last page']], onChange: renderCanvas });
    }
    buttonsRow(s, [['fa-plus', 'Text', 'Add a text', function () { addElement('text', name); }],
      ['fa-table', 'Table', 'Add a table', function () { addElement('table', name); }]]);
  }

  function reportProps(p) {
    p.appendChild(h('div', { class: 'pdfd-props-head' }, [h('strong', { text: 'Report' })]));
    var s = section(p, 'Report');
    var meta = { name: S.name, description: S.description };
    field(s, 'Name', meta, 'name', 'text', { onChange: function () { S.name = meta.name; els.title.querySelector('strong').textContent = S.name; } });
    field(s, 'Description', meta, 'description', 'textarea', { rows: 3 });
    p.lastChild.querySelector('textarea').addEventListener('input', function () { S.description = meta.description; });
    s.appendChild(h('div', { class: 'pdfd-field' }, [h('label', { text: 'Code (for the API)' }), h('code', { class: 'pdfd-codebox', text: "pdf_api.generate('" + S.code + "')" })]));
    var sl = section(p, 'Layout');
    field(sl, 'Kind', S.layout, 'type', 'select', {
      options: [['report', 'Document / report (bands)'], ['labels', 'Labels (a grid of labels)']],
      onChange: function () {
        normalize(S.layout);
        if (S.layout.type === 'labels') { S.activeBand = 'label'; } else { S.activeBand = 'body'; }
        renderCanvas(); renderProps();
      }
    });
    if (S.layout.type !== 'labels') {
      field(sl, 'One document per row of', S.layout, 'repeat', 'select', {
        options: queryOptions(true), rerender: true,
        hint: 'Batch printing: the whole layout repeats for every row of that query (page numbers restart). The other queries read its columns as :Q1_COLUMN.'
      });
    }
    var sf = section(p, 'Default font');
    field(sf, 'Font', S.layout.font, 'family', 'select', { half: true, options: FONT_OPTIONS, onChange: renderCanvas });
    field(sf, 'Size (pt)', S.layout.font, 'size', 'number', { half: true, step: 0.5, onChange: renderCanvas });
    field(sf, 'Colour', S.layout.font, 'color', 'color', { half: true, required: true, dflt: '#000000', onChange: renderCanvas });
    buttonsRow(p, [['fa-file-o', 'Page setup', 'Page size, orientation and margins', pageSetup]]);
    p.appendChild(h('div', { class: 'pdfd-hint pdfd-keys', html:
      '<strong>Keys</strong>: Del delete · Ctrl+D duplicate · Ctrl+C / Ctrl+V copy and paste · arrows move (Shift: 10 pt) · Ctrl+Z / Ctrl+Y undo, redo · Ctrl+S save · Ctrl+P preview · Shift+click select more' }));
  }

  // ------------------------------------------------------------------ page setup
  function overlay(title, content, buttons, wide) {
    var close = function () { ov.remove(); document.removeEventListener('keydown', onKey, true); };
    var onKey = function (ev) { if (ev.key === 'Escape') { ev.stopPropagation(); close(); } };
    var dlg = h('div', { class: 'pdfd-dialog' + (wide ? ' pdfd-dialog--wide' : ''), role: 'dialog', 'aria-modal': 'true', 'aria-label': title }, [
      h('div', { class: 'pdfd-dialog-head' }, [h('strong', { text: title }),
        h('button', { type: 'button', class: 'pdfd-btn pdfd-btn--quiet', 'aria-label': 'Close', onclick: close }, [icon('fa-times')])]),
      h('div', { class: 'pdfd-dialog-body' }, [content]),
      buttons ? h('div', { class: 'pdfd-dialog-foot' }, buttons.map(function (b) {
        return h('button', { type: 'button', class: 'pdfd-btn' + (b.hot ? ' pdfd-btn--hot' : ''), onclick: function () { if (b.fn() !== false) { close(); } } }, [b.label]);
      })) : null]);
    var ov = h('div', { class: 'pdfd-overlay', onmousedown: function (ev) { if (ev.target === ov) { close(); } } }, [dlg]);
    document.addEventListener('keydown', onKey, true);
    root.appendChild(ov);
    var first = dlg.querySelector('input, select, button');
    if (first) { first.focus(); }
    return { close: close, el: dlg };
  }

  function pageSetup() {
    var p = S.layout.page;
    var w = clone(p);
    var lab = S.layout.labels ? clone(S.layout.labels) : null;
    var u = function () { return w.unit; };
    var tu = function (pt) { return round(pt / PT[u()], u() === 'pt' ? 1 : 2); };
    var body = h('div', { class: 'pdfd-setup' });
    var sizeSel = h('select', { class: 'pdfd-input', id: 'pdfd-ps-size' });
    Object.keys(SIZES).concat(['Custom']).forEach(function (k) {
      var o = h('option', { value: k, text: k === 'Custom' ? 'Custom size' : k + ' (' + (k.indexOf('Letter') >= 0 || k === 'Legal' || k === 'Tabloid' || k === 'Executive' || k.indexOf('#') >= 0 ? round(SIZES[k][0] / 72, 2) + ' × ' + round(SIZES[k][1] / 72, 2) + ' in' : round(SIZES[k][0] / PT.mm, 0) + ' × ' + round(SIZES[k][1] / PT.mm, 0) + ' mm') + ')' });
      if (k === w.size) { o.selected = true; }
      sizeSel.appendChild(o);
    });
    var orient = h('div', { class: 'pdfd-seg', role: 'radiogroup', 'aria-label': 'Orientation' });
    var unitSel = h('select', { class: 'pdfd-input', id: 'pdfd-ps-unit' }, [['mm', 'Millimetres'], ['in', 'Inches'], ['pt', 'Points']].map(function (o) {
      var e = h('option', { value: o[0], text: o[1] }); if (o[0] === w.unit) { e.selected = true; } return e;
    }));
    var wIn = h('input', { type: 'number', class: 'pdfd-input', id: 'pdfd-ps-w', step: 'any' });
    var hIn = h('input', { type: 'number', class: 'pdfd-input', id: 'pdfd-ps-h', step: 'any' });
    var mIn = {};
    ['top', 'right', 'bottom', 'left'].forEach(function (k) { mIn[k] = h('input', { type: 'number', class: 'pdfd-input', id: 'pdfd-ps-m' + k, step: 'any' }); });
    var labIn = {};
    function refresh() {
      orient.innerHTML = '';
      [['portrait', 'fa-file-o', 'Portrait'], ['landscape', 'fa-file-o fa-rotate-90', 'Landscape']].forEach(function (o) {
        orient.appendChild(h('button', {
          type: 'button', role: 'radio', 'aria-checked': w.orientation === o[0] ? 'true' : 'false', class: 'pdfd-btn pdfd-btn--small' + (w.orientation === o[0] ? ' is-on' : ''),
          onclick: function () {
            if (w.orientation !== o[0]) { var t = w.width; w.width = w.height; w.height = t; w.orientation = o[0]; }
            refresh();
          }
        }, [icon(o[1]), ' ' + o[2]]));
      });
      wIn.value = tu(w.width); hIn.value = tu(w.height);
      wIn.disabled = hIn.disabled = w.size !== 'Custom';
      ['top', 'right', 'bottom', 'left'].forEach(function (k) { mIn[k].value = tu(w.margin[k]); });
      Object.keys(labIn).forEach(function (k) { labIn[k].value = ['across', 'down'].indexOf(k) >= 0 ? lab[k] : tu(lab[k]); });
      body.querySelectorAll('.pdfd-unit').forEach(function (x) { x.textContent = u(); });
    }
    sizeSel.addEventListener('change', function () {
      w.size = sizeSel.value;
      if (SIZES[w.size]) {
        var s = SIZES[w.size];
        w.width = w.orientation === 'landscape' ? s[1] : s[0];
        w.height = w.orientation === 'landscape' ? s[0] : s[1];
      }
      refresh();
    });
    unitSel.addEventListener('change', function () { w.unit = unitSel.value; refresh(); });
    wIn.addEventListener('input', function () { w.width = num(wIn.value, 0) * PT[u()]; });
    hIn.addEventListener('input', function () { w.height = num(hIn.value, 0) * PT[u()]; });
    ['top', 'right', 'bottom', 'left'].forEach(function (k) { mIn[k].addEventListener('input', function () { w.margin[k] = num(mIn[k].value, 0) * PT[u()]; }); });
    var fld = function (label, input, id, withUnit) {
      return h('div', { class: 'pdfd-field pdfd-field--half' }, [h('label', { for: id }, [label, withUnit ? h('span', {}, [' (', h('span', { class: 'pdfd-unit', text: u() }), ')']) : null]), input]);
    };
    body.appendChild(h('div', { class: 'pdfd-setup-grid' }, [
      h('div', { class: 'pdfd-field' }, [h('label', { for: 'pdfd-ps-size', text: 'Page size' }), sizeSel]),
      h('div', { class: 'pdfd-field' }, [h('label', { text: 'Orientation' }), orient]),
      fld('Width', wIn, 'pdfd-ps-w', true), fld('Height', hIn, 'pdfd-ps-h', true),
      h('div', { class: 'pdfd-field' }, [h('label', { for: 'pdfd-ps-unit', text: 'Units of the designer' }), unitSel])
    ]));
    body.appendChild(h('h4', { class: 'pdfd-setup-h', text: 'Margins' }));
    body.appendChild(h('div', { class: 'pdfd-setup-grid' }, ['top', 'right', 'bottom', 'left'].map(function (k) {
      return fld(k.charAt(0).toUpperCase() + k.slice(1), mIn[k], 'pdfd-ps-m' + k, true);
    })));
    if (lab) {
      body.appendChild(h('h4', { class: 'pdfd-setup-h', text: 'Labels' }));
      var qs = h('select', { class: 'pdfd-input', id: 'pdfd-ps-lq' }, queryOptions().map(function (o) { var e = h('option', { value: o[0], text: o[1] }); if (o[0] === lab.query) { e.selected = true; } return e; }));
      qs.addEventListener('change', function () { lab.query = qs.value; });
      var grid = h('div', { class: 'pdfd-setup-grid' }, [h('div', { class: 'pdfd-field' }, [h('label', { for: 'pdfd-ps-lq', text: 'A label for every row of' }), qs])]);
      [['across', 'Labels across', false], ['down', 'Labels down', false], ['width', 'Label width', true], ['height', 'Label height', true], ['gapX', 'Gap across', true], ['gapY', 'Gap down', true]].forEach(function (d) {
        var inp = labIn[d[0]] = h('input', { type: 'number', class: 'pdfd-input', id: 'pdfd-ps-l' + d[0], step: d[2] ? 'any' : '1', min: d[2] ? null : '1' });
        inp.addEventListener('input', function () { lab[d[0]] = d[2] ? num(inp.value, 0) * PT[u()] : Math.max(1, parseInt(inp.value, 10) || 1); });
        grid.appendChild(fld(d[1], inp, 'pdfd-ps-l' + d[0], d[2]));
      });
      var outl = h('input', { type: 'checkbox', class: 'pdfd-check', id: 'pdfd-ps-lo' });
      outl.checked = !!lab.outline;
      outl.addEventListener('change', function () { lab.outline = outl.checked; });
      grid.appendChild(h('div', { class: 'pdfd-field pdfd-field--check' }, [outl, h('label', { for: 'pdfd-ps-lo', text: 'Print a dashed outline (for test prints)' })]));
      grid.appendChild(h('div', { class: 'pdfd-fhint', text: 'The first label starts at the top and left margins. Parameter LABEL_START skips the used labels of a sheet.' }));
      body.appendChild(grid);
    }
    refresh();
    overlay('Page setup', body, [
      { label: 'Cancel', fn: function () { } },
      {
        label: 'Apply', hot: true, fn: function () {
          if (!(w.width > 20 && w.height > 20)) { toast('Give the page a width and a height.', true); return false; }
          if (w.margin.left + w.margin.right >= w.width - 20 || w.margin.top + w.margin.bottom >= w.height - 20) { toast('The margins leave no room on the page.', true); return false; }
          checkpoint();
          S.layout.page = w;
          if (lab) { S.layout.labels = lab; S.layout.bands.label.height = lab.height; }
          setDirty();
          renderCanvas();
          renderProps();
        }
      }]);
  }

  // ------------------------------------------------------------------ save and preview
  function payload() {
    allElements().forEach(function (x) { if (x.el.type === 'table') { x.el.h = tableHeight(x.el); } });
    return {
      name: S.name, description: S.description, layout: S.layout,
      queries: S.queries.map(function (q) { return { alias: q.alias, title: q.title || '', sql: q.sql || '' }; })
    };
  }

  function save() {
    return ajax('SAVE_REPORT', { x01: S.id, p_clob_01: JSON.stringify(payload()) }).then(function (r) {
      S.savedAt = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setDirty(false);
      toast('Saved');
    }, function (err) { toast('Not saved: ' + err, true); });
  }

  function preview() {
    var pl = payload();
    var params = {};
    Object.keys(S.layout.params || {}).forEach(function (k) { params[k] = S.layout.params[k]; });
    pl.params = params;
    var wait = h('div', { class: 'pdfd-busy', role: 'status' }, [icon('fa-spinner fa-anim-spin'), ' Making the PDF ...']);
    root.appendChild(wait);
    ajax('PREVIEW', { p_clob_01: JSON.stringify(pl) }).then(function (r) {
      wait.remove();
      var bin = atob(r.pdf);
      var bytes = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) { bytes[i] = bin.charCodeAt(i); }
      var url = URL.createObjectURL(new Blob([bytes], { type: 'application/pdf' }));
      var frame = h('iframe', { class: 'pdfd-pdf', src: url, title: 'PDF preview' });
      var info = h('div', { class: 'pdfd-previewinfo', text: r.pages + ' page' + (r.pages === 1 ? '' : 's') + ' · ' + Math.round(r.bytes / 1024) + ' KB · made in ' + r.ms + ' ms' });
      var dlg = overlay('Preview - ' + S.name, h('div', { class: 'pdfd-previewwrap' }, [info, frame]), [
        { label: 'Open in a new tab', fn: function () { window.open(url, '_blank'); return false; } },
        { label: 'Download', fn: function () { var a = h('a', { href: url, download: S.code.toLowerCase() + '.pdf' }); root.appendChild(a); a.click(); a.remove(); return false; } },
        { label: 'Close', hot: true, fn: function () { } }], true);
      dlg.el.classList.add('pdfd-dialog--preview');
    }, function (err) {
      wait.remove();
      toast('Preview failed: ' + err, true);
    });
  }

  // ------------------------------------------------------------------ keyboard, clipboard
  function onKey(ev) {
    if (!root || !document.body.contains(root) || root.querySelector('.pdfd-overlay')) { return; }
    var tag = (ev.target.tagName || '').toLowerCase();
    var inField = tag === 'input' || tag === 'textarea' || tag === 'select' || ev.target.isContentEditable;
    var mod = ev.ctrlKey || ev.metaKey;
    if (mod && ev.key.toLowerCase() === 's') { ev.preventDefault(); save(); return; }
    if (mod && ev.key.toLowerCase() === 'p') { ev.preventDefault(); preview(); return; }
    if (inField) { return; }
    if (mod && ev.key.toLowerCase() === 'z') { ev.preventDefault(); if (ev.shiftKey) { redo(); } else { undo(); } return; }
    if (mod && ev.key.toLowerCase() === 'y') { ev.preventDefault(); redo(); return; }
    if (mod && ev.key.toLowerCase() === 'd') { ev.preventDefault(); duplicate(); return; }
    if (mod && ev.key.toLowerCase() === 'c' && S.sel.length) { S.clip = selected().map(function (f) { return clone(f.el); }); return; }
    if (mod && ev.key.toLowerCase() === 'v' && S.clip && S.clip.length) {
      ev.preventDefault();
      checkpoint();
      var ids = [];
      var b = S.activeBand || 'body';
      S.clip.forEach(function (c) { var n = clone(c); n.id = newId(); n.x = snap(n.x + 10); n.y = snap(n.y + 10); band(b).elements.push(n); ids.push(n.id); });
      S.clip = S.clip.map(function (c) { var n = clone(c); n.x += 10; n.y += 10; return n; });
      setDirty();
      select(ids);
      return;
    }
    if (mod && ev.key.toLowerCase() === 'a') { ev.preventDefault(); select(band(S.activeBand || 'body').elements.map(function (e) { return e.id; })); return; }
    if ((ev.key === 'Delete' || ev.key === 'Backspace') && S.sel.length) { ev.preventDefault(); removeSelected(); return; }
    if (ev.key === 'Escape') { select([]); return; }
    var step = ev.shiftKey ? 10 : 1;
    if (ev.key === 'ArrowLeft') { ev.preventDefault(); nudge(-step, 0); }
    if (ev.key === 'ArrowRight') { ev.preventDefault(); nudge(step, 0); }
    if (ev.key === 'ArrowUp') { ev.preventDefault(); nudge(0, -step); }
    if (ev.key === 'ArrowDown') { ev.preventDefault(); nudge(0, step); }
  }

  // a click on a field chip while a text property has the focus inserts the token there
  function onChipClick(ev) {
    var chip = ev.target.closest && ev.target.closest('.pdfd-chip');
    if (!chip || !S.lastText || document.activeElement !== S.lastText) { return; }
    ev.preventDefault();
    var token = chip.getAttribute('title').split(' - ')[0];
    var t = S.lastText;
    var s = t.selectionStart === undefined || t.selectionStart === null ? t.value.length : t.selectionStart;
    var e = t.selectionEnd === undefined || t.selectionEnd === null ? s : t.selectionEnd;
    t.value = t.value.slice(0, s) + token + t.value.slice(e);
    t.dispatchEvent(new Event('input'));
    t.focus();
    t.selectionStart = t.selectionEnd = s + token.length;
  }

  // ------------------------------------------------------------------ start
  function init(opts) {
    root = typeof opts.el === 'string' ? document.querySelector(opts.el) : opts.el;
    if (!root) { return; }
    S = {
      opts: opts, id: opts.reportId, code: '', name: '', description: '', layout: null, queries: [],
      cols: {}, sel: [], undo: [], redo: [], zoom: 1, snap: true, grid: 5, tab: 'queries',
      activeBand: 'body', bandSel: null, dirty: false, fieldSeq: 0, images: []
    };
    try { S.zoom = parseFloat(window.localStorage.getItem('pdfd.zoom')) || 1; } catch (x) { S.zoom = 1; }
    buildShell();
    bindTips();
    if (!document.getElementById('pdfd-masks')) {
      document.body.appendChild(h('datalist', { id: 'pdfd-masks' }, MASKS.map(function (m) { return h('option', { value: m }); })));
    }
    root.appendChild(h('div', { class: 'pdfd-busy', role: 'status' }, [icon('fa-spinner fa-anim-spin'), ' Loading ...']));
    $.when(ajax('LOAD_REPORT', { x01: S.id }), loadImages()).then(function (r) {
      root.querySelectorAll('.pdfd-busy').forEach(function (b) { b.remove(); });
      S.code = r.code; S.name = r.name; S.description = r.description || '';
      S.layout = normalize(r.layout);
      S.queries = r.queries || [];
      if (!S.queries.length) { S.queries.push({ alias: 'Q1', title: '', sql: 'select *\n  from dual' }); }
      S.activeBand = S.layout.type === 'labels' ? 'label' : 'body';
      // a single label is small: start zoomed in
      if (S.layout.type === 'labels' && S.zoom < 2) { S.zoom = 2; }
      renderAll();
      setDirty(false);
      // the fields of every query
      $.when.apply($, S.queries.map(function (q) { return describe(q); })).always(function () { renderCanvas(); });
    }, function (err) {
      root.querySelectorAll('.pdfd-busy').forEach(function (b) { b.remove(); });
      root.appendChild(h('div', { class: 'pdfd-fatal', role: 'alert', text: 'The report could not be loaded: ' + err }));
    });
    document.addEventListener('keydown', onKey);
    root.addEventListener('mousedown', onChipClick);
    window.addEventListener('beforeunload', function (ev) {
      if (S && S.dirty) { ev.preventDefault(); ev.returnValue = ''; }
    });
    window.addEventListener('pagehide', function () { try { window.localStorage.setItem('pdfd.zoom', String(S.zoom)); } catch (x) { /* private mode */ } });
  }

  return { init: init, state: function () { return S; } };
})(apex.jQuery);
