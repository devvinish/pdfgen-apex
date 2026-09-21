"""The demo screens of the PDF Report Designer app: invoices, customers and products, each an interactive
report with an edit screen, and the PDF of a row in a dialog, in a new tab or as a download.

Pages
  10 Invoices (IR, batch printing of a period)     11 Invoice (header form + lines grid)
  20 Customers (IR)                                21 Customer (form + its invoices)
  30 Products (IR, shelf labels of a category)     31 Product (form)
  92 Invoice PDF, 93 Statement PDF, 94 Label PDF, 95 Labels PDF, 96 Invoices PDF (modal dialogs)

A PDF dialog has its own items (P92_INVOICE_ID), set by the link or button that opens it, and a URL
region showing an application process in an iframe (f?p=&APP_ID.:0:&SESSION.:APPLICATION_PROCESS=INVOICE_PDF);
the process passes the item to the report:
pdf_api.download('INVOICE', p_params => apex_t_varchar2('P11_INVOICE_ID', :P92_INVOICE_ID)).
"""
from components import T, Page
from emit import attrs

# ------------------------------------------------------------------ the PDF dialogs
# Every report has an application process (Ajax Callback) that sends its PDF, and a modal page whose
# URL region shows that process in an iframe. The reports read their page items (:P11_INVOICE_ID,
# :P21_CUSTOMER_ID, ...) from session state, so nothing else is needed.
APP_PROCESSES = [
    ('INVOICE_PDF', "pdf_api.download('INVOICE',\n"
                    "  p_params   => apex_t_varchar2('P11_INVOICE_ID', :P92_INVOICE_ID),\n"
                    "  p_filename => 'invoice-' || :P92_INVOICE_ID || '.pdf');"),
    ('STATEMENT_PDF', "pdf_api.download('CUSTOMER_STATEMENT',\n"
                      "  p_params   => apex_t_varchar2('P21_CUSTOMER_ID', :P93_CUSTOMER_ID),\n"
                      "  p_filename => 'statement-' || :P93_CUSTOMER_ID || '.pdf');"),
    ('LABEL_PDF', "pdf_api.download('PRODUCT_LABELS',\n"
                  "  p_params   => apex_t_varchar2('P30_SKU', :P94_SKU, 'P30_CATEGORY', null, 'P30_COPIES', 1),\n"
                  "  p_filename => 'label-' || :P94_SKU || '.pdf');"),
    ('LABELS_PDF', "pdf_api.download('PRODUCT_LABELS',\n"
                   "  p_params   => apex_t_varchar2('P30_SKU', null, 'P30_CATEGORY', :P95_CATEGORY, 'P30_COPIES', nvl(:P95_COPIES, 1)),\n"
                   "  p_filename => 'labels-' || nvl(lower(:P95_CATEGORY), 'all') || '.pdf');"),
    ('INVOICES_PDF', "pdf_api.download('INVOICE_BATCH',\n"
                     "  p_params   => apex_t_varchar2('P10_DATE_FROM', :P96_DATE_FROM, 'P10_DATE_TO', :P96_DATE_TO),\n"
                     "  p_filename => 'invoices.pdf');"),
]
DIALOG_CSS = ".t-Dialog-body { padding: 0; } .t-Dialog-body .t-Region { margin: 0; }"


def pdf_url(process, items=None, values=None):
    """the application process; items/values (page 92.. items) set on the way"""
    return 'f?p=&APP_ID.:0:&SESSION.:APPLICATION_PROCESS=' + process + (':::%s:%s' % (items, values) if items else '')


def pdf_dialog(ctx, pid, name, alias, process, items):
    """the modal page: its items (set by the caller), a URL region on the process, Close and New tab"""
    p = Page(ctx.app, pid, name, alias, title=name, mode='MODAL', group=ctx.group_demo, auth=ctx.demo_auth, component_map='03',
             dialog_width='1100', inline_css=DIALOG_CSS)
    p.head.append(('p_dialog_height', '800'))
    r = p._plug('PDF', p_region_template_options='#DEFAULT#', p_escape_on_http_output='N',
                p_plug_template=T['region_blank'], p_plug_display_sequence=10, p_plug_item_display_point='ABOVE',
                p_plug_source_type='NATIVE_URL', p_plug_query_headings_type='COLON_DELMITED_LIST',
                p_attributes=attrs({'url': pdf_url(process), 'inclusion_mode': 'IFRAME',
                                    'iframe_attributes': 'title="%s" style="width:100%%;height:calc(100vh - 70px);border:0;display:block"' % name}))
    for item in items:
        p.item(item, r, kind='hidden', protection='N')
    bar = p.buttons_bar()
    close = p.button('CLOSE', 'Close', bar, action='DEFINED_BY_DA', position='PREVIOUS', seq=10)
    p.da('Close the dialog', 'click', [{'action': 'NATIVE_DIALOG_CANCEL'}], button=close, element_type='BUTTON')
    p.button('NEW_TAB', 'Open in a new tab', bar, action='REDIRECT_URL', position='NEXT', seq=10, icon='fa-external-link',
             hot=True, url="javascript:window.open('%s', '_blank');void(0);" % pdf_url(process))
    return p


def pdf_pages(ctx):
    return [pdf_dialog(ctx, 92, 'Invoice PDF', 'INVOICE-PDF', 'INVOICE_PDF', ['P92_INVOICE_ID']),
            pdf_dialog(ctx, 93, 'Statement PDF', 'STATEMENT-PDF', 'STATEMENT_PDF', ['P93_CUSTOMER_ID']),
            pdf_dialog(ctx, 94, 'Label PDF', 'LABEL-PDF', 'LABEL_PDF', ['P94_SKU']),
            pdf_dialog(ctx, 95, 'Labels PDF', 'LABELS-PDF', 'LABELS_PDF', ['P95_CATEGORY', 'P95_COPIES']),
            pdf_dialog(ctx, 96, 'Invoices PDF', 'INVOICES-PDF', 'INVOICES_PDF', ['P96_DATE_FROM', 'P96_DATE_TO'])]


def pdf_buttons(p, region, dialog, process, items, values, cond_item, label, seq=50, preview_label=None):
    """Preview (the dialog page, its items set) and New tab (the process, the same items set)"""
    cond = dict(cond_type='ITEM_IS_NOT_NULL', cond=cond_item) if cond_item else {}
    p.button('PREVIEW', preview_label or 'Preview ' + label, region, action='REDIRECT_PAGE', position='NEXT', seq=seq,
             icon='fa-file-pdf-o', hot=bool(preview_label),
             url='f?p=&APP_ID.:%d:&SESSION.::&DEBUG.::%s:%s' % (dialog, items, values), **cond)
    p.button('NEW_TAB', 'New tab', region, action='REDIRECT_URL', position='NEXT', seq=seq + 1, icon='fa-external-link',
             url="javascript:window.open('%s', '_blank');void(0);" % pdf_url(process, items, values), **cond)


def preview_link(dialog, item, value):
    """IR column PREVIEW: the dialog of the PDF, its item set from the row"""
    return dict(name='PREVIEW', label='PDF', align='CENTER',
                link='f?p=&APP_ID.:%d:&SESSION.::&DEBUG.::%s:%s' % (dialog, item, value),
                link_text='<span class="fa fa-file-pdf-o" aria-hidden="true"></span> Preview')


PDF_COLS = ", 'Preview' preview"


def submit_on_change(p, items):
    """a change of these items submits the page, so the Preview links carry the new values"""
    p.da('Submit on change', 'change', [{'action': 'NATIVE_SUBMIT_PAGE', 'attrs': {'show_processing': 'Y'}}],
         element_type='ITEM', element=items)


# ------------------------------------------------------------------ invoices
INVOICES_SQL = """select i.invoice_id, i.invoice_no, i.invoice_date, i.due_date, c.name customer, c.city, initcap(i.status) status,
       (select count(*) from pdf_demo_invoice_lines l where l.invoice_id = i.invoice_id) lines,
       (select sum(v.amount) from pdf_demo_invoice_lines_v v where v.invoice_id = i.invoice_id) amount""" + PDF_COLS + """
  from pdf_demo_invoices i
  join pdf_demo_customers c on c.customer_id = i.customer_id"""

def page_invoices(ctx):
    p = Page(ctx.app, 10, 'Invoices', 'INVOICES', title='Invoices', group=ctx.group_demo, auth=ctx.demo_auth, component_map='18')
    b = p.static('Print the Invoices of a Period', seq=5, options='#DEFAULT#:t-Region--scrollBody')
    p.item('P10_DATE_FROM', b, kind='date', label='From', colspan=3)
    p.item('P10_DATE_TO', b, kind='date', label='To', colspan=3, new_line='N')
    p.computation('P10_DATE_FROM', 'EXPRESSION', "to_char(trunc(add_months(sysdate, -1), 'MM'), 'DD-MON-YYYY')",
                  lang='PLSQL', seq=10, when_type='ITEM_IS_NULL', when='P10_DATE_FROM')
    p.computation('P10_DATE_TO', 'EXPRESSION', "to_char(last_day(sysdate), 'DD-MON-YYYY')",
                  lang='PLSQL', seq=20, when_type='ITEM_IS_NULL', when='P10_DATE_TO')
    submit_on_change(p, 'P10_DATE_FROM,P10_DATE_TO')
    pdf_buttons(p, b, 96, 'INVOICES_PDF', 'P96_DATE_FROM,P96_DATE_TO', '&P10_DATE_FROM.,&P10_DATE_TO.', None,
                'invoices', seq=10, preview_label='Preview all')
    p.static('Batch hint', seq=6, parent=b, template='region_blank', html=(
        '<p class="u-color-text-secondary">One PDF with every invoice of the period (report <code>INVOICE_BATCH</code>, '
        'one document per row of its Q1).</p>'))
    r = p.ir('Invoices', INVOICES_SQL, [
        dict(name='INVOICE_ID', hidden=True),
        dict(name='INVOICE_NO', label='Invoice No.'),
        dict(name='INVOICE_DATE', label='Date', type='DATE'),
        dict(name='DUE_DATE', label='Due', type='DATE'),
        dict(name='CUSTOMER', label='Customer'),
        dict(name='CITY', label='City'),
        dict(name='STATUS', label='Status'),
        dict(name='LINES', label='Lines', type='NUMBER'),
        dict(name='AMOUNT', label='Amount', type='NUMBER', mask='FM999G999G990D00'),
        preview_link(92, 'P92_INVOICE_ID', '#INVOICE_ID#'),
    ],
        seq=10, sort=('INVOICE_DATE', 'DESC'), rows=25,
        link='f?p=&APP_ID.:11:&SESSION.::&DEBUG.:RP,11:P11_INVOICE_ID:#INVOICE_ID#')
    p.button('CREATE', 'New Invoice', r, action='REDIRECT_URL', position='RIGHT_OF_IR_SEARCH_BAR', hot=True,
             icon='fa-plus', url='f?p=&APP_ID.:11:&SESSION.::&DEBUG.:RP,11::')
    return p


INVOICE_FETCH = """begin
  select invoice_no, to_char(invoice_date, 'DD-MON-YYYY'), to_char(due_date, 'DD-MON-YYYY'), customer_id, status, notes
    into :P11_INVOICE_NO, :P11_INVOICE_DATE, :P11_DUE_DATE, :P11_CUSTOMER_ID, :P11_STATUS, :P11_NOTES
    from pdf_demo_invoices
   where invoice_id = :P11_INVOICE_ID;
end;"""

INVOICE_DEFAULTS = """select 'NW/2026-27/' || to_char(nvl(max(to_number(substr(invoice_no, -4) default null on conversion error)), 0) + 1, 'FM0000'),
       to_char(trunc(sysdate), 'DD-MON-YYYY'), to_char(trunc(sysdate) + 30, 'DD-MON-YYYY'), 'DUE'
  into :P11_INVOICE_NO, :P11_INVOICE_DATE, :P11_DUE_DATE, :P11_STATUS
  from pdf_demo_invoices;"""

INVOICE_CREATE = """select nvl(max(invoice_id), 1000) + 1 into :P11_INVOICE_ID from pdf_demo_invoices;
insert into pdf_demo_invoices (invoice_id, invoice_no, invoice_date, due_date, customer_id, status, notes)
values (:P11_INVOICE_ID, :P11_INVOICE_NO, to_date(:P11_INVOICE_DATE, 'DD-MON-YYYY'), to_date(:P11_DUE_DATE, 'DD-MON-YYYY'),
        :P11_CUSTOMER_ID, :P11_STATUS, :P11_NOTES);"""

INVOICE_SAVE = """update pdf_demo_invoices
   set invoice_no = :P11_INVOICE_NO, invoice_date = to_date(:P11_INVOICE_DATE, 'DD-MON-YYYY'),
       due_date = to_date(:P11_DUE_DATE, 'DD-MON-YYYY'), customer_id = :P11_CUSTOMER_ID,
       status = :P11_STATUS, notes = :P11_NOTES
 where invoice_id = :P11_INVOICE_ID;"""

INVOICE_DELETE = """delete from pdf_demo_invoice_lines where invoice_id = :P11_INVOICE_ID;
delete from pdf_demo_invoices where invoice_id = :P11_INVOICE_ID;"""

# runs once for every changed row of the grid (:APEX$ROW_STATUS C, U or D)
LINES_SAVE = """declare
  l_line  number := to_number(substr(:LINE_KEY, instr(:LINE_KEY, ':') + 1));
  l_price number;
begin
  case :APEX$ROW_STATUS
    when 'C' then
      select price into l_price from pdf_demo_products where product_id = :PRODUCT_ID;
      insert into pdf_demo_invoice_lines (invoice_id, line_no, product_id, description, qty, unit_price, discount_pct)
      select :P11_INVOICE_ID, nvl(max(line_no), 0) + 1, :PRODUCT_ID, :DESCRIPTION, nvl(:QTY, 1),
             nvl(:UNIT_PRICE, l_price), nvl(:DISCOUNT_PCT, 0)
        from pdf_demo_invoice_lines where invoice_id = :P11_INVOICE_ID;
    when 'U' then
      update pdf_demo_invoice_lines
         set product_id = :PRODUCT_ID, description = :DESCRIPTION, qty = :QTY,
             unit_price = nvl(:UNIT_PRICE, unit_price), discount_pct = nvl(:DISCOUNT_PCT, 0)
       where invoice_id = :P11_INVOICE_ID and line_no = l_line;
    when 'D' then
      delete from pdf_demo_invoice_lines where invoice_id = :P11_INVOICE_ID and line_no = l_line;
  end case;
end;"""

LINES_SQL = """select line_key, line_no, product_id, description, qty, unit_price, discount_pct, tax_rate, taxable, amount
  from pdf_demo_invoice_lines_v
 where invoice_id = :P11_INVOICE_ID
 order by line_no"""

INVOICE_TOTALS = """declare
  l_taxable number; l_tax number; l_total number;
begin
  select nvl(sum(taxable), 0), nvl(sum(amount - taxable), 0), nvl(sum(amount), 0)
    into l_taxable, l_tax, l_total
    from pdf_demo_invoice_lines_v where invoice_id = :P11_INVOICE_ID;
  sys.htp.p('<dl class="inv-totals">'
    || '<dt>Taxable value</dt><dd>' || to_char(l_taxable, 'FM999G999G990D00') || '</dd>'
    || '<dt>GST</dt><dd>' || to_char(l_tax, 'FM999G999G990D00') || '</dd>'
    || '<dt>Round off</dt><dd>' || to_char(round(l_total) - l_total, 'FM990D00') || '</dd>'
    || '<dt class="is-total">Grand total</dt><dd class="is-total">' || to_char(round(l_total), 'FM999G999G990D00') || '</dd></dl>');
end;"""

INVOICE_CSS = """.inv-totals { display: grid; grid-template-columns: 1fr auto; gap: 6px 16px; margin: 0; font-size: 14px; }
.inv-totals dt { color: #5f6b7a; } .inv-totals dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }
.inv-totals .is-total { font-weight: 700; font-size: 16px; border-top: 1px solid #d9dee6; padding-top: 6px; }"""


def form_buttons(p, bar, key_item, list_page, what):
    p.button('CANCEL', 'Back', bar, action='REDIRECT_URL', position='PREVIOUS', seq=10, icon='fa-chevron-left',
             url='f?p=&APP_ID.:%d:&SESSION.::&DEBUG.:::' % list_page)
    p.button('DELETE', 'Delete', bar, action='REDIRECT_URL', position='PREVIOUS', seq=20, icon='fa-trash-o',
             url="javascript:apex.confirm('Delete this %s?', 'DELETE');" % what,
             cond_type='ITEM_IS_NOT_NULL', cond=key_item, options='#DEFAULT#:t-Button--danger:t-Button--simple:t-Button--iconLeft')
    save = p.button('SAVE', 'Save', bar, position='NEXT', seq=10, hot=True, icon='fa-save',
                    cond_type='ITEM_IS_NOT_NULL', cond=key_item)
    create = p.button('CREATE', 'Create', bar, position='NEXT', seq=10, hot=True, icon='fa-plus',
                      cond_type='ITEM_IS_NULL', cond=key_item)
    return save, create


def page_invoice(ctx):
    p = Page(ctx.app, 11, 'Invoice', 'INVOICE', title='Invoice', group=ctx.group_demo, auth=ctx.demo_auth, component_map='03',
             inline_css=INVOICE_CSS)
    bar = p.buttons_bar(seq=1)
    save, create = form_buttons(p, bar, 'P11_INVOICE_ID', 10, 'invoice and all its lines')
    pdf_buttons(p, bar, 92, 'INVOICE_PDF', 'P92_INVOICE_ID', '&P11_INVOICE_ID.', 'P11_INVOICE_ID', 'Invoice')
    r = p.static('Invoice', seq=10, grid=8)
    p.item('P11_INVOICE_ID', r, kind='hidden')
    p.item('P11_INVOICE_NO', r, label='Invoice No.', required=True, maxlen=30, colspan=4)
    p.item('P11_INVOICE_DATE', r, kind='date', label='Invoice Date', required=True, colspan=4, new_line='N')
    p.item('P11_DUE_DATE', r, kind='date', label='Due Date', colspan=4, new_line='N')
    p.item('P11_CUSTOMER_ID', r, kind='select', label='Customer', required=True, named_lov='DEMO_CUSTOMERS',
           lov_null='- choose -', colspan=8)
    p.item('P11_STATUS', r, kind='select', label='Status', lov='STATIC2:Due;DUE,Paid;PAID,Cancelled;CANCELLED',
           colspan=4, new_line='N')
    p.item('P11_NOTES', r, kind='textarea', label='Notes', height=2)
    p.plsql_region('Totals', INVOICE_TOTALS, seq=20, grid=4, new_row=False,
                   cond_type='ITEM_IS_NOT_NULL', cond='P11_INVOICE_ID')
    grid = p.ig('Lines', LINES_SQL, [
        dict(name='LINE_KEY', pk=True),
        dict(name='LINE_NO', label='#', type='NUMBER', kind='display', width=50),
        dict(name='PRODUCT_ID', label='Product', type='NUMBER', kind='select', lov=ctx.lov_products, required=True, width=320),
        dict(name='DESCRIPTION', label='Description (optional)', maxlen=400),
        dict(name='QTY', label='Qty', type='NUMBER', kind='number', required=True, width=80),
        dict(name='UNIT_PRICE', label='Rate (empty: list price)', type='NUMBER', kind='number', width=110),
        dict(name='DISCOUNT_PCT', label='Disc %', type='NUMBER', kind='number', width=80),
        dict(name='TAX_RATE', label='GST %', type='NUMBER', kind='display', width=70),
        dict(name='TAXABLE', label='Taxable', type='NUMBER', kind='display', width=110),
        dict(name='AMOUNT', label='Amount', type='NUMBER', kind='display', width=110),
    ], seq=30, items_to_submit='P11_INVOICE_ID', edit_ops='i:u:d', cond_type='ITEM_IS_NOT_NULL', cond='P11_INVOICE_ID')
    p.static('Lines hint', seq=31, template='region_blank', cond_type='ITEM_IS_NULL', cond='P11_INVOICE_ID',
             html='<p class="u-color-text-secondary">Create the invoice first; then add its lines here.</p>')
    p.process('Load the invoice', INVOICE_FETCH, point='BEFORE_HEADER', seq=10, when_type='ITEM_IS_NOT_NULL',
              when='P11_INVOICE_ID')
    p.process('Defaults of a new invoice', INVOICE_DEFAULTS, point='BEFORE_HEADER', seq=20,
              when_type='EXPRESSION', when=':P11_INVOICE_ID is null and :P11_INVOICE_NO is null')
    p.process('Create the invoice', INVOICE_CREATE, seq=10, button=create, success='Invoice created - add its lines.')
    p.process('Save the invoice', INVOICE_SAVE, seq=20, button=save, success='Invoice saved.')
    p.process('Save the lines', LINES_SAVE, seq=30, region=grid)
    p.process('Delete the invoice', INVOICE_DELETE, seq=40, when_type='REQUEST_EQUALS_CONDITION', when='DELETE',
              success='Invoice deleted.')
    p.branch('f?p=&APP_ID.:10:&SESSION.::&DEBUG.:::&success_msg=#SUCCESS_MSG#', seq=10, name='To the list',
             cond_type='REQUEST_EQUALS_CONDITION', cond='DELETE')
    p.branch('f?p=&APP_ID.:11:&SESSION.::&DEBUG.::P11_INVOICE_ID:&P11_INVOICE_ID.&success_msg=#SUCCESS_MSG#', seq=20,
             name='Stay')
    return p


# ------------------------------------------------------------------ customers
CUSTOMERS_SQL = """select c.customer_id, c.name, c.city, c.state, c.gstin, c.phone, c.email,
       (select count(*) from pdf_demo_invoices i where i.customer_id = c.customer_id) invoices,
       (select sum(v.amount) from pdf_demo_invoices i join pdf_demo_invoice_lines_v v on v.invoice_id = i.invoice_id
         where i.customer_id = c.customer_id and i.status = 'DUE') balance""" + PDF_COLS + """
  from pdf_demo_customers c"""


def page_customers(ctx):
    p = Page(ctx.app, 20, 'Customers', 'CUSTOMERS', title='Customers', group=ctx.group_demo, auth=ctx.demo_auth, component_map='18')
    r = p.ir('Customers', CUSTOMERS_SQL, [
        dict(name='CUSTOMER_ID', hidden=True),
        dict(name='NAME', label='Customer'),
        dict(name='CITY', label='City'),
        dict(name='STATE', label='State'),
        dict(name='GSTIN', label='GSTIN'),
        dict(name='PHONE', label='Phone'),
        dict(name='EMAIL', label='E-mail'),
        dict(name='INVOICES', label='Invoices', type='NUMBER'),
        dict(name='BALANCE', label='Balance Due', type='NUMBER', mask='FM999G999G990D00'),
        preview_link(93, 'P93_CUSTOMER_ID', '#CUSTOMER_ID#'),
    ],
        seq=10, sort=('NAME', 'ASC'), rows=25,
        link='f?p=&APP_ID.:21:&SESSION.::&DEBUG.:RP,21:P21_CUSTOMER_ID:#CUSTOMER_ID#')
    p.button('CREATE', 'New Customer', r, action='REDIRECT_URL', position='RIGHT_OF_IR_SEARCH_BAR', hot=True,
             icon='fa-plus', url='f?p=&APP_ID.:21:&SESSION.::&DEBUG.:RP,21::')
    return p


CUSTOMER_FETCH = """begin
  select name, address, city, state, pincode, gstin, phone, email
    into :P21_NAME, :P21_ADDRESS, :P21_CITY, :P21_STATE, :P21_PINCODE, :P21_GSTIN, :P21_PHONE, :P21_EMAIL
    from pdf_demo_customers where customer_id = :P21_CUSTOMER_ID;
end;"""

CUSTOMER_CREATE = """select nvl(max(customer_id), 0) + 1 into :P21_CUSTOMER_ID from pdf_demo_customers;
insert into pdf_demo_customers (customer_id, name, address, city, state, pincode, gstin, phone, email)
values (:P21_CUSTOMER_ID, :P21_NAME, :P21_ADDRESS, :P21_CITY, :P21_STATE, :P21_PINCODE, :P21_GSTIN, :P21_PHONE, :P21_EMAIL);"""

CUSTOMER_SAVE = """update pdf_demo_customers
   set name = :P21_NAME, address = :P21_ADDRESS, city = :P21_CITY, state = :P21_STATE, pincode = :P21_PINCODE,
       gstin = :P21_GSTIN, phone = :P21_PHONE, email = :P21_EMAIL
 where customer_id = :P21_CUSTOMER_ID;"""

CUSTOMER_INVOICES = """select i.invoice_id, i.invoice_no, i.invoice_date, initcap(i.status) status,
       (select sum(v.amount) from pdf_demo_invoice_lines_v v where v.invoice_id = i.invoice_id) amount,
       'Preview' preview
  from pdf_demo_invoices i
 where i.customer_id = :P21_CUSTOMER_ID
 order by i.invoice_date desc"""


def page_customer(ctx):
    p = Page(ctx.app, 21, 'Customer', 'CUSTOMER', title='Customer', group=ctx.group_demo, auth=ctx.demo_auth, component_map='03')
    bar = p.buttons_bar(seq=1)
    save, create = form_buttons(p, bar, 'P21_CUSTOMER_ID', 20, 'customer')
    pdf_buttons(p, bar, 93, 'STATEMENT_PDF', 'P93_CUSTOMER_ID', '&P21_CUSTOMER_ID.', 'P21_CUSTOMER_ID', 'Statement')
    r = p.static('Customer', seq=10, grid=6)
    p.item('P21_CUSTOMER_ID', r, kind='hidden')
    p.item('P21_NAME', r, label='Name', required=True, maxlen=200)
    p.item('P21_ADDRESS', r, kind='textarea', label='Address', height=2)
    p.item('P21_CITY', r, label='City', maxlen=100, colspan=6)
    p.item('P21_STATE', r, label='State', maxlen=100, colspan=4, new_line='N')
    p.item('P21_PINCODE', r, label='PIN', maxlen=10, colspan=2, new_line='N')
    p.item('P21_GSTIN', r, label='GSTIN', maxlen=20, colspan=6)
    p.item('P21_PHONE', r, label='Phone', maxlen=30, colspan=6, new_line='N')
    p.item('P21_EMAIL', r, label='E-mail', maxlen=200)
    p.classic('Invoices', CUSTOMER_INVOICES, [
        dict(name='INVOICE_ID', hidden=True),
        dict(name='INVOICE_NO', label='Invoice No.', link='f?p=&APP_ID.:11:&SESSION.::&DEBUG.:RP,11:P11_INVOICE_ID:#INVOICE_ID#',
             link_text='#INVOICE_NO#'),
        dict(name='INVOICE_DATE', label='Date', format='DD-MON-YYYY'),
        dict(name='STATUS', label='Status'),
        dict(name='AMOUNT', label='Amount', format='FM999G999G990D00', align='RIGHT'),
        dict(name='PREVIEW', label='PDF', align='CENTER',
             link='f?p=&APP_ID.:92:&SESSION.::&DEBUG.::P92_INVOICE_ID:#INVOICE_ID#',
             link_text='<span class="fa fa-file-pdf-o" aria-hidden="true"></span> Preview'),
    ], seq=20, grid=6, new_row=False, rows=15, no_data='No invoices yet.')
    p.validation('No invoices', 'NOT_EXISTS', 'select 1 from pdf_demo_invoices where customer_id = :P21_CUSTOMER_ID',
                 'This customer has invoices: delete them first.', seq=10,
                 cond_type='REQUEST_EQUALS_CONDITION', cond='DELETE')
    p.process('Load the customer', CUSTOMER_FETCH, point='BEFORE_HEADER', seq=10, when_type='ITEM_IS_NOT_NULL',
              when='P21_CUSTOMER_ID')
    p.process('Create the customer', CUSTOMER_CREATE, seq=10, button=create, success='Customer created.')
    p.process('Save the customer', CUSTOMER_SAVE, seq=20, button=save, success='Customer saved.')
    p.process('Delete the customer', 'delete from pdf_demo_customers where customer_id = :P21_CUSTOMER_ID;', seq=30,
              when_type='REQUEST_EQUALS_CONDITION', when='DELETE', success='Customer deleted.')
    p.branch('f?p=&APP_ID.:20:&SESSION.::&DEBUG.:::&success_msg=#SUCCESS_MSG#', seq=10, name='To the list',
             cond_type='REQUEST_EQUALS_CONDITION', cond='DELETE')
    p.branch('f?p=&APP_ID.:21:&SESSION.::&DEBUG.::P21_CUSTOMER_ID:&P21_CUSTOMER_ID.&success_msg=#SUCCESS_MSG#', seq=20,
             name='Stay')
    return p


# ------------------------------------------------------------------ products
PRODUCTS_SQL = """select p.product_id, p.sku, p.name, p.category, p.hsn, p.unit, p.price, p.tax_rate,
       (select nvl(sum(l.qty), 0) from pdf_demo_invoice_lines l where l.product_id = p.product_id) sold""" + PDF_COLS + """
  from pdf_demo_products p"""

def page_products(ctx):
    p = Page(ctx.app, 30, 'Products', 'PRODUCTS', title='Products', group=ctx.group_demo, auth=ctx.demo_auth, component_map='18')
    b = p.static('Print Shelf Labels', seq=5, options='#DEFAULT#:t-Region--scrollBody')
    p.item('P30_CATEGORY', b, kind='select', label='Category', named_lov='DEMO_CATEGORIES', lov_null='- all -',
           colspan=4, attrs_={'page_action_on_selection': 'NONE'})
    p.item('P30_COPIES', b, kind='select', label='Copies of each', default='1', colspan=2, new_line='N',
           lov='STATIC2:1;1,2;2,3;3,4;4,5;5,10;10,24;24', attrs_={'page_action_on_selection': 'NONE'})
    p.computation('P30_COPIES', 'STATIC_ASSIGNMENT', '1', seq=10, when_type='ITEM_IS_NULL', when='P30_COPIES')
    submit_on_change(p, 'P30_CATEGORY,P30_COPIES')
    pdf_buttons(p, b, 95, 'LABELS_PDF', 'P95_CATEGORY,P95_COPIES', '&P30_CATEGORY.,&P30_COPIES.', None,
                'labels', seq=10, preview_label='Preview labels')
    r = p.ir('Products', PRODUCTS_SQL, [
        dict(name='PRODUCT_ID', hidden=True),
        dict(name='SKU', label='SKU'),
        dict(name='NAME', label='Product'),
        dict(name='CATEGORY', label='Category'),
        dict(name='HSN', label='HSN'),
        dict(name='UNIT', label='Unit'),
        dict(name='PRICE', label='Price', type='NUMBER', mask='FM999G999G990D00'),
        dict(name='TAX_RATE', label='GST %', type='NUMBER'),
        dict(name='SOLD', label='Sold', type='NUMBER'),
        preview_link(94, 'P94_SKU', '#SKU#'),
    ],
        seq=10, sort=('NAME', 'ASC'), rows=25,
        link='f?p=&APP_ID.:31:&SESSION.::&DEBUG.:RP,31:P31_PRODUCT_ID:#PRODUCT_ID#')
    p.button('CREATE', 'New Product', r, action='REDIRECT_URL', position='RIGHT_OF_IR_SEARCH_BAR', hot=True,
             icon='fa-plus', url='f?p=&APP_ID.:31:&SESSION.::&DEBUG.:RP,31::')
    return p


PRODUCT_FETCH = """begin
  select sku, name, category, hsn, unit, price, tax_rate
    into :P31_SKU, :P31_NAME, :P31_CATEGORY, :P31_HSN, :P31_UNIT, :P31_PRICE, :P31_TAX_RATE
    from pdf_demo_products where product_id = :P31_PRODUCT_ID;
end;"""

PRODUCT_CREATE = """select nvl(max(product_id), 100) + 1 into :P31_PRODUCT_ID from pdf_demo_products;
insert into pdf_demo_products (product_id, sku, name, category, hsn, unit, price, tax_rate)
values (:P31_PRODUCT_ID, upper(:P31_SKU), :P31_NAME, :P31_CATEGORY, :P31_HSN, :P31_UNIT, :P31_PRICE, :P31_TAX_RATE);"""

PRODUCT_SAVE = """update pdf_demo_products
   set sku = upper(:P31_SKU), name = :P31_NAME, category = :P31_CATEGORY, hsn = :P31_HSN, unit = :P31_UNIT,
       price = :P31_PRICE, tax_rate = :P31_TAX_RATE
 where product_id = :P31_PRODUCT_ID;"""


def page_product(ctx):
    p = Page(ctx.app, 31, 'Product', 'PRODUCT', title='Product', group=ctx.group_demo, auth=ctx.demo_auth, component_map='03')
    bar = p.buttons_bar(seq=1)
    save, create = form_buttons(p, bar, 'P31_PRODUCT_ID', 30, 'product')
    pdf_buttons(p, bar, 94, 'LABEL_PDF', 'P94_SKU', '&P31_SKU.', 'P31_PRODUCT_ID', 'Label')
    r = p.static('Product', seq=10, grid=8)
    p.item('P31_PRODUCT_ID', r, kind='hidden')
    p.item('P31_SKU', r, label='SKU (barcode)', required=True, maxlen=30, colspan=4)
    p.item('P31_NAME', r, label='Name', required=True, maxlen=200, colspan=8, new_line='N')
    p.item('P31_CATEGORY', r, kind='select', label='Category', lov='STATIC2:Consumables;Consumables,Equipment;Equipment',
           colspan=4)
    p.item('P31_HSN', r, label='HSN', maxlen=10, colspan=4, new_line='N')
    p.item('P31_UNIT', r, label='Unit', maxlen=10, colspan=4, new_line='N')
    p.item('P31_PRICE', r, kind='number', label='Price', required=True, colspan=6)
    p.item('P31_TAX_RATE', r, kind='select', label='GST %', lov='STATIC2:0%;0,5%;5,12%;12,18%;18,28%;28',
           colspan=6, new_line='N')
    p.validation('Not sold', 'NOT_EXISTS', 'select 1 from pdf_demo_invoice_lines where product_id = :P31_PRODUCT_ID',
                 'This product is on invoices and cannot be deleted.', seq=10,
                 cond_type='REQUEST_EQUALS_CONDITION', cond='DELETE')
    p.process('Load the product', PRODUCT_FETCH, point='BEFORE_HEADER', seq=10, when_type='ITEM_IS_NOT_NULL',
              when='P31_PRODUCT_ID')
    p.process('Create the product', PRODUCT_CREATE, seq=10, button=create, success='Product created.')
    p.process('Save the product', PRODUCT_SAVE, seq=20, button=save, success='Product saved.')
    p.process('Delete the product', 'delete from pdf_demo_products where product_id = :P31_PRODUCT_ID;', seq=30,
              when_type='REQUEST_EQUALS_CONDITION', when='DELETE', success='Product deleted.')
    p.branch('f?p=&APP_ID.:30:&SESSION.::&DEBUG.:::&success_msg=#SUCCESS_MSG#', seq=10, name='To the list',
             cond_type='REQUEST_EQUALS_CONDITION', cond='DELETE')
    p.branch('f?p=&APP_ID.:31:&SESSION.::&DEBUG.::P31_PRODUCT_ID:&P31_PRODUCT_ID.&success_msg=#SUCCESS_MSG#', seq=20,
             name='Stay')
    return p


def pages(ctx):
    return ([page_invoices(ctx), page_invoice(ctx), page_customers(ctx), page_customer(ctx),
             page_products(ctx), page_product(ctx)] + pdf_pages(ctx))


LOVS = {
    'DEMO_CUSTOMERS': "select name || ' (' || city || ')' d, customer_id r from pdf_demo_customers order by name",
    'DEMO_PRODUCTS': "select name || ' - ' || sku || ' - Rs. ' || to_char(price, 'FM999G999G990D00') d, product_id r\n"
                     "  from pdf_demo_products order by name",
    'DEMO_CATEGORIES': "select distinct category d, category r from pdf_demo_products order by 1",
}
