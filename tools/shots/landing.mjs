// Screenshots for the VinAura landing page, from the no-login test copy (application 2099). Nothing is saved.
const openReport = (name) => ({
  eval: `[...document.querySelectorAll('a')].find((a) => a.textContent.trim() === ${JSON.stringify(name)}).click()`,
  navigates: true,
});
const designerReady = [{ waitFor: '.pdfd-el' }, { wait: 1800 }];
// the sample invoice as designed (the saved copy may have been changed by hand); in the browser only, never saved
const asDesigned = { eval: `(() => { const s = pdfd.state();
  Object.values(s.layout.bands).forEach((b) => b.elements.forEach((e) => { if (e.font === 'arialblack') delete e.font; }));
  s.dirty = false; document.querySelector('.pdfd-zoom').click(); })()`, wait: 400 };
// select an element of the canvas the way a mouse click does
const pick = (test) => ({
  eval: `(() => { const e = [...document.querySelectorAll('.pdfd-el')].find((d) => ${test});
    e.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
    document.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })); })()`,
  wait: 400,
});
const rowLink = (text, n) => ({
  eval: `[...document.querySelectorAll('.a-IRR-table td a')].filter((a) => a.textContent.trim() === ${JSON.stringify(text)})[${n}].click()`,
});

export default [
  // the designer: the invoice with its table selected
  { name: 'designer-invoice', page: 1,
    steps: [openReport('Tax Invoice'), ...designerReady, asDesigned, pick("d.classList.contains('pdfd-el--table')")] },
  // the fields of the queries, a field selected
  { name: 'designer-fields', page: 1,
    steps: [openReport('Tax Invoice'), ...designerReady, asDesigned,
            { eval: "[...document.querySelectorAll('.pdfd-tab')].find((t) => t.textContent === 'Fields').click()", wait: 300 },
            pick("/CUSTOMER_NAME/.test(d.textContent)")] },
  // the queries tab, nothing selected (report properties)
  { name: 'designer-queries', page: 1, steps: [openReport('Tax Invoice'), ...designerReady, asDesigned] },
  // a label layout
  { name: 'designer-labels', page: 1,
    steps: [openReport('Product Labels (3 x 8)'), ...designerReady, pick("d.classList.contains('pdfd-el--barcode')")] },
  // page setup
  { name: 'designer-page-setup', page: 1,
    steps: [openReport('Tax Invoice'), ...designerReady, asDesigned,
            { eval: "document.querySelector('.pdfd-btn[data-tip^=\"Page setup\"]').click()", wait: 500 }] },
  // preview in the designer
  { name: 'designer-preview', page: 1,
    steps: [openReport('Tax Invoice'), ...designerReady, asDesigned,
            { eval: "document.querySelector('.pdfd-btn[data-tip^=\"Preview\"]').click()", wait: 5000 }] },
  // the demo: invoice list, invoice screen, the PDF dialog
  { name: 'demo-invoices', page: 10 },
  { name: 'demo-invoice-edit', page: 10,
    steps: [{ eval: "[...document.querySelectorAll('.a-IRR-table td a')].map((a) => a.href).filter((h) => /p11_invoice_id=1005/.test(h)).forEach((h, i) => { if (!i) location.href = h; })", navigates: true, wait: 1200 }] },
  // the invoices of a period (INVOICE_BATCH, the same invoice layout) in the dialog
  { name: 'demo-dialog', page: 10,
    steps: [{ set: 'P10_DATE_FROM', value: '09-SEP-2026', wait: 1500 }, { set: 'P10_DATE_TO', value: '09-SEP-2026', wait: 2500 },
            { eval: "[...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Preview all').click()", wait: 6500 }] },
  { name: 'demo-statement-dialog', page: 20, steps: [rowLink('Preview', 4), { wait: 6000 }] },
  // try the API
  { name: 'try-api', page: 4,
    steps: [{ set: 'P4_REPORT', value: 'CUSTOMER_STATEMENT' }, { set: 'P4_PARAMS', value: 'P21_CUSTOMER_ID=3' },
            { eval: "document.querySelector('#pdf-frame') && [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === 'Generate PDF').click()", wait: 5000 }] },
];
