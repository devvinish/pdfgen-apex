#!/usr/bin/env python3
"""Writes sql/60_samples.sql: the sample reports (INVOICE, INVOICE_BATCH, PRODUCT_LABELS) and the
demo logo. The layouts are the same JSON the designer saves."""
import base64
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLUE = '#1F4E79'
GREY = '#5B6573'
_n = [0]


def eid():
    _n[0] += 1
    return 'e%d' % _n[0]


def text(x, y, w, h, t, **k):
    return dict(id=eid(), type='text', x=x, y=y, w=w, h=h, text=t, **k)


def box(x, y, w, h, **k):
    return dict(id=eid(), type='box', x=x, y=y, w=w, h=h, **k)


def line(x, y, w, h, **k):
    return dict(id=eid(), type='line', x=x, y=y, w=w, h=h, **k)


def page(size='A4', orientation='portrait', margin=30):
    w, h = {'A4': (595.28, 841.89), 'Letter': (612, 792)}[size]
    if orientation == 'landscape':
        w, h = h, w
    return dict(size=size, orientation=orientation, width=w, height=h, unit='mm',
                margin=dict(top=margin, right=margin, bottom=margin, left=margin))


def company_header(cw, title, number_token):
    return [
        dict(id=eid(), type='image', x=0, y=0, w=56, h=56, src='demo-logo', fit='contain'),
        text(66, 4, 290, 22, 'Northwind Medical Supplies Pvt. Ltd.', size=15, bold=True, color=BLUE),
        text(66, 26, 290, 30, '12 MG Road, Bengaluru 560001, Karnataka\nGSTIN 29ABCDE1234F1Z5  ·  +91 80 1234 5678\naccounts@northwind.example',
             size=7.5, color=GREY),
        box(cw - 170, 0, 170, 56, bg=BLUE, radius=8),
        text(cw - 170, 8, 170, 22, title, size=15, bold=True, color='#FFFFFF', align='center'),
        text(cw - 170, 30, 170, 16, number_token, size=9.5, color='#FFFFFF', align='center'),
        line(0, 66, cw, 0, color=BLUE, lineWidth=1.5),
    ]


def invoice_layout(repeat=False):
    _n[0] = 0
    cw = 535.28
    page_header = [
        dict(id=eid(), type='image', x=0, y=0, w=56, h=56, src='demo-logo', fit='contain'),
        text(66, 4, 290, 22, 'Northwind Medical Supplies Pvt. Ltd.', size=15, bold=True, color=BLUE),
        text(66, 26, 290, 30, '12 MG Road, Bengaluru 560001, Karnataka\nGSTIN 29ABCDE1234F1Z5  ·  +91 80 1234 5678\naccounts@northwind.example',
             size=7.5, color=GREY),
        box(cw - 170, 0, 170, 56, bg=BLUE, radius=8),
        text(cw - 170, 8, 170, 22, 'TAX INVOICE', size=16, bold=True, color='#FFFFFF', align='center'),
        text(cw - 170, 30, 170, 16, '{Q1.INVOICE_NO}', size=10, color='#FFFFFF', align='center'),
        line(0, 66, cw, 0, color=BLUE, lineWidth=1.5),
    ]
    report_header = [
        box(0, 4, 262, 78, borderWidth=0.75, borderColor='#C5CED9', radius=6),
        text(8, 9, 200, 12, 'BILL TO', size=7, bold=True, color=GREY),
        text(8, 21, 246, 14, '{Q1.CUSTOMER_NAME}', size=10.5, bold=True),
        text(8, 36, 246, 44, '{Q1.ADDRESS}\n{Q1.CITY}\nGSTIN: {Q1.GSTIN}   Phone: {Q1.PHONE}', size=8, lineHeight=1.3),
        box(273, 4, cw - 273, 78, borderWidth=0.75, borderColor='#C5CED9', radius=6),
        text(281, 11, 90, 14, 'Invoice No.', size=8, color=GREY),
        text(371, 11, cw - 381, 14, '{Q1.INVOICE_NO}', size=8.5, bold=True, align='right'),
        text(281, 27, 90, 14, 'Invoice Date', size=8, color=GREY),
        text(371, 27, cw - 381, 14, '{Q1.INVOICE_DATE}', format='DD-Mon-YYYY', size=8.5, bold=True, align='right'),
        text(281, 43, 90, 14, 'Due Date', size=8, color=GREY),
        text(371, 43, cw - 381, 14, '{Q1.DUE_DATE}', format='DD-Mon-YYYY', size=8.5, bold=True, align='right'),
        text(281, 59, 90, 14, 'Place of Supply', size=8, color=GREY),
        text(371, 59, cw - 381, 14, '{Q1.STATE}', size=8.5, bold=True, align='right'),
    ]
    cols = [
        dict(title='#', field='SNO', width=22, align='center'),
        dict(title='Item / Description', field='DESCRIPTION', width=178),
        dict(title='HSN', field='HSN', width=40, align='center'),
        dict(title='Qty', field='QTY', width=40, align='right', format='FM999G990D00'),
        dict(title='Rate', field='UNIT_PRICE', width=56, align='right', format='FM999G999G990D00'),
        dict(title='Disc %', field='DISCOUNT_PCT', width=36, align='right', format='FM990D0'),
        dict(title='GST %', field='TAX_RATE', width=36, align='right', format='FM990'),
        dict(title='Taxable', field='TAXABLE', width=62, align='right', format='FM999G999G990D00', total='sum'),
        dict(title='Amount', field='AMOUNT', width=65.28, align='right', format='FM999G999G990D00', total='sum'),
    ]
    body = [
        dict(id=eid(), type='table', x=0, y=10, w=cw, h=44, query='Q2', columns=cols, size=8,
             header=dict(show=True, height=20, bg=BLUE, color='#FFFFFF', bold=True, repeat=True, size=8),
             rowHeight=17, padding=4, zebra='#F3F6FA', grid='horizontal', gridColor='#D5DCE6', gridWidth=0.5,
             totals=dict(show=True, label='Total', bg='#E4EBF3', bold=True), noData='No items on this invoice.'),
    ]
    summary = [
        text(0, 10, 225, 12, 'Amount in words', size=7, bold=True, color=GREY),
        text(0, 22, 225, 28, 'Rupees {WORDS(Q3.GRAND_TOTAL)} only', size=9, italic=True),
        text(0, 52, 225, 12, 'Notes', size=7, bold=True, color=GREY, printWhen='{Q1.NOTES}'),
        text(0, 64, 225, 40, '{Q1.NOTES}', size=8, printWhen='{Q1.NOTES}'),
        box(cw - 200, 10, 200, 96, borderWidth=0.75, borderColor=BLUE, radius=6),
        text(cw - 192, 16, 100, 16, 'Taxable value', size=8.5, color=GREY),
        text(cw - 100, 16, 92, 16, '{Q3.TAXABLE|FM999G999G990D00}', size=8.5, align='right'),
        text(cw - 192, 34, 100, 16, 'GST', size=8.5, color=GREY),
        text(cw - 100, 34, 92, 16, '{Q3.TAX|FM999G999G990D00}', size=8.5, align='right'),
        text(cw - 192, 52, 100, 16, 'Round off', size=8.5, color=GREY),
        text(cw - 100, 52, 92, 16, '{Q3.ROUND_OFF|FM999G990D00}', size=8.5, align='right'),
        box(cw - 200, 76, 200, 30, bg=BLUE, radius=6),
        box(cw - 200, 76, 200, 12, bg=BLUE),
        text(cw - 192, 76, 100, 30, 'Grand Total', size=10, bold=True, color='#FFFFFF', valign='middle'),
        text(cw - 110, 76, 102, 30, 'Rs. {Q3.GRAND_TOTAL|FM999G999G990D00}', size=11, bold=True,
             color='#FFFFFF', align='right', valign='middle'),
        dict(id=eid(), type='ellipse', x=cw - 296, y=56, w=84, h=44, borderWidth=2, borderColor='#2E7D32',
             printWhen='{Q1.STATUS} = PAID'),
        text(cw - 296, 56, 84, 44, 'PAID', size=16, bold=True, color='#2E7D32', align='center', valign='middle',
             printWhen='{Q1.STATUS} = PAID'),
        text(cw - 200, 122, 200, 12, 'For Northwind Medical Supplies Pvt. Ltd.', size=8, align='right'),
        line(cw - 140, 162, 140, 0, color='#333333', lineWidth=0.5),
        text(cw - 200, 164, 200, 12, 'Authorised Signatory', size=7, align='right', color=GREY),
    ]
    page_footer = [
        line(0, 4, cw, 0, color='#C5CED9', lineWidth=0.5),
        text(0, 8, 360, 14, 'Thank you for your business. This is a computer generated invoice.', size=7, color=GREY),
        text(cw - 150, 8, 150, 14, 'Page {PAGE} of {PAGES}', size=7, color=GREY, align='right'),
    ]
    return dict(
        version=1, type='report', repeat='Q1' if repeat else '',
        page=page(), font=dict(family='helvetica', size=9, color='#1D2530'),
        params={'P11_INVOICE_ID': '1001'} if not repeat else {'P10_DATE_FROM': '01-SEP-2026', 'P10_DATE_TO': '30-SEP-2026'},
        bands=dict(
            pageHeader=dict(height=74, printOn='all', elements=page_header),
            reportHeader=dict(height=90, elements=report_header),
            body=dict(height=60, elements=body),
            summary=dict(height=182, elements=summary),
            pageFooter=dict(height=24, printOn='all', elements=page_footer)))


INVOICE_Q1 = """select i.invoice_no, i.invoice_date, i.due_date, i.status, i.notes,
       c.name customer_name, c.address, c.city || ' - ' || c.pincode || ', ' || c.state city,
       c.state, c.gstin, c.phone
  from pdf_demo_invoices i
  join pdf_demo_customers c on c.customer_id = i.customer_id
 where i.invoice_id = :P11_INVOICE_ID"""

LINES = """select l.line_no sno,
       nvl(l.description, p.name) description, p.hsn, l.qty, l.unit_price, l.discount_pct, p.tax_rate,
       round(l.qty * l.unit_price * (1 - l.discount_pct / 100), 2) taxable,
       round(l.qty * l.unit_price * (1 - l.discount_pct / 100) * (1 + p.tax_rate / 100), 2) amount
  from pdf_demo_invoice_lines l
  join pdf_demo_products p on p.product_id = l.product_id
 where l.invoice_id = %s
 order by l.line_no"""

TOTALS = """with t as (
  select sum(round(l.qty * l.unit_price * (1 - l.discount_pct / 100), 2)) taxable,
         sum(round(l.qty * l.unit_price * (1 - l.discount_pct / 100) * p.tax_rate / 100, 2)) tax
    from pdf_demo_invoice_lines l
    join pdf_demo_products p on p.product_id = l.product_id
   where l.invoice_id = %s)
select taxable, tax,
       round(taxable + tax) - (taxable + tax) round_off,
       round(taxable + tax) grand_total,
       'Rupees ' || initcap(to_char(to_date(round(taxable + tax), 'J'), 'Jsp')) || ' only' amount_words
  from t"""

BATCH_Q1 = """select i.invoice_id, i.invoice_no, i.invoice_date, i.due_date, i.status, i.notes,
       c.name customer_name, c.address, c.city || ' - ' || c.pincode || ', ' || c.state city,
       c.state, c.gstin, c.phone
  from pdf_demo_invoices i
  join pdf_demo_customers c on c.customer_id = i.customer_id
 where i.invoice_date between to_date(:P10_DATE_FROM, 'DD-MON-YYYY') and to_date(:P10_DATE_TO, 'DD-MON-YYYY')
   and i.status <> 'CANCELLED'
 order by i.invoice_date, i.invoice_no"""


def labels_layout():
    _n[0] = 0
    # A4 sheet of 3 x 8 labels, 63.5 x 33.9 mm
    mm = 72 / 25.4
    lw, lh = 63.5 * mm, 33.9 * mm
    label = [
        box(2, 2, lw - 4, lh - 4, borderWidth=0.5, borderColor='#C5CED9', radius=6),
        text(8, 6, lw - 16, 12, '{Q1.NAME}', size=8, bold=True, wrap=False),
        text(8, 18, lw - 16, 10, '{Q1.SKU}  ·  {Q1.CATEGORY}', size=6.5, color=GREY),
        dict(id=eid(), type='barcode', x=4, y=32, w=lw * 0.62, h=topt(34, lh), text='{Q1.SKU}', showText=True, size=6),
        text(lw * 0.62, 36, lw * 0.38 - 8, 12, 'MRP', size=6, color=GREY, align='right'),
        text(lw * 0.62 - 10, 46, lw * 0.38 + 2, 18, 'Rs. {Q1.PRICE|FM99G990}', size=11, bold=True, align='right', color=BLUE),
        text(lw * 0.62, 66, lw * 0.38 - 8, 10, 'incl. {Q1.TAX_RATE}% GST', size=5.5, color=GREY, align='right'),
    ]
    p = page(margin=0)
    p['margin'] = dict(top=12.9 * mm, right=7.2 * mm, bottom=12.9 * mm, left=7.2 * mm)
    return dict(
        version=1, type='labels', repeat='', page=p, font=dict(family='helvetica', size=8, color='#1D2530'),
        labels=dict(query='Q1', across=3, down=8, width=lw, height=lh, gapX=2.5 * mm, gapY=0, outline=False),
        params={'P30_CATEGORY': '', 'P30_SKU': '', 'P30_COPIES': '1'},
        bands=dict(label=dict(height=lh, elements=label)))


def topt(v, lh):
    return round(min(v, lh - 36), 2)


LABELS_Q1 = """select p.sku, p.name, p.category, p.price, p.tax_rate
  from pdf_demo_products p
 cross join (select level copy_no from dual connect by level <= to_number(nvl(:P30_COPIES, '1'))) c
 where p.category = nvl(:P30_CATEGORY, p.category)
   and p.sku = nvl(:P30_SKU, p.sku)
 order by p.category, p.name, c.copy_no"""


STATEMENT_Q1 = """select c.customer_id, c.name customer_name, c.address, c.city || ' - ' || c.pincode || ', ' || c.state city,
       c.gstin, c.phone, c.email
  from pdf_demo_customers c
 where c.customer_id = :P21_CUSTOMER_ID"""

STATEMENT_Q2 = """with inv as (
  select i.invoice_no, i.invoice_date, i.due_date, i.status,
         sum(round(l.qty * l.unit_price * (1 - l.discount_pct / 100) * (1 + p.tax_rate / 100), 2)) amount
    from pdf_demo_invoices i
    join pdf_demo_invoice_lines l on l.invoice_id = i.invoice_id
    join pdf_demo_products p on p.product_id = l.product_id
   where i.customer_id = :P21_CUSTOMER_ID
   group by i.invoice_no, i.invoice_date, i.due_date, i.status)
select invoice_no, invoice_date, due_date, initcap(status) status, amount,
       case when status = 'PAID' then amount else 0 end paid,
       case when status = 'DUE' then amount else 0 end balance,
       case when status = 'DUE' and due_date < trunc(sysdate) then trunc(sysdate) - due_date end overdue_days
  from inv
 order by invoice_date, invoice_no"""


def statement_layout():
    _n[0] = 0
    cw = 535.28
    money = 'FM999G999G990D00'
    report_header = [
        box(0, 4, 300, 74, borderWidth=0.75, borderColor='#C5CED9', radius=6),
        text(8, 9, 200, 12, 'STATEMENT FOR', size=7, bold=True, color=GREY),
        text(8, 21, 284, 14, '{Q1.CUSTOMER_NAME}', size=10.5, bold=True),
        text(8, 36, 284, 40, '{Q1.ADDRESS}\n{Q1.CITY}\nGSTIN: {Q1.GSTIN}', size=8, lineHeight=1.3),
        box(312, 4, cw - 312, 74, bg='#F3F6FA', radius=6),
        text(320, 10, 110, 14, 'Statement date', size=8, color=GREY),
        text(420, 10, cw - 428, 14, '{TODAY|DD-Mon-YYYY}', size=8.5, bold=True, align='right'),
        text(320, 26, 110, 14, 'Invoices', size=8, color=GREY),
        text(420, 26, cw - 428, 14, '{COUNT(Q2)}', size=8.5, bold=True, align='right'),
        text(320, 42, 110, 14, 'Total billed', size=8, color=GREY),
        text(420, 42, cw - 428, 14, '{SUM(Q2.AMOUNT)|' + money + '}', size=8.5, bold=True, align='right'),
        text(320, 58, 110, 14, 'Balance due', size=8, color=GREY),
        text(420, 58, cw - 428, 14, 'Rs. {SUM(Q2.BALANCE)|' + money + '}', size=9, bold=True, align='right', color='#B3261E'),
    ]
    cols = [
        dict(title='Invoice No.', field='INVOICE_NO', width=95),
        dict(title='Date', field='INVOICE_DATE', width=62, format='DD-Mon-YYYY'),
        dict(title='Due', field='DUE_DATE', width=62, format='DD-Mon-YYYY'),
        dict(title='Status', field='STATUS', width=52),
        dict(title='Amount', field='AMOUNT', width=70, align='right', format=money, total='sum'),
        dict(title='Paid', field='PAID', width=65, align='right', format=money, total='sum'),
        dict(title='Balance', field='BALANCE', width=70, align='right', format=money, total='sum'),
        dict(title='Overdue (days)', field='OVERDUE_DAYS', width=59.28, align='right'),
    ]
    body = [
        dict(id=eid(), type='table', x=0, y=10, w=cw, h=44, query='Q2', columns=cols, size=8,
             header=dict(show=True, height=20, bg=BLUE, color='#FFFFFF', bold=True, repeat=True, size=8),
             rowHeight=17, padding=4, zebra='#F3F6FA', grid='horizontal', gridColor='#D5DCE6', gridWidth=0.5,
             totals=dict(show=True, label='Total', bg='#E4EBF3', bold=True), noData='No invoices for this customer.'),
    ]
    summary = [
        box(cw - 220, 12, 220, 40, bg=BLUE, radius=6),
        text(cw - 212, 12, 100, 40, 'Balance due', size=10, bold=True, color='#FFFFFF', valign='middle'),
        text(cw - 130, 12, 122, 40, 'Rs. {SUM(Q2.BALANCE)|' + money + '}', size=12, bold=True, color='#FFFFFF',
             align='right', valign='middle'),
        text(0, 12, 280, 12, 'In words', size=7, bold=True, color=GREY),
        text(0, 24, 280, 28, 'Rupees {WORDS(SUM(Q2.BALANCE))} only', size=9, italic=True),
        text(0, 64, cw, 30, 'Please pay the balance by NEFT to Northwind Medical Supplies Pvt. Ltd., HDFC Bank, '
             'A/c 50200012345678, IFSC HDFC0000123. Invoices overdue by more than 30 days attract interest at 18% a year.',
             size=7.5, color=GREY),
    ]
    page_footer = [
        line(0, 4, cw, 0, color='#C5CED9', lineWidth=0.5),
        text(0, 8, 360, 14, 'Statement of account - {Q1.CUSTOMER_NAME}', size=7, color=GREY),
        text(cw - 150, 8, 150, 14, 'Page {PAGE} of {PAGES}', size=7, color=GREY, align='right'),
    ]
    return dict(
        version=1, type='report', repeat='', page=page(), font=dict(family='helvetica', size=9, color='#1D2530'),
        params={'P21_CUSTOMER_ID': '3'},
        bands=dict(
            pageHeader=dict(height=74, printOn='all', elements=company_header(cw, 'STATEMENT', 'of account')),
            reportHeader=dict(height=86, elements=report_header),
            body=dict(height=60, elements=body),
            summary=dict(height=100, elements=summary),
            pageFooter=dict(height=24, printOn='all', elements=page_footer)))


def sq(s):
    """a SQL expression for a long text: to_clob chunks of q'~...~' literals"""
    parts = [s[i:i + 3000] for i in range(0, len(s), 3000)] or ['']
    for p in parts:
        assert '~\'' not in p
    return '\n || '.join("to_clob(q'~%s~')" % p for p in parts)


def report_sql(code, name, desc, layout, queries):
    # added only when missing: a report changed in the designer is never overwritten
    out = ["-- %s" % code,
           "select count(*) into l_n from pdf_reports where code = '%s';" % code,
           "if l_n = 0 then",
           "insert into pdf_reports (code, name, description, layout) values ('%s', q'~%s~', q'~%s~',\n %s);"
           % (code, name, desc, sq(json.dumps(layout, separators=(',', ':'))))]
    for n, (alias, title, sql) in enumerate(queries, 1):
        out.append("insert into pdf_queries (report_id, alias, seq, title, sql_text)\n"
                   "select report_id, '%s', %d, q'~%s~', %s from pdf_reports where code = '%s';"
                   % (alias, n, title, sq(sql), code))
    out.append("end if;")
    return '\n'.join(out)


def main():
    logo = open(os.path.join(ROOT, 'app', 'samples', 'logo.jpg'), 'rb').read()
    b64 = base64.b64encode(logo).decode()
    chunks = [b64[i:i + 3000] for i in range(0, len(b64), 3000)]
    parts = ["-- PDF Report Designer: the sample reports and the demo logo (generated by tools/samples.py)",
             "set define off",
             "declare",
             "  l_b64 clob;",
             "  l_img blob;",
             "  l_raw raw(32767);",
             "  l_pos pls_integer := 1;",
             "  l_n   number;",
             "begin",
             "  select count(*) into l_n from pdf_images where name = 'demo-logo';",
             "  if l_n > 0 then",
             "    return;",
             "  end if;",
             "  dbms_lob.createtemporary(l_b64, true);"]
    for c in chunks:
        parts.append("  dbms_lob.append(l_b64, '%s');" % c)
    parts += ["  dbms_lob.createtemporary(l_img, true);",
              "  while l_pos <= dbms_lob.getlength(l_b64) loop",
              "    l_raw := utl_encode.base64_decode(utl_raw.cast_to_raw(dbms_lob.substr(l_b64, 4000, l_pos)));",
              "    dbms_lob.writeappend(l_img, utl_raw.length(l_raw), l_raw);",
              "    l_pos := l_pos + 4000;",
              "  end loop;",
              "  insert into pdf_images (name, mime_type, width, height, content) values ('demo-logo', 'image/jpeg', 400, 400, l_img);",
              "end;",
              "/",
              "declare",
              "  l_n number;",
              "begin"]
    parts.append(report_sql('INVOICE', 'Tax Invoice', 'A GST tax invoice: logo, bill-to and invoice boxes, '
                            'the items in a table that continues over pages, totals, amount in words, a PAID stamp.',
                            invoice_layout(), [('Q1', 'Invoice header', INVOICE_Q1),
                                               ('Q2', 'Invoice lines', LINES % ':P11_INVOICE_ID'),
                                               ('Q3', 'Totals', TOTALS % ':P11_INVOICE_ID')]))
    parts.append(report_sql('INVOICE_BATCH', 'Tax Invoices (batch)', 'Every invoice of a date range in one PDF: '
                            'the layout repeats for each row of Q1 and the other queries read its columns as :Q1_<COLUMN>.',
                            invoice_layout(repeat=True), [('Q1', 'Invoices of the period', BATCH_Q1),
                                                          ('Q2', 'Lines of the invoice', LINES % ':Q1_INVOICE_ID'),
                                                          ('Q3', 'Totals of the invoice', TOTALS % ':Q1_INVOICE_ID')]))
    parts.append(report_sql('PRODUCT_LABELS', 'Product Labels (3 x 8)', 'Shelf labels on an A4 sheet of 24 '
                            '(63.5 x 33.9 mm): name, SKU, a Code 128 barcode and the price.',
                            labels_layout(), [('Q1', 'Products', LABELS_Q1)]))
    parts.append(report_sql('CUSTOMER_STATEMENT', 'Customer Statement', 'Statement of account of a customer: '
                            'every invoice with what is paid and what is due, the balance in words, overdue days.',
                            statement_layout(), [('Q1', 'Customer', STATEMENT_Q1), ('Q2', 'Invoices', STATEMENT_Q2)]))
    parts += ["commit;", "end;", "/"]
    open(os.path.join(ROOT, 'sql', '60_samples.sql'), 'w').write('\n'.join(parts) + '\n')
    print('sql/60_samples.sql written')


if __name__ == '__main__':
    main()
