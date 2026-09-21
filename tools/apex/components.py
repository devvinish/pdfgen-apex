"""APEX 26.1 page / component builders used by the Rounds generator.

Every call and parameter used here appears in a real APEX 26.1.1 export
(the reference f76246.sql), and tools/apex/check_export.py verifies the
generated file against stub packages built from that vocabulary.
"""
from emit import Raw, attrs, call, static_id, wid

# Universal Theme 42 templates as referenced by an APEX 26.1 export
T = {
    'page_standard': 4073832297226169690,
    'page_dialog': 2101883943284197310,
    'page_login': 2102634289808461002,
    'region_standard': 4073835273271169698,
    'region_blank': 4502917002193490937,
    'region_ir': 2102002977963900996,
    'region_buttons': 2127905476394690047,
    'region_titlebar': 2532939663579242476,
    'region_collapsible': 2665811232373458102,
    'region_alert': 2042159785845301134,
    'region_login': 2675634334296186762,
    'report_standard': 2540130677583398057,
    'label_optional': 2320077351817916916,
    'label_required': 2528236951996823187,
    'label_optional_floating': 1610598304472262251,
    'label_required_floating': 1610598484065263269,
    'label_hidden': 2042262243893469891,
    'label_optional_above': 3033038003750078790,
    'label_required_above': 3033038269190080499,
    'button_text': 4073839297780169708,
    'button_text_icon': 2084305881903810008,   # "Text with Icon"
    'button_icon': 2350584059425431644,        # "Icon" (icon only)
    'breadcrumb': 4073839682315169711,
    'list_side_nav': 2469215554099805162,
    'list_navbar': 2849019392706229583,
    'list_media': 2069471208528591807,
}

STATIC_ATTRS = {'expand_shortcuts': 'N', 'output_as': 'HTML', 'show_line_breaks': 'N'}

# per-application look, set by gen_apex.py before a build: labels 'floating' or 'above' the items,
# the button bar at the top of normal pages (NetSuite style) instead of at the end, fields that
# stretch to the width of their grid columns, and date reads that also accept YYYY-MM-DD (the value
# of a date picker switched to "Native HTML"); ir_print adds a Print button to every interactive report
# (rounds-hms.js opens the print page 901 with all its rows); button_ids gives every button the id of its
# name in the page, so that the keyboard shortcuts of the data entry screens can press it
STYLE = {'labels': 'floating', 'buttons_top': False, 'stretch': False, 'tolerant_dates': False,
         'ir_print': False, 'button_ids': False}


def set_style(labels='floating', buttons_top=False, stretch=False, tolerant_dates=False, ir_print=False,
              button_ids=False):
    STYLE.update(labels=labels, buttons_top=buttons_top, stretch=stretch, tolerant_dates=tolerant_dates,
                 ir_print=ir_print, button_ids=button_ids)


def col_ident(n):
    """IR column identifiers: A..Z, AA..AZ, BA.."""
    s = ''
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


class App:
    def __init__(self, ids):
        self.ids = ids
        self.uid = 90000000000000        # p_internal_uid values
        self.report_alias = 200000

    def new_uid(self):
        self.uid += 1
        return self.uid

    def new_alias(self):
        self.report_alias += 1
        return str(self.report_alias)



# the categorical colours of the charts (validated for colour-blind separation on a light surface); fixed order
CHART_PALETTE = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948']


def point_colors(sql, label_col):
    """the query with a CHART_COLOR column: the colour of each label, in the query's own row order"""
    case = ' '.join("when %d then '%s'" % (n, c) for n, c in enumerate(CHART_PALETTE))
    return ("select * from (\n  select q.*, rownum chart_rn,\n"
            "         case mod(dense_rank() over (order by q.%s) - 1, %d) %s end chart_color\n"
            "    from (\n%s\n) q)\n order by chart_rn" % (label_col, len(CHART_PALETTE), case, sql))

class Page:
    """Collects the components of one page and renders them in export order."""

    def __init__(self, app, pid, name, alias, title=None, mode=None, group=None, auth=None,
                 template=None, public=False, help_text=None, inline_css=None, js_onload=None,
                 component_map='03', template_options='#DEFAULT#', dialog_width=None,
                 autocomplete='OFF', protection='C', first_item=None, reload='A'):
        self.app = app
        self.id = pid
        self.mode = mode
        self.head = [('p_id', pid), ('p_name', name), ('p_alias', alias)]
        if mode:
            self.head.append(('p_page_mode', mode))
        # reload: 'A' always, 'S' only for success (required by pages with an editable interactive grid)
        self.head += [('p_step_title', title or name), ('p_reload_on_submit', reload),
                      ('p_warn_on_unsaved_changes', 'N'), ('p_first_item', first_item),
                      ('p_autocomplete_on_off', autocomplete),
                      ('p_group_id', wid(group) if group else None),
                      ('p_inline_css', inline_css),
                      ('p_javascript_code_onload', js_onload),
                      ('p_step_template', template if template is not None else
                       (T['page_dialog'] if mode == 'MODAL' else T['page_standard'])),
                      ('p_page_template_options', template_options),
                      ('p_required_role', wid(auth) if auth else None),
                      ('p_dialog_width', dialog_width),
                      ('p_dialog_chained', 'N' if mode == 'MODAL' else None),
                      ('p_page_is_public_y_n', 'Y' if public else None),
                      ('p_protection_level', protection),
                      ('p_help_text', help_text),
                      ('p_page_component_map', component_map)]
        self.plugs, self.buttons, self.branches, self.items = [], [], [], []
        self.comps, self.vals, self.das, self.procs = [], [], [], []
        self.sids = {k: set() for k in ('plug', 'button', 'proc', 'da', 'act', 'val', 'comp')}
        self.item_names = set()
        self.plug_sids = {}        # region id -> static id
        self.button_sids = {}      # button id -> static id (the id of the button in the page)

    # ------------------------------------------------------------ regions
    def _plug(self, name, rid=None, **p):
        rid = rid or self.app.ids.new()
        self.plug_sids[rid] = static_id(p.pop('sid', None) or name, self.sids['plug'])
        params = [('p_id', wid(rid)), ('p_plug_name', name), ('p_static_id', self.plug_sids[rid])]
        order = ['p_title', 'p_parent_plug_id', 'p_region_name', 'p_region_css_classes',
                 'p_region_template_options', 'p_component_template_options', 'p_escape_on_http_output',
                 'p_plug_template', 'p_plug_display_sequence', 'p_plug_new_grid_row',
                 'p_plug_new_grid_column', 'p_plug_grid_column_span', 'p_plug_display_point',
                 'p_plug_item_display_point', 'p_query_type', 'p_query_table', 'p_include_rowid_column',
                 'p_plug_source', 'p_list_id', 'p_menu_id', 'p_plug_source_type', 'p_list_template_id',
                 'p_menu_template_id', 'p_ajax_items_to_submit', 'p_plug_query_headings_type',
                 'p_plug_query_num_rows', 'p_plug_query_show_nulls_as', 'p_plug_display_condition_type',
                 'p_plug_display_when_condition', 'p_plug_display_when_cond2', 'p_plug_required_role',
                 'p_pagination_display_position', 'p_ai_enabled', 'p_attributes', 'p_plug_header',
                 'p_plug_footer']
        for k in order:
            v = p.pop(k, None)
            if v is not None:
                params.append((k, v))
        if p:
            raise ValueError('unknown region params %s' % list(p))
        self.plugs.append(call('wwv_flow_imp_page.create_page_plug', params))
        return rid

    def static(self, name, html=None, template='region_standard', seq=10, parent=None,
               point=None, options='#DEFAULT#', css=None, grid=None, new_row=None, new_col=None,
               cond_type=None, cond=None, cond2=None, auth=None, title=None, sid=None, attrs_=None):
        return self._plug(
            name, sid=sid, p_title=title, p_parent_plug_id=wid(parent) if parent else None,
            p_region_css_classes=css, p_region_template_options=options,
            p_escape_on_http_output='N', p_plug_template=T[template], p_plug_display_sequence=seq,
            p_plug_new_grid_row=new_row, p_plug_new_grid_column=new_col, p_plug_grid_column_span=grid,
            p_plug_display_point=point or ('SUB_REGIONS' if parent else None),
            p_plug_item_display_point='ABOVE', p_plug_source=html,
            p_plug_query_headings_type='COLON_DELMITED_LIST',
            p_plug_display_condition_type=cond_type, p_plug_display_when_condition=cond,
            p_plug_display_when_cond2=cond2 or ('PLSQL' if cond_type == 'EXPRESSION' else None),
            p_plug_required_role=wid(auth) if auth else None,
            p_attributes=attrs(attrs_ or STATIC_ATTRS))

    def buttons_bar(self, seq=None, point=None):
        """Button container: the dialog footer (REGION_POSITION_03) on modal pages; the end of the
        body on normal pages - the Standard page template has no REGION_POSITION_03."""
        modal = self.mode == 'MODAL'
        top = STYLE['buttons_top'] and not modal
        return self.static('Buttons', template='region_buttons', seq=seq or (5 if modal else (1 if top else 900)),
                           point=point or ('REGION_POSITION_03' if modal else None),
                           attrs_={'expand_shortcuts': 'N', 'output_as': 'HTML'})

    def plsql_region(self, name, plsql, template='region_standard', seq=10, parent=None, options='#DEFAULT#',
                     grid=None, new_row=None, cond_type=None, cond=None, items_to_submit=None, css=None,
                     point=None):
        return self._plug(
            name, p_parent_plug_id=wid(parent) if parent else None, p_region_css_classes=css,
            p_region_template_options=options,
            p_escape_on_http_output='N', p_plug_template=T[template], p_plug_display_sequence=seq,
            p_plug_new_grid_row=new_row, p_plug_grid_column_span=grid,
            p_plug_display_point=point or ('SUB_REGIONS' if parent else None),
            p_plug_item_display_point='ABOVE', p_plug_source=plsql, p_plug_source_type='NATIVE_PLSQL',
            p_ajax_items_to_submit=items_to_submit, p_plug_query_headings_type='COLON_DELMITED_LIST',
            p_plug_display_condition_type=cond_type, p_plug_display_when_condition=cond,
            p_plug_display_when_cond2='PLSQL' if cond_type == 'EXPRESSION' else None)

    def breadcrumb(self, menu_id, cond_type=None):
        return self._plug(
            'Breadcrumb', p_region_template_options='#DEFAULT#:t-BreadcrumbRegion--useBreadcrumbTitle',
            p_component_template_options='#DEFAULT#', p_escape_on_http_output='N',
            p_plug_template=T['region_titlebar'], p_plug_display_sequence=1,
            p_plug_display_point='REGION_POSITION_01', p_plug_item_display_point='ABOVE',
            p_menu_id=wid(menu_id), p_plug_source_type='NATIVE_BREADCRUMB',
            p_menu_template_id=T['breadcrumb'], p_plug_query_headings_type='COLON_DELMITED_LIST',
            p_plug_display_condition_type=cond_type)

    def list_region(self, name, list_id, seq=10, options='#DEFAULT#',
                    comp_options='#DEFAULT#:u-colors', template='region_standard', grid=None):
        return self._plug(
            name, p_region_template_options=options, p_component_template_options=comp_options,
            p_escape_on_http_output='N', p_plug_template=T[template], p_plug_display_sequence=seq,
            p_plug_grid_column_span=grid, p_plug_item_display_point='ABOVE', p_list_id=wid(list_id),
            p_plug_source_type='NATIVE_LIST', p_list_template_id=T['list_media'],
            p_plug_query_headings_type='COLON_DELMITED_LIST')

    def ir(self, name, sql, columns, seq=10, link=None, link_text=None, sort=None,
           items_to_submit=None, rows=15, options='#DEFAULT#:t-IRR-region--noBorders',
           parent=None, template='region_ir', reports=None, max_rows='100000'):
        """columns: list of dicts {name, label, type(STRING|NUMBER|DATE), mask, hidden, link, link_text,
        link_attr, align}. link = detail link URL (#COL# substitutions)."""
        rid = self._plug(
            name, p_parent_plug_id=wid(parent) if parent else None,
            p_region_template_options=options, p_escape_on_http_output='N',
            p_plug_template=T[template], p_plug_display_sequence=seq,
            p_plug_display_point='SUB_REGIONS' if parent else None,
            p_plug_item_display_point='ABOVE', p_query_type='SQL', p_plug_source=sql,
            p_plug_source_type='NATIVE_IR', p_ajax_items_to_submit=items_to_submit,
            p_plug_query_headings_type='COLON_DELMITED_LIST', p_plug_query_show_nulls_as=' - ',
            p_pagination_display_position='BOTTOM_RIGHT', p_ai_enabled=False)
        wsid = self.app.ids.new()
        self.plugs.append(call('wwv_flow_imp_page.create_worksheet', [
            ('p_id', wid(wsid)), ('p_max_row_count', max_rows),
            ('p_max_row_count_message', 'This query returns more than #MAX_ROW_COUNT# rows, please filter your data to ensure complete results.'),
            ('p_no_data_found_message', 'No data found.'), ('p_allow_save_rpt_public', 'Y'),
            ('p_show_nulls_as', '-'), ('p_pagination_type', 'ROWS_X_TO_Y'),
            ('p_pagination_display_pos', 'BOTTOM_RIGHT'), ('p_report_list_mode', 'TABS'),
            ('p_lazy_loading', False), ('p_show_detail_link', 'C' if link else 'N'),
            ('p_show_notify', 'Y'), ('p_download_formats', 'CSV:HTML:XLSX:PDF'),
            ('p_enable_mail_download', 'Y'), ('p_detail_link', link),
            ('p_detail_link_text', link_text or ('<span role="img" aria-label="Edit" class="fa fa-edit" title="Edit"></span>' if link else None)),
            ('p_internal_uid', self.app.new_uid())]))
        names = []
        for i, c in enumerate(columns):
            ctype = c.get('type', 'STRING')
            names.append(c['name'])
            self.plugs.append(call('wwv_flow_imp_page.create_worksheet_column', [
                ('p_id', wid(self.app.ids.new())), ('p_db_column_name', c['name']),
                ('p_display_order', (i + 1) * 10), ('p_column_identifier', col_ident(i)),
                ('p_column_label', c.get('label', c['name'].replace('_', ' ').title())),
                ('p_column_link', c.get('link')), ('p_column_linktext', c.get('link_text')),
                ('p_column_link_attr', c.get('link_attr')),
                ('p_column_type', ctype),
                ('p_display_text_as', 'HIDDEN' if c.get('hidden') else ('WITHOUT_MODIFICATION' if c.get('html') else None)),
                ('p_heading_alignment', c.get('align', 'RIGHT' if ctype == 'NUMBER' else 'LEFT')),
                ('p_column_alignment', c.get('align', 'RIGHT' if ctype == 'NUMBER' else None)),
                ('p_format_mask', c.get('mask', 'DD-MON-YYYY' if ctype == 'DATE' else None)),
                ('p_tz_dependent', 'N' if ctype == 'DATE' else None),
                ('p_use_as_row_header', 'N')]))
        visible = [c['name'] for c in columns if not c.get('hidden')]
        default = [('p_id', wid(self.app.ids.new())), ('p_application_user', 'APXWS_DEFAULT'),
                   ('p_report_seq', 10), ('p_report_alias', self.app.new_alias()), ('p_status', 'PUBLIC'),
                   ('p_is_default', 'Y'), ('p_display_rows', rows), ('p_report_columns', ':'.join(visible))]
        if sort:
            default += [('p_sort_column_1', sort[0]), ('p_sort_direction_1', sort[1])]
        self.plugs.append(call('wwv_flow_imp_page.create_worksheet_rpt', default))
        for n, rep in enumerate(reports or [], 2):
            rp = [('p_id', wid(self.app.ids.new())), ('p_application_user', 'APXWS_ALTERNATIVE'),
                  ('p_name', rep['name']), ('p_report_seq', n * 10), ('p_report_alias', self.app.new_alias()),
                  ('p_status', 'PUBLIC'), ('p_is_default', 'Y'), ('p_display_rows', rep.get('rows', 50)),
                  ('p_report_columns', ':'.join(rep['columns']))]
            if rep.get('sort'):
                rp += [('p_sort_column_1', rep['sort'][0]), ('p_sort_direction_1', rep['sort'][1])]
            if rep.get('break_on'):
                rp += [('p_break_on', rep['break_on']), ('p_break_enabled_on', rep['break_on'])]
            if rep.get('sum'):
                rp += [('p_sum_columns_on_break', rep['sum'])]
            self.plugs.append(call('wwv_flow_imp_page.create_worksheet_rpt', rp))
        if STYLE['ir_print']:
            # every row of the report, with the user's filters, on a page made for printing (page 901)
            self.button('PRINT_REPORT', 'Print', rid, action='REDIRECT_URL', position='RIGHT_OF_IR_SEARCH_BAR',
                        seq=5, icon='fa-print', url="javascript:rounds.printReport('%s');" % self.plug_sids[rid])
        return rid

    def classic(self, name, sql, columns, seq=10, template='region_standard', options='#DEFAULT#',
                comp_options='#DEFAULT#:t-Report--altRowsDefault:t-Report--rowHighlight', rows=50,
                no_data='No data found.', items_to_submit=None, parent=None, grid=None, new_row=None,
                headings='COLON_DELMITED_LIST', sid=None, css=None):
        """columns: list of dicts {name, label, align, format, link, link_text, link_attr, html, hidden}"""
        rid = self.app.ids.new()
        self.plug_sids[rid] = static_id(sid or name, self.sids['plug'])
        self.plugs.append(call('wwv_flow_imp_page.create_report_region', [
            ('p_id', wid(rid)), ('p_name', name),
            ('p_static_id', self.plug_sids[rid]),
            ('p_parent_plug_id', wid(parent) if parent else None),
            ('p_template', T[template]), ('p_display_sequence', seq), ('p_region_css_classes', css),
            ('p_region_template_options', options), ('p_component_template_options', comp_options),
            ('p_new_grid_row', new_row), ('p_grid_column_span', grid),
            ('p_display_point', 'SUB_REGIONS' if parent else None),
            ('p_source_type', 'NATIVE_SQL_REPORT'), ('p_query_type', 'SQL'), ('p_source', sql),
            ('p_ajax_enabled', 'Y'), ('p_ajax_items_to_submit', items_to_submit),
            ('p_lazy_loading', False), ('p_query_row_template', T['report_standard']),
            ('p_query_headings_type', headings), ('p_query_num_rows', rows),
            ('p_query_options', 'DERIVED_REPORT_COLUMNS'), ('p_query_show_nulls_as', ' - '),
            ('p_query_no_data_found', no_data), ('p_query_num_rows_type', 'NEXT_PREVIOUS_LINKS'),
            ('p_pagination_display_position', 'BOTTOM_RIGHT'), ('p_csv_output', 'N'),
            ('p_prn_output', 'N'), ('p_sort_null', 'L'), ('p_plug_query_strip_html', 'N')]))
        for i, c in enumerate(columns, 1):
            self.plugs.append(call('wwv_flow_imp_page.create_report_columns', [
                ('p_id', wid(self.app.ids.new())), ('p_query_column_id', i), ('p_column_alias', c['name']),
                ('p_column_display_sequence', i),
                ('p_column_heading', c.get('label', c['name'].replace('_', ' ').title())),
                ('p_column_format', c.get('format')), ('p_column_html_expression', c.get('html')),
                ('p_column_link', c.get('link')), ('p_column_linktext', c.get('link_text')),
                ('p_column_link_attr', c.get('link_attr')),
                ('p_column_alignment', c.get('align')), ('p_heading_alignment', c.get('align', 'LEFT')),
                ('p_hidden_column', 'Y' if c.get('hidden') else None),
                ('p_derived_column', 'N'), ('p_include_in_export', 'Y')]))
        return rid

    def ig(self, name, sql, columns, seq=10, items_to_submit=None, edit_ops='u', template='region_standard',
           options='#DEFAULT#', cond_type=None, cond=None):
        """Editable interactive grid, laid out like the grids App Builder creates.
        columns: dicts {name, label, type (VARCHAR2|NUMBER|DATE|ROWID), kind (text|textarea|display|hidden),
        pk, maxlen, required, width}. Returns the region id (for the NATIVE_IG_DML process)."""
        # APEX refuses a page with an editable grid that reloads on every submit (Tariff Version showed it)
        self.head = [(k, 'S' if k == 'p_reload_on_submit' else v) for k, v in self.head]
        rid = self._plug(
            name, p_region_template_options=options, p_escape_on_http_output='N', p_plug_template=T[template],
            p_plug_display_sequence=seq, p_plug_item_display_point='ABOVE', p_query_type='SQL',
            p_plug_source=sql, p_plug_source_type='NATIVE_IG', p_ajax_items_to_submit=items_to_submit,
            p_plug_query_headings_type='COLON_DELMITED_LIST', p_plug_display_condition_type=cond_type,
            p_plug_display_when_condition=cond)
        cols = []
        sel = self.app.ids.new()
        self.plugs.append(call('wwv_flow_imp_page.create_region_column', [
            ('p_id', wid(sel)), ('p_name', 'APEX$ROW_SELECTOR'), ('p_session_state_data_type', 'VARCHAR2'),
            ('p_item_type', 'NATIVE_ROW_SELECTOR'), ('p_display_sequence', 10),
            ('p_attributes', attrs({'enable_multi_select': 'Y', 'hide_control': 'N', 'show_select_all': 'Y'})),
            ('p_use_as_row_header', False), ('p_enable_hide', True), ('p_include_in_export', True)]))
        act = self.app.ids.new()
        self.plugs.append(call('wwv_flow_imp_page.create_region_column', [
            ('p_id', wid(act)), ('p_name', 'APEX$ROW_ACTION'), ('p_session_state_data_type', 'VARCHAR2'),
            ('p_item_type', 'NATIVE_ROW_ACTION'), ('p_label', 'Actions'), ('p_heading_alignment', 'LEFT'),
            ('p_display_sequence', 20), ('p_value_alignment', 'CENTER'), ('p_use_as_row_header', False),
            ('p_enable_hide', True), ('p_include_in_export', True)]))
        cols.append((act, True, None))
        for i, c in enumerate(columns, 3):
            cid = self.app.ids.new()
            kind = 'hidden' if c.get('pk') else c.get('kind', 'text')
            dtype = c.get('type', 'VARCHAR2')
            item_type, a = {
                'text': ('NATIVE_TEXT_FIELD', {'trim_spaces': 'BOTH'}),
                'textarea': ('NATIVE_TEXTAREA', {'auto_height': 'N', 'character_counter': 'N', 'resizable': 'Y',
                                                 'trim_spaces': 'BOTH'}),
                'display': ('NATIVE_DISPLAY_ONLY', {'based_on': 'VALUE', 'format': 'PLAIN'}),
                # markup made by the query (a coloured flag), shown as it is
                'html': ('NATIVE_DISPLAY_ONLY', {'based_on': 'VALUE', 'format': 'HTML'}),
                'hidden': ('NATIVE_HIDDEN', {'value_protected': 'Y'}),
                'number': ('NATIVE_NUMBER_FIELD', {'number_alignment': 'right', 'virtual_keyboard': 'decimal'}),
                # a select list on a shared list of values (c['lov'] = its id)
                'select': ('NATIVE_SELECT_LIST', None),
            }[kind]
            p = [('p_id', wid(cid)), ('p_name', c['name']), ('p_source_type', 'DB_COLUMN'),
                 ('p_source_expression', c['name']), ('p_data_type', dtype), ('p_session_state_data_type', 'VARCHAR2')]
            if c.get('pk'):
                p += [('p_item_type', item_type), ('p_display_sequence', i * 10), ('p_attributes', attrs(a)),
                      ('p_use_as_row_header', False), ('p_enable_sort_group', False),
                      ('p_enable_control_break', False), ('p_enable_hide', True), ('p_is_primary_key', True),
                      ('p_include_in_export', False)]
            else:
                editable = kind in ('text', 'textarea', 'number', 'select')
                p += [('p_is_query_only', not editable), ('p_item_type', item_type)]
                if kind != 'hidden':
                    p += [('p_heading', c.get('label', c['name'].replace('_', ' ').title())),
                          ('p_heading_alignment', 'LEFT')]
                p += [('p_display_sequence', i * 10)]
                if kind != 'hidden':
                    p += [('p_value_alignment', 'RIGHT' if dtype == 'NUMBER' else 'LEFT')]
                if a is not None:
                    p += [('p_attributes', attrs(a))]
                if kind == 'select':
                    p += [('p_lov_type', 'SHARED'), ('p_lov_id', wid(c['lov'])), ('p_lov_display_extra', False),
                          ('p_lov_display_null', True), ('p_lov_null_text', c.get('null_text', '- choose -'))]
                if editable:
                    p += [('p_is_required', bool(c.get('required'))), ('p_max_length', c.get('maxlen', 4000))]
                if kind != 'hidden':
                    p += [('p_enable_filter', True),
                          ('p_filter_operators', 'C:S:CASE_INSENSITIVE:REGEXP' if dtype == 'VARCHAR2' else None),
                          ('p_filter_is_required', False),
                          ('p_filter_text_case', 'MIXED' if dtype == 'VARCHAR2' else None),
                          ('p_filter_exact_match', True), ('p_filter_lov_type', 'NONE')]
                p += [('p_use_as_row_header', False), ('p_enable_sort_group', kind != 'hidden'),
                      ('p_enable_control_break', kind != 'hidden'), ('p_enable_hide', True),
                      ('p_is_primary_key', False), ('p_duplicate_value', True), ('p_include_in_export', True)]
            self.plugs.append(call('wwv_flow_imp_page.create_region_column', p))
            cols.append((cid, kind != 'hidden' or c.get('pk'), c.get('width')))
        gid = self.app.ids.new()
        self.plugs.append(call('wwv_flow_imp_page.create_interactive_grid', [
            ('p_id', wid(gid)), ('p_internal_uid', self.app.new_uid()), ('p_is_editable', True),
            ('p_edit_operations', edit_ops), ('p_lost_update_check_type', 'VALUES'),
            ('p_submit_checked_rows', False), ('p_lazy_loading', False), ('p_requires_filter', False),
            ('p_max_row_count', 100000), ('p_show_nulls_as', '-'), ('p_select_first_row', True),
            ('p_fixed_row_height', True), ('p_pagination_type', 'SCROLL'), ('p_show_total_row_count', True),
            ('p_show_toolbar', True), ('p_enable_save_public_report', False), ('p_enable_subscriptions', True),
            ('p_enable_flashback', True), ('p_define_chart_view', True), ('p_enable_download', True),
            ('p_download_formats', 'CSV:HTML:XLSX:PDF'), ('p_enable_mail_download', True),
            ('p_fixed_header', 'PAGE'), ('p_show_icon_view', False), ('p_show_detail_view', False)]))
        rep = self.app.ids.new()
        self.plugs.append(call('wwv_flow_imp_page.create_ig_report', [
            ('p_id', wid(rep)), ('p_interactive_grid_id', wid(gid)), ('p_static_id', self.app.new_alias()),
            ('p_type', 'PRIMARY'), ('p_default_view', 'GRID'), ('p_show_row_number', False),
            ('p_settings_area_expanded', True)]))
        view = self.app.ids.new()
        self.plugs.append(call('wwv_flow_imp_page.create_ig_report_view', [
            ('p_id', wid(view)), ('p_report_id', wid(rep)), ('p_view_type', 'GRID'), ('p_stretch_columns', True),
            ('p_srv_exclude_null_values', False), ('p_srv_only_display_columns', True), ('p_edit_mode', False)]))
        for n, (cid, visible, width) in enumerate(cols, 1):
            self.plugs.append(call('wwv_flow_imp_page.create_ig_report_column', [
                ('p_id', wid(self.app.ids.new())), ('p_view_id', wid(view)), ('p_display_seq', n),
                ('p_column_id', wid(cid)), ('p_is_visible', bool(visible)), ('p_is_frozen', False),
                ('p_width', width)]))
        return rid

    def chart(self, name, sql, label_col, value_col, series='Series', ctype='bar', seq=10,
              grid=None, new_row=None, orientation='vertical', items_to_submit=None, height_class='i-h320',
              color=None, parent=None, sorting='label-asc', css=None, extra_series=()):
        """sorting None keeps the order of the query; extra_series: (name, sql, color) of more series with the
        same label and value columns, shown with a legend. color 'points' gives every bar or slice a colour of
        CHART_PALETTE, by its label in alphabetical order (a label keeps its colour whatever the bars' order)."""
        legend = bool(extra_series)
        if color == 'points':
            sql = point_colors(sql, label_col)
            color = '&CHART_COLOR.'
            legend = legend or ctype in ('pie', 'donut')      # a slice is named by the legend
        rid = self._plug(
            name, p_parent_plug_id=wid(parent) if parent else None, p_region_css_classes=css,
            p_region_template_options='#DEFAULT#:t-Region--scrollBody:' + height_class,
            p_escape_on_http_output='Y', p_plug_template=T['region_standard'],
            p_plug_display_sequence=seq, p_plug_new_grid_row=new_row, p_plug_grid_column_span=grid,
            p_plug_display_point='SUB_REGIONS' if parent else None,
            p_plug_item_display_point='ABOVE', p_plug_source_type='NATIVE_JET_CHART',
            p_ajax_items_to_submit=items_to_submit, p_plug_query_headings_type='COLON_DELMITED_LIST')
        cid = self.app.ids.new()
        self.plugs.append(call('wwv_flow_imp_page.create_jet_chart', [
            ('p_id', wid(cid)), ('p_region_id', wid(rid)), ('p_chart_type', ctype),
            ('p_animation_on_display', 'none'), ('p_animation_on_data_change', 'none'),
            ('p_orientation', orientation), ('p_data_cursor', 'auto'), ('p_data_cursor_behavior', 'auto'),
            ('p_hover_behavior', 'none'), ('p_stack', 'off'), ('p_stack_label', 'off'),
            ('p_spark_chart', 'N'), ('p_connect_nulls', 'Y'), ('p_value_position', 'auto'),
            ('p_sorting', sorting), ('p_fill_multi_series_gaps', True), ('p_zoom_and_scroll', 'off'),
            ('p_tooltip_rendered', 'Y'), ('p_show_series_name', False), ('p_show_group_name', True),
            ('p_show_value', True), ('p_show_label', True), ('p_show_row', True), ('p_show_start', True),
            ('p_show_end', True), ('p_show_progress', True), ('p_show_baseline', True),
            ('p_legend_rendered', 'on' if legend else 'off'), ('p_legend_position', 'top' if legend else 'auto'),
            ('p_overview_rendered', 'off'),
            ('p_horizontal_grid', 'auto'), ('p_vertical_grid', 'auto'), ('p_gauge_orientation', 'circular'),
            ('p_gauge_plot_area', 'on'), ('p_show_gauge_value', True)]))
        used = set()
        self.plugs.append(call('wwv_flow_imp_page.create_jet_chart_series', [
            ('p_id', wid(self.app.ids.new())), ('p_chart_id', wid(cid)),
            ('p_static_id', static_id(series, used)), ('p_seq', 10), ('p_name', series),
            ('p_data_source_type', 'SQL'), ('p_data_source', sql),
            ('p_ajax_items_to_submit', items_to_submit), ('p_color', color),
            ('p_items_value_column_name', value_col), ('p_items_label_column_name', label_col),
            ('p_assigned_to_y2', 'off'), ('p_items_label_rendered', False),
            ('p_items_label_display_as', 'PERCENT'), ('p_threshold_display', 'onIndicator')]))
        for n, (xname, xsql, xcolor) in enumerate(extra_series, 2):
            self.plugs.append(call('wwv_flow_imp_page.create_jet_chart_series', [
                ('p_id', wid(self.app.ids.new())), ('p_chart_id', wid(cid)),
                ('p_static_id', static_id(xname, used)), ('p_seq', n * 10), ('p_name', xname),
                ('p_data_source_type', 'SQL'), ('p_data_source', xsql),
                ('p_ajax_items_to_submit', items_to_submit), ('p_color', xcolor),
                ('p_items_value_column_name', value_col), ('p_items_label_column_name', label_col),
                ('p_assigned_to_y2', 'off'), ('p_items_label_rendered', False),
                ('p_items_label_display_as', 'PERCENT'), ('p_threshold_display', 'onIndicator')]))
        for axis in ('x', 'y'):
            params = [('p_id', wid(self.app.ids.new())), ('p_chart_id', wid(cid)),
                      ('p_static_id', axis), ('p_axis', axis), ('p_is_rendered', 'on'),
                      ('p_format_scaling', 'auto' if axis == 'x' else 'none'), ('p_scaling', 'linear'),
                      ('p_baseline_scaling', 'zero')]
            if axis == 'y':
                params.append(('p_position', 'auto'))
            params += [('p_major_tick_rendered', 'auto' if axis == 'x' else 'on'),
                       ('p_minor_tick_rendered', 'on' if axis == 'x' else 'off'),
                       ('p_tick_label_rendered', 'on')]
            if axis == 'x':
                params += [('p_tick_label_rotation', 'auto'), ('p_tick_label_position', 'outside')]
            params += [('p_zoom_order_%s' % z, False) for z in
                       ('seconds', 'minutes', 'hours', 'days', 'weeks', 'months', 'quarters', 'years')]
            self.plugs.append(call('wwv_flow_imp_page.create_jet_chart_axis', params))
        return rid

    # ------------------------------------------------------------ buttons, branches
    def button(self, name, label, region, action='SUBMIT', position='NEXT', seq=10, hot=False,
               url=None, icon=None, cond_type=None, cond=None, db_action=None, options='#DEFAULT#',
               template=None, auth=None, validations=None, confirm=None):
        bid = self.app.ids.new()
        if icon and template is None and options == '#DEFAULT#':
            options = '#DEFAULT#:t-Button--iconLeft'   # "Text with Icon" shows the icon on one side only
        self.button_sids[bid] = static_id(name, self.sids['button'])
        self.buttons.append(call('wwv_flow_imp_page.create_page_button', [
            ('p_id', wid(bid)), ('p_button_sequence', seq), ('p_button_plug_id', wid(region)),
            ('p_button_name', name), ('p_static_id', self.button_sids[bid]),
            ('p_button_static_id', self.button_sids[bid] if STYLE['button_ids'] else None),
            ('p_button_action', action), ('p_button_template_options', options),
            ('p_button_template_id', template or (T['button_text_icon'] if icon else T['button_text'])),
            ('p_button_is_hot', 'Y' if hot else None), ('p_button_image_alt', label),
            ('p_button_position', position), ('p_button_redirect_url', url),
            ('p_button_execute_validations', validations),
            ('p_warn_on_unsaved_changes', Raw('null') if action in ('DEFINED_BY_DA', 'REDIRECT_URL') else None),
            ('p_button_condition', cond), ('p_button_condition_type', cond_type),
            ('p_button_condition2', 'PLSQL' if cond_type == 'EXPRESSION' else None),
            ('p_database_action', db_action), ('p_security_scheme', wid(auth) if auth else None),
            ('p_icon_css_classes', icon)]))
        return bid

    def branch(self, url, seq=10, button=None, name='Go To Page', cond_type=None, cond=None):
        self.branches.append(call('wwv_flow_imp_page.create_page_branch', [
            ('p_id', wid(self.app.ids.new())), ('p_branch_name', name), ('p_branch_action', url),
            ('p_branch_point', 'AFTER_PROCESSING'), ('p_branch_type', 'REDIRECT_URL'),
            ('p_branch_when_button_id', wid(button) if button else None),
            ('p_branch_sequence', seq), ('p_branch_condition_type', cond_type),
            ('p_branch_condition', cond)]))

    # ------------------------------------------------------------ items
    def item(self, name, region, kind='text', label=None, seq=None, source=None, source_type=None,
             required=False, size=None, maxlen=None, height=None, lov=None, named_lov=None,
             lov_null=None, default=None, default_type=None, default_lang=None, mask=None,
             new_line=None, colspan=None, template=None, protection=None, help_text=None,
             readonly_type=None, readonly=None, css=None, placeholder=None, cascade=None,
             inline_help=None, persistent=None, post_text=None, icon=None, source_lang=None,
             display_when_type=None, display_when=None, grid_column=None, label_span=None, attrs_=None,
             tag_attrs=None):
        """kind: text, number, date, textarea, select, popup, radio, hidden, display, yesno,
        password, checkbox. attrs_ overrides the item type attributes."""
        if name in self.item_names:
            raise ValueError('duplicate item ' + name)
        self.item_names.add(name)
        seq = seq or (len(self.items) + 1) * 10
        display_as, a = {
            'text': ('NATIVE_TEXT_FIELD', {'disabled': 'N', 'submit_when_enter_pressed': 'N',
                                           'subtype': 'TEXT', 'trim_spaces': 'BOTH'}),
            'number': ('NATIVE_NUMBER_FIELD', {'number_alignment': 'right', 'virtual_keyboard': 'decimal'}),
            'date': ('NATIVE_DATE_PICKER_APEX', {'display_as': 'POPUP', 'max_date': 'NONE',
                                                 'min_date': 'NONE', 'multiple_months': 'N',
                                                 'show_time': 'N', 'use_defaults': 'Y'}),
            'textarea': ('NATIVE_TEXTAREA', {'auto_height': 'N', 'character_counter': 'N',
                                             'resizable': 'Y', 'trim_spaces': 'BOTH'}),
            'select': ('NATIVE_SELECT_LIST', {'page_action_on_selection': 'NONE'}),
            'popup': ('NATIVE_POPUP_LOV', {'case_sensitive': 'N', 'display_as': 'DIALOG',
                                           'fetch_on_search': 'Y', 'initial_fetch': 'FIRST_ROWSET',
                                           'manual_entry': 'N', 'match_type': 'CONTAINS',
                                           'min_chars': '0'}),
            'radio': ('NATIVE_RADIOGROUP', {'number_of_columns': '6', 'page_action_on_selection': 'NONE'}),
            'hidden': ('NATIVE_HIDDEN', {'value_protected': 'N'}),
            'hidden_protected': ('NATIVE_HIDDEN', {'value_protected': 'Y'}),
            # not sent on submit: submitted display values are checksummed, so a value filled in by a
            # dynamic action raises "Session state protection violation" on the next submit; the
            # server code of the dynamic actions / processes keeps their session state instead
            'display': ('NATIVE_DISPLAY_ONLY', {'based_on': 'VALUE', 'format': 'PLAIN',
                                                'send_on_page_submit': 'N', 'show_line_breaks': 'Y'}),
            'yesno': ('NATIVE_YES_NO', {'use_defaults': 'Y'}),
            'password': ('NATIVE_PASSWORD', {'submit_when_enter_pressed': 'Y'}),
            'checkbox': ('NATIVE_CHECKBOX', {'number_of_columns': '1'}),
            'file': ('NATIVE_FILE', {'allow_multiple_files': 'N', 'display_as': 'DROPZONE_INLINE',
                                     'dropzone_title': 'Choose or drop the file', 'file_types': '.csv',
                                     'purge_file_at': 'REQUEST', 'storage_type': 'APEX_APPLICATION_TEMP_FILES'}),
        }[kind]
        if attrs_:
            a = dict(a, **attrs_)
        hidden = kind.startswith('hidden')
        if template is None and not hidden:
            # floating / above labels take no label grid columns, so 2-column items stay valid
            # (side labels raise "label column span ... only has 2 Column(s) available")
            if STYLE['labels'] == 'above':
                template = T['label_required_above'] if required else T['label_optional_above']
            else:
                template = T['label_required_floating'] if required else T['label_optional_floating']
        params = [('p_id', wid(self.app.ids.new())), ('p_name', name),
                  ('p_is_required', True if required else None), ('p_item_sequence', seq),
                  ('p_item_plug_id', wid(region)), ('p_use_cache_before_default', 'NO' if source_type == 'DB_COLUMN' else None),
                  ('p_item_default', default), ('p_item_default_type', default_type),
                  ('p_item_default_language', default_lang),
                  ('p_prompt', None if hidden else (label or name)), ('p_placeholder', placeholder),
                  ('p_post_element_text', post_text), ('p_format_mask', mask or ('DD-MON-YYYY' if kind == 'date' else None)),
                  ('p_source', source), ('p_source_type', source_type), ('p_source_language', source_lang),
                  ('p_display_as', display_as), ('p_named_lov', named_lov), ('p_lov', lov),
                  ('p_lov_display_null', 'YES' if lov_null is not None else None),
                  ('p_lov_null_text', lov_null if lov_null else None),
                  ('p_lov_cascade_parent_items', cascade),
                  ('p_ajax_optimize_refresh', 'Y' if cascade else None),
                  ('p_cSize', size), ('p_cMaxlength', maxlen), ('p_cHeight', height),
                  ('p_tag_css_classes', css), ('p_tag_attributes', tag_attrs), ('p_begin_on_new_line', new_line),
                  ('p_colspan', colspan),
                  ('p_grid_column', grid_column), ('p_grid_label_column_span', label_span),
                  ('p_field_template', template), ('p_item_icon_css_classes', icon),
                  ('p_item_template_options', None if hidden else
                   ('#DEFAULT#:t-Form-fieldContainer--stretchInputs' if STYLE['stretch'] else '#DEFAULT#')),
                  # migrated rows may hold values that are no longer in the master tables
                  ('p_lov_display_extra', 'YES' if kind in ('select', 'popup', 'radio', 'checkbox') else None),
                  ('p_read_only_when', readonly), ('p_read_only_when_type', readonly_type),
                  ('p_read_only_when2', 'PLSQL' if readonly_type == 'EXPRESSION' else None),
                  ('p_display_when', display_when), ('p_display_when_type', display_when_type),
                  ('p_display_when2', 'PLSQL' if display_when_type == 'EXPRESSION' else None),
                  # items stay "Unrestricted": checksum-protected items cannot be sent by Ajax requests
                  # (charts, dynamic actions, cascading LOVs, report refresh -> ORA-20987)
                  ('p_is_persistent', persistent), ('p_protection_level', protection),
                  ('p_help_text', help_text), ('p_inline_help_text', inline_help),
                  ('p_attributes', attrs(a))]
        if kind == 'checkbox':
            params += [('p_multi_value_type', 'SEPARATED'), ('p_multi_value_separator', ':')]
        self.items.append(call('wwv_flow_imp_page.create_page_item', params))

    # ------------------------------------------------------------ logic
    def computation(self, item, ctype, value, point='BEFORE_HEADER', seq=10, lang=None,
                    when_type=None, when=None):
        self.comps.append(call('wwv_flow_imp_page.create_page_computation', [
            ('p_id', wid(self.app.ids.new())), ('p_computation_sequence', seq),
            ('p_computation_item', item), ('p_static_id', static_id(item, self.sids['comp'])),
            ('p_computation_point', point), ('p_computation_type', ctype),
            ('p_computation_language', lang), ('p_computation', value),
            ('p_compute_when', when), ('p_compute_when_type', when_type)]))

    def validation(self, name, vtype, expr, message, seq=10, item=None, button=None, cond_type=None,
                   cond=None, expr2=None):
        self.vals.append(call('wwv_flow_imp_page.create_page_validation', [
            ('p_id', wid(self.app.ids.new())), ('p_validation_name', name),
            ('p_static_id', static_id(name, self.sids['val'])), ('p_validation_sequence', seq),
            ('p_validation', expr), ('p_validation2', expr2), ('p_validation_type', vtype),
            ('p_error_message', message), ('p_validation_condition', cond),
            ('p_validation_condition_type', cond_type),
            ('p_validation_condition2', 'PLSQL' if cond_type == 'EXPRESSION' else None),
            ('p_when_button_pressed', wid(button) if button else None),
            ('p_associated_item', wid(item) if isinstance(item, int) else None),
            ('p_error_display_location', 'INLINE_WITH_FIELD_AND_NOTIFICATION' if item else 'INLINE_IN_NOTIFICATION')]))

    def process(self, name, plsql=None, ptype='NATIVE_PLSQL', point='AFTER_SUBMIT', seq=10,
                button=None, when_type=None, when=None, success=None, error=None, attrs_=None,
                region=None):
        self.procs.append(call('wwv_flow_imp_page.create_page_process', [
            ('p_id', wid(self.app.ids.new())), ('p_process_sequence', seq),
            ('p_process_point', point), ('p_region_id', wid(region) if region else None),
            ('p_process_type', ptype), ('p_process_name', name),
            ('p_static_id', static_id(name, self.sids['proc'])),
            ('p_process_sql_clob', plsql), ('p_process_clob_language', 'PLSQL' if plsql else None),
            ('p_attributes', attrs(attrs_) if attrs_ else None),
            ('p_process_error_message', error), ('p_process_when_button_id', wid(button) if button else None),
            ('p_process_when', when), ('p_process_when_type', when_type),
            ('p_process_when2', 'PLSQL' if when_type == 'EXPRESSION' else None),
            ('p_process_success_message', success),
            ('p_error_display_location', 'INLINE_IN_NOTIFICATION'),
            ('p_internal_uid', self.app.new_uid())]))

    def da(self, name, event, actions, element_type=None, element=None, button=None, seq=None,
           cond_type=None, cond_expr=None, selector=None):
        """actions: list of dicts {action, result('TRUE'), items, region, attrs, init, wait}"""
        eid = self.app.ids.new()
        seq = seq or (len(self.das) + 1) * 10
        self.das.append(call('wwv_flow_imp_page.create_page_da_event', [
            ('p_id', wid(eid)), ('p_name', name), ('p_static_id', static_id(name, self.sids['da'])),
            ('p_event_sequence', seq), ('p_triggering_element_type', element_type),
            ('p_triggering_element', element), ('p_triggering_button_id', wid(button) if button else None),
            ('p_triggering_condition_type', cond_type), ('p_triggering_expression', cond_expr),
            ('p_bind_type', 'bind'), ('p_execution_type', 'IMMEDIATE'), ('p_bind_event_type', event)]))
        for n, act in enumerate(actions, 1):
            a = act['action']
            aff_type = 'ITEM' if act.get('items') else ('REGION' if act.get('region') else None)
            self.das.append(call('wwv_flow_imp_page.create_page_da_action', [
                ('p_id', wid(self.app.ids.new())), ('p_event_id', wid(eid)),
                ('p_event_result', act.get('result', 'TRUE')), ('p_action_sequence', n * 10),
                ('p_execute_on_page_init', act.get('init', 'N')),
                ('p_static_id', static_id(a.lower().replace('_', '-'), self.sids['act'])),
                ('p_action', a), ('p_affected_elements_type', aff_type),
                ('p_affected_elements', act.get('items')),
                ('p_affected_region_id', wid(act['region']) if act.get('region') else None),
                ('p_attributes', attrs(act['attrs']) if act.get('attrs') else None),
                ('p_wait_for_result', act.get('wait'))]))
        return eid

    def plsql_da(self, name, element, plsql, submit, ret, event='change', element_type='ITEM', button=None):
        return self.da(name, event, [{'action': 'NATIVE_EXECUTE_PLSQL_CODE', 'wait': 'Y',
                                      'attrs': {'items_to_return': ret, 'items_to_submit': submit,
                                                'language': 'PLSQL', 'plsql_code': plsql,
                                                'show_processing': 'N',
                                                # returned items must not re-fire change DAs (no loops)
                                                'suppress_change_event': 'Y' if ret else None}}],
                       element_type=None if button else element_type, element=None if button else element,
                       button=button)

    # ------------------------------------------------------------ render
    def render(self, exp):
        exp.prompt('pages/page_%05d' % self.id)
        exp.block(call('wwv_flow_imp_page.create_page', self.head), *self.plugs, *self.buttons,
                  *self.branches, *self.items, *self.comps, *self.vals, *self.das, *self.procs)
