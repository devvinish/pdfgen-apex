#!/usr/bin/env python3
"""Generate the PDF Report Designer Oracle APEX 26.1 application export.

Writes dist/pdf_report_designer.sql           the application with its supporting objects (all of sql/)
       local/pdf_report_designer_test.sql     a copy without login, for local testing only

Usage: tools/gen_app.py [--app-id 2000]
"""
import argparse
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, 'apex'))

from components import T, App, Page  # noqa: E402
from emit import Export, Ids, Raw, attrs, call, hex_table, static_id, varchar2_table, wid  # noqa: E402
import demo_pages  # noqa: E402

VERSION_DATE = '2026.03.30'
RELEASE = '26.1.1'
APP_NAME = 'PDF Report Designer'
APP_ALIAS = 'PDF_DESIGNER'
OWNER = 'PDFGEN'
VERSION = '1.0'

SQL_SCRIPTS = ['10_tables.sql', '20_pdf_writer.sql', '30_pdf_engine.sql', '40_pdf_api.sql',
               '45_pdf_designer.sql', '50_demo_data.sql', '60_samples.sql']
DROPS = ['PACKAGE PDF_DESIGNER', 'PACKAGE PDF_API', 'PACKAGE PDF_REPO', 'PACKAGE PDF_ENGINE', 'PACKAGE PDF_WRITER',
         'TABLE PDF_DEMO_INVOICE_LINES', 'TABLE PDF_DEMO_INVOICES', 'TABLE PDF_DEMO_PRODUCTS',
         'TABLE PDF_DEMO_CUSTOMERS', 'TABLE PDF_LOG', 'TABLE PDF_IMAGES', 'TABLE PDF_QUERIES', 'TABLE PDF_REPORTS']

STATIC = [('css/designer.css', 'text/css', os.path.join(ROOT, 'app', 'designer.css')),
          ('js/designer.js', 'text/javascript', os.path.join(ROOT, 'app', 'designer.js'))]

PLUGIN_SETTINGS = [
    ('ITEM TYPE', 'NATIVE_SINGLE_CHECKBOX', {'checked_value': 'Y', 'unchecked_value': 'N'}),
    ('ITEM TYPE', 'NATIVE_YES_NO', {'display_style': 'SWITCH', 'off_value': 'N', 'on_value': 'Y'}),
    ('REGION TYPE', 'NATIVE_IR', {'actions_menu_structure': 'IG'}),
]
TEMPLATE_OPT_GROUPS = [
    ('PRESERVE_LABEL_SPACING', 'preserve-label-spacing', 'Preserve Label Spacing', 1, 'FIELD',
     'Preserves the label space and enables use of the Label Column Span property.', 'Yes'),
    ('DISPLAY_MODE', 'display-mode', 'Display Mode', 30, 'PAGE',
     'Determines the default display appearance and positioning of the dialog. The default opens a floating dialog position at the center of the screen.',
     'Default'),
]


class Ctx:
    def __init__(self, app):
        new = app.ids.new
        self.app = app
        self.auth_id = new()
        self.nav_list = new()
        self.navbar_list = new()
        self.menu = new()
        self.theme = new()
        self.install = new()
        self.lov_reports = new()
        self.group_main = new()
        self.group_demo = new()
        self.demo_auth = new()
        self.demo_lovs = {n: new() for n in demo_pages.LOVS}
        self.lov_products = self.demo_lovs['DEMO_PRODUCTS']


def files_version():
    data = b''.join(open(p, 'rb').read() for _, _, p in STATIC)
    return int(hashlib.sha256(data).hexdigest()[:6], 16) % 900000 + 100


# ------------------------------------------------------------------ shared components
def header(exp, app_id):
    exp.raw('prompt --application/set_environment\nset define off verify off feedback off\n'
            'whenever sqlerror exit sql.sqlcode rollback\n' + '-' * 80 + '\n--\n'
            '-- Oracle APEX export file - PDF Report Designer\n'
            '--\n-- Import it with App Builder > Import. Choose "Install Supporting Objects" to create the\n'
            '-- PDF_* tables and packages, the demo tables and the sample reports in the parsing schema.\n'
            '--\n' + '-' * 80)
    exp.block(call('wwv_flow_imp.import_begin ', [
        ('p_version_yyyy_mm_dd', VERSION_DATE), ('p_release', RELEASE),
        ('p_default_workspace_id', 1845521730123456789), ('p_default_application_id', app_id),
        ('p_default_id_offset', 0), ('p_default_owner', OWNER)]))
    exp.raw(' \nprompt APPLICATION %d - %s' % (app_id, APP_NAME))
    exp.prompt('delete_application')
    exp.block('wwv_flow_imp.remove_flow(wwv_flow.g_flow_id);')


def application(exp, ctx, alias, name):
    salt = hashlib.sha256(b'pdf-report-designer').hexdigest().upper()
    exp.prompt('create_application')
    exp.block(call('wwv_imp_workspace.create_flow', [
        ('p_id', Raw('wwv_flow.g_flow_id')),
        ('p_owner', Raw("nvl(wwv_flow_application_install.get_schema,'%s')" % OWNER)),
        ('p_name', Raw("nvl(wwv_flow_application_install.get_application_name,'%s')" % name)),
        ('p_alias', Raw("nvl(wwv_flow_application_install.get_application_alias,'%s')" % alias)),
        ('p_page_view_logging', 'YES'), ('p_page_protection_enabled_y_n', 'Y'),
        ('p_checksum_salt', salt), ('p_bookmark_checksum_function', 'SH512'),
        ('p_max_session_length_sec', 28800), ('p_max_session_idle_sec', 7200),
        ('p_compatibility_mode', '24.2'), ('p_flow_language', 'en'),
        ('p_flow_language_derived_from', 'FLOW_PRIMARY_LANGUAGE'),
        ('p_date_format', 'DD-MON-YYYY'), ('p_timestamp_format', 'DS'), ('p_direction_right_to_left', 'N'),
        ('p_flow_image_prefix', Raw("nvl(wwv_flow_application_install.get_image_prefix,'')")),
        ('p_documentation_banner', 'Design PDF documents (invoices, labels, reports) on a canvas, bind them to SQL '
                                   'queries and generate them from any APEX application with pdfgen.pdf_api.'),
        ('p_authentication_id', wid(ctx.auth_id)), ('p_application_tab_set', 1),
        ('p_logo_type', 'IT'), ('p_logo_text', 'PDF Report Designer'), ('p_public_user', 'APEX_PUBLIC_USER'),
        ('p_proxy_server', Raw("nvl(wwv_flow_application_install.get_proxy,'')")),
        ('p_no_proxy_domains', Raw("nvl(wwv_flow_application_install.get_no_proxy_domains,'')")),
        ('p_flow_version', VERSION), ('p_flow_status', 'AVAILABLE_W_EDIT_LINK'),
        ('p_exact_substitutions_only', 'Y'), ('p_browser_cache', 'N'), ('p_browser_frame', 'S'),
        ('p_deep_linking', 'Y'), ('p_runtime_api_usage', 'T'), ('p_pass_ecid', 'N'),
        ('p_rejoin_existing_sessions', 'N'), ('p_csv_encoding', 'Y'), ('p_tokenize_row_search', 'N'),
        ('p_substitution_string_01', 'APP_NAME'), ('p_substitution_value_01', APP_NAME),
        ('p_file_prefix', Raw("nvl(wwv_flow_application_install.get_static_app_file_prefix,'')")),
        ('p_files_version', files_version()), ('p_print_server_type', 'INSTANCE'), ('p_file_storage', 'DB'),
        ('p_is_pwa', 'N'), ('p_theme_id', 42), ('p_home_url', 'f?p=&APP_ID.:1:&SESSION.'),
        ('p_theme_style_by_user_pref', False),
        ('p_navigation_list_id', wid(ctx.nav_list)), ('p_navigation_list_position', 'TOP'),
        ('p_navigation_list_template_id', 2528231041045349458),
        ('p_nav_list_template_options', '#DEFAULT#:js-tabLike'),
        ('p_css_file_urls', '#APP_FILES#css/designer.css'),
        ('p_nav_bar_type', 'LIST'), ('p_nav_bar_list_id', wid(ctx.navbar_list)),
        ('p_nav_bar_list_template_id', 2849019392706229583)]))


def plugin_settings(exp, ctx):
    exp.prompt('plugin_settings')
    exp.block(*[call('wwv_flow_imp_shared.create_plugin_setting', [
        ('p_id', wid(ctx.app.ids.new())), ('p_plugin_type', t), ('p_plugin', p),
        ('p_attributes', attrs(a) if a else None)]) for t, p, a in PLUGIN_SETTINGS])


# (label, page, icon, current pages, children)
NAV = [('Reports', 1, 'fa-file-pdf-o', '1,2,3', None),
       ('Demo', None, 'fa-desktop', None, [('Invoices', 10, 'fa-file-text-o', '10,11'),
                                            ('Customers', 20, 'fa-users', '20,21'),
                                            ('Products', 30, 'fa-cubes', '30,31')]),
       ('Try the API', 4, 'fa-play-circle', '4', None),
       ('Log', 6, 'fa-history', '6', None), ('How to Use', 7, 'fa-question-circle', '7', None)]


def lists(exp, ctx):
    new = ctx.app.ids.new
    used = set()
    exp.prompt('shared_components/navigation/lists/navigation_menu')
    calls = [call('wwv_flow_imp_shared.create_list', [
        ('p_id', wid(ctx.nav_list)), ('p_name', 'Navigation Menu'), ('p_static_id', 'navigation-menu')])]
    def entry(seq, label, page, ic, pages, parent=None, auth=None):
        iid = new()
        calls.append(call('wwv_flow_imp_shared.create_list_item', [
            ('p_id', wid(iid)), ('p_list_item_display_sequence', seq), ('p_list_item_link_text', label),
            ('p_static_id', static_id(label, used)),
            ('p_list_item_link_target', 'f?p=&APP_ID.:%d:&SESSION.::&DEBUG.:::' % page if page else None),
            ('p_list_item_icon', ic), ('p_parent_list_item_id', wid(parent) if parent else None),
            ('p_security_scheme', wid(auth) if auth else None),
            ('p_list_item_current_type', 'COLON_DELIMITED_PAGE_LIST' if page else 'TARGET_PAGE'),
            ('p_list_item_current_for_pages', pages)]))
        return iid

    for n, (label, page, ic, pages, kids) in enumerate(NAV, 1):
        # the Demo menu shows only when the demo tables are installed
        auth = ctx.demo_auth if label == 'Demo' else None
        parent = entry(n * 10, label, page, ic, pages, auth=auth)
        for k, (kl, kp, ki, kpages) in enumerate(kids or [], 1):
            entry(k * 10, kl, kp, ki, kpages, parent, auth=auth)
    exp.block(*calls)
    exp.prompt('shared_components/navigation/lists/navigation_bar')
    used2 = set()
    user_item = new()
    exp.block(
        call('wwv_flow_imp_shared.create_list', [
            ('p_id', wid(ctx.navbar_list)), ('p_name', 'Navigation Bar'), ('p_static_id', 'navigation-bar')]),
        call('wwv_flow_imp_shared.create_list_item', [
            ('p_id', wid(user_item)), ('p_list_item_display_sequence', 10), ('p_list_item_link_text', '&APP_USER.'),
            ('p_static_id', static_id('app-user', used2)), ('p_list_item_link_target', '#'),
            ('p_list_item_icon', 'fa-user'), ('p_list_text_02', 'has-username'),
            ('p_list_item_current_type', 'TARGET_PAGE')]),
        call('wwv_flow_imp_shared.create_list_item', [
            ('p_id', wid(new())), ('p_list_item_display_sequence', 20), ('p_list_item_link_text', 'Sign Out'),
            ('p_static_id', static_id('sign-out', used2)), ('p_list_item_link_target', '&LOGOUT_URL.'),
            ('p_list_item_icon', 'fa-sign-out'), ('p_parent_list_item_id', wid(user_item)),
            ('p_list_item_current_type', 'TARGET_PAGE')]))
    exp.prompt('shared_components/navigation/listentry')
    exp.block()


def static_files(exp, ctx):
    for name, mime, path in STATIC:
        exp.prompt('shared_components/files/' + name.replace('/', '_').replace('.', '_'))
        exp.block(hex_table(open(path, 'rb').read()), call('wwv_flow_imp_shared.create_app_static_file', [
            ('p_id', wid(ctx.app.ids.new())), ('p_file_name', name), ('p_mime_type', mime),
            ('p_file_charset', 'utf-8'),
            ('p_file_content', Raw('wwv_flow_imp.varchar2_to_blob(wwv_flow_imp.g_varchar2_table)'))]))


DEMO_INSTALLED = """-- the Demo menu and pages need the demo tables (sql/50_demo_data.sql, sql/60_samples.sql)
declare
  l number;
begin
  select count(*) into l from user_tables
   where table_name in ('PDF_DEMO_CUSTOMERS', 'PDF_DEMO_PRODUCTS', 'PDF_DEMO_INVOICES', 'PDF_DEMO_INVOICE_LINES');
  return l = 4;
end;"""


def security(exp, ctx):
    exp.prompt('shared_components/security/authorizations/demo_installed')
    exp.block(call('wwv_flow_imp_shared.create_security_scheme', [
        ('p_id', wid(ctx.demo_auth)), ('p_name', 'Demo installed'), ('p_static_id', 'demo-installed'),
        ('p_scheme_type', 'NATIVE_FUNCTION_BODY'), ('p_attributes', attrs({'plsql_function_body': DEMO_INSTALLED})),
        ('p_error_message', 'The demo is not installed: run sql/50_demo_data.sql and sql/60_samples.sql '
                            '(or import the application with its supporting objects).'),
        ('p_caching', 'BY_USER_BY_PAGE_VIEW')]))


# the Ajax calls of the designer (app/designer.js)
PROCESSES = [
    ('LOAD_REPORT', 'pdf_designer.load_report(apex_application.g_x01);'),
    ('SAVE_REPORT', 'pdf_designer.save_report(apex_application.g_x01, apex_application.g_clob_01);'),
    ('DESCRIBE_QUERY', 'pdf_designer.describe_query(apex_application.g_clob_01);'),
    ('PREVIEW', 'pdf_designer.preview(apex_application.g_clob_01);'),
    ('LIST_IMAGES', 'pdf_designer.list_images;'),
    ('SAVE_IMAGE', 'pdf_designer.save_image(apex_application.g_x01, apex_application.g_clob_01);'),
    ('IMAGE_DATA', 'pdf_designer.image_data(apex_application.g_x01);'),
]


def logic(exp, ctx):
    demo = {name for name, _ in demo_pages.APP_PROCESSES}
    for n, (name, plsql) in enumerate(PROCESSES + demo_pages.APP_PROCESSES, 1):
        exp.prompt('shared_components/logic/application_processes/' + name.lower())
        exp.block(call('wwv_flow_imp_shared.create_flow_process', [
            ('p_id', wid(ctx.app.ids.new())), ('p_process_sequence', n), ('p_process_point', 'ON_DEMAND'),
            ('p_process_name', name), ('p_static_id', name.lower().replace('_', '-')),
            ('p_process_sql_clob', plsql), ('p_process_clob_language', 'PLSQL'),
            ('p_security_scheme', wid(ctx.demo_auth) if name in demo else None)]))
    for p in ('shared_components/logic/application_settings', 'shared_components/navigation/tabs/standard',
              'shared_components/navigation/tabs/parent'):
        exp.prompt(p)
        exp.block()


def lovs(exp, ctx):
    exp.prompt('shared_components/user_interface/lovs/pdf_reports')
    exp.block(call('wwv_flow_imp_shared.create_list_of_values', [
        ('p_id', wid(ctx.lov_reports)), ('p_lov_name', 'PDF_REPORTS'), ('p_static_id', 'pdf-reports'),
        ('p_lov_query', "select name || ' (' || code || ')' d, code r from pdf_reports order by name"),
        ('p_source_type', 'LEGACY_SQL'), ('p_location', 'LOCAL')]))
    for name, sql in demo_pages.LOVS.items():
        exp.prompt('shared_components/user_interface/lovs/' + name.lower())
        exp.block(call('wwv_flow_imp_shared.create_list_of_values', [
            ('p_id', wid(ctx.demo_lovs[name])), ('p_lov_name', name), ('p_static_id', name.lower().replace('_', '-')),
            ('p_lov_query', sql), ('p_source_type', 'LEGACY_SQL'), ('p_location', 'LOCAL')]))


def page_groups(exp, ctx):
    exp.prompt('pages/page_groups')
    exp.block(call('wwv_flow_imp_page.create_page_group', [
        ('p_id', wid(ctx.group_main)), ('p_group_name', 'Designer'), ('p_static_id', 'designer')]),
        call('wwv_flow_imp_page.create_page_group', [
            ('p_id', wid(ctx.group_demo)), ('p_group_name', 'Demo'), ('p_static_id', 'demo')]))


def breadcrumbs(exp, ctx):
    exp.prompt('shared_components/navigation/breadcrumbs/breadcrumb')
    exp.block(call('wwv_flow_imp_shared.create_menu', [('p_id', wid(ctx.menu)), ('p_name', 'Breadcrumb'),
                                                       ('p_static_id', 'breadcrumb')]))
    exp.prompt('shared_components/navigation/breadcrumbentry')
    exp.block()


def theme(exp, ctx):
    exp.prompt('shared_components/user_interface/themes')
    exp.block(call('wwv_flow_imp_shared.create_theme', [
        ('p_id', wid(ctx.theme)), ('p_theme_id', 42), ('p_static_id', 'universal-theme'),
        ('p_theme_name', 'Universal Theme'), ('p_theme_internal_name', 'UNIVERSAL_THEME'),
        ('p_version_identifier', '26.1'), ('p_navigation_type', 'L'), ('p_nav_bar_type', 'LIST'),
        ('p_is_locked', False), ('p_current_theme_style_id', 2243014446517417),
        ('p_default_page_template', 4073832297226169690), ('p_default_dialog_template', 2101883943284197310),
        ('p_error_template', 2102634289808461002), ('p_printer_friendly_template', 4073832297226169690),
        ('p_login_template', 2102634289808461002), ('p_default_button_template', 4073839297780169708),
        ('p_default_region_template', 4073835273271169698), ('p_default_chart_template', 4073835273271169698),
        ('p_default_form_template', 4073835273271169698), ('p_default_reportr_template', 4073835273271169698),
        ('p_default_wizard_template', 4073835273271169698), ('p_default_menur_template', 2532939663579242476),
        ('p_default_listr_template', 4073835273271169698), ('p_default_irr_template', 2102002977963900996),
        ('p_default_report_template', 2540130677583398057),
        ('p_default_label_template', Raw('wwv_flow_imp.id(2318601014859922299)')),
        ('p_default_menu_template', 4073839682315169711), ('p_default_list_template', 4073837480889169704),
        ('p_default_top_nav_list_temp', 2528231041045349458), ('p_default_side_nav_list_temp', 2469215554099805162),
        ('p_default_nav_list_position', 'SIDE'), ('p_default_dialogbtnr_template', 2127905476394690047),
        ('p_default_dialogr_template', 4502917002193490937),
        ('p_default_option_label', Raw('wwv_flow_imp.id(2318601014859922299)')),
        ('p_default_required_label', Raw('wwv_flow_imp.id(2526760615038828570)')),
        ('p_default_navbar_list_template', 2849019392706229583),
        ('p_file_prefix', Raw("nvl(wwv_flow_application_install.get_static_theme_file_prefix(42),'#APEX_FILES#themes/theme_42/26.1/')")),
        ('p_files_version', 64), ('p_icon_library', 'FONTAPEX'),
        ('p_javascript_file_urls', '#APEX_FILES#libraries/apex/#MIN_DIRECTORY#widget.stickyWidget#MIN#.js?v=#APEX_VERSION#\n'
                                   '#THEME_FILES#js/theme42#MIN#.js?v=#APEX_VERSION#\n'
                                   '#APP_FILES#js/designer.js'),
        ('p_css_file_urls', '#THEME_FILES#css/Core#MIN#.css?v=#APEX_VERSION#'),
        ('p_reference_id', Raw("wwv_imp_util.get_subscription_id(4073840274158169736,2000,'universal-theme',8842.261)")),
        ('p_version_scn', 'SH256:_g5TkoniPmMM8qu-qn_VQMogPd_uGhgh_nbDep83BD0'),
        ('p_version_scn_master', 'SH256:WOPVC8vP1TPWUxczh2dJ4mCZcNGSTzA1cn8DjR2oQjY')]))
    for p in ('shared_components/user_interface/theme_style', 'shared_components/user_interface/theme_files'):
        exp.prompt(p)
        exp.block()
    exp.prompt('shared_components/user_interface/template_opt_groups')
    exp.block(*[call('wwv_flow_imp_shared.create_template_opt_group', [
        ('p_id', wid(ctx.app.ids.new())), ('p_theme_id', 42), ('p_name', n), ('p_static_id', s),
        ('p_display_name', dn), ('p_display_sequence', seq), ('p_template_types', tt),
        ('p_help_text', hl), ('p_null_text', nt), ('p_is_advanced', 'N')])
        for n, s, dn, seq, tt, hl, nt in TEMPLATE_OPT_GROUPS])
    for p in ('shared_components/user_interface/template_options', 'shared_components/globalization/language',
              'shared_components/globalization/translations', 'shared_components/logic/build_options',
              'shared_components/globalization/messages', 'shared_components/globalization/dyntranslations'):
        exp.prompt(p)
        exp.block()


def authentication(exp, ctx, no_auth):
    if no_auth:
        exp.prompt('shared_components/security/authentications/no_authentication')
        exp.block(call('wwv_flow_imp_shared.create_authentication', [
            ('p_id', wid(ctx.auth_id)), ('p_name', 'No Authentication (local test)'),
            ('p_static_id', 'no-authentication'), ('p_scheme_type', 'NATIVE_DAD'),
            ('p_use_secure_cookie_yn', 'N'), ('p_ras_mode', 0)]))
    else:
        exp.prompt('shared_components/security/authentications/oracle_apex_accounts')
        exp.block(call('wwv_flow_imp_shared.create_authentication', [
            ('p_id', wid(ctx.auth_id)), ('p_name', 'Oracle APEX Accounts'), ('p_static_id', 'oracle-apex-accounts'),
            ('p_scheme_type', 'NATIVE_APEX_ACCOUNTS'), ('p_use_secure_cookie_yn', 'N'), ('p_ras_mode', 0)]))
    exp.prompt('user_interfaces/combined_files')
    exp.block()


def deployment(exp, ctx):
    drops = '\n'.join("begin execute immediate 'drop %s%s'; exception when others then null; end;\n/"
                      % (d, ' cascade constraints purge' if d.startswith('TABLE') else '') for d in DROPS)
    exp.prompt('deployment/definition')
    exp.block(varchar2_table(drops), call('wwv_flow_imp_shared.create_install', [
        ('p_id', wid(ctx.install)),
        ('p_welcome_message', 'This installs the PDF Report Designer objects in the parsing schema: the tables '
                              'PDF_REPORTS, PDF_QUERIES, PDF_IMAGES and PDF_LOG, the packages PDF_WRITER, PDF_ENGINE, '
                              'PDF_API and PDF_DESIGNER, the demo tables PDF_DEMO_* and three sample reports.'),
        ('p_configuration_message', 'You can configure the following attributes of your application.'),
        ('p_build_options_message', 'You can choose to include the following build options.'),
        ('p_validation_message', 'The following validations will be performed to ensure your system is compatible with this application.'),
        ('p_install_message', 'Please confirm that you would like to install this application''s supporting objects.'),
        ('p_upgrade_message', 'The application installer has detected that this application''s supporting objects were previously installed.  This wizard will guide you through the process of upgrading these supporting objects.'),
        ('p_upgrade_confirm_message', 'Please confirm that you would like to install this application''s supporting objects.'),
        ('p_upgrade_success_message', 'Your application''s supporting objects have been installed.'),
        ('p_upgrade_failure_message', 'Installation of database objects and seed data has failed.'),
        ('p_deinstall_success_message', 'PDF Report Designer objects removed.'),
        ('p_deinstall_script_clob', Raw('wwv_flow_imp.varchar2_to_clob(wwv_flow_imp.g_varchar2_table)')),
        ('p_required_free_kb', 20000),
        ('p_required_sys_privs', 'CREATE PROCEDURE:CREATE TABLE'),
        ('p_deinstall_message', 'This removes the PDF Report Designer tables (with every report and image) and packages.')]))
    for n, name in enumerate(SQL_SCRIPTS, 1):
        sql = open(os.path.join(ROOT, 'sql', name)).read()
        if '&' in sql:
            raise SystemExit('%s contains "&" (APEX substitution) - not allowed in supporting objects' % name)
        exp.prompt('deployment/install/install_%02d_%s' % (n, name[3:-4]))
        exp.block(varchar2_table(sql), call('wwv_flow_imp_shared.create_install_script', [
            ('p_id', wid(ctx.app.ids.new())), ('p_install_id', wid(ctx.install)),
            ('p_name', name[:-4].replace('_', ' ')), ('p_sequence', n * 10), ('p_script_type', 'INSTALL'),
            ('p_script_clob', Raw('wwv_flow_imp.varchar2_to_clob(wwv_flow_imp.g_varchar2_table)'))]))


def footer(exp):
    for p in ('deployment/checks', 'deployment/buildoptions'):
        exp.prompt(p)
        exp.block()
    exp.prompt('end_environment')
    exp.raw('begin\nwwv_flow_imp.import_end(p_auto_install_sup_obj => nvl(wwv_flow_application_install.get_auto_install_sup_obj, false)\n'
            ',p_has_subscriptions=>true\n);\ncommit;\nend;\n/\nset verify on feedback on define on\nprompt  ...done')


# ------------------------------------------------------------------ pages
REPORTS_SQL = """select r.report_id, r.code, r.name, r.description,
       json_value(r.layout, '$.type') kind,
       json_value(r.layout, '$.page.size') || ' ' || json_value(r.layout, '$.page.orientation') page_size,
       (select count(*) from pdf_queries q where q.report_id = r.report_id) queries,
       nvl(r.updated_on, r.created_on) updated_on, nvl(r.updated_by, r.created_by) updated_by,
       'Design' design, 'Try' try, 'Export' export
  from pdf_reports r"""


def page_reports(ctx):
    p = Page(ctx.app, 1, 'Reports', 'REPORTS', title='PDF Reports', group=ctx.group_main, component_map='18')
    p.static('Intro', template='region_blank', seq=5, html=(
        '<p class="pdfd-intro">Design a PDF on a canvas, bind it to your SQL queries and call it from any page: '
        '<code>pdf_api.generate(\'CODE\')</code> returns the PDF as a BLOB. '
        '<a href="f?p=&APP_ID.:7:&SESSION.">How to use it</a></p>'))
    r = p.ir('Reports', REPORTS_SQL, [
        dict(name='REPORT_ID', hidden=True),
        dict(name='CODE', label='Code'),
        dict(name='NAME', label='Name',
             link='f?p=&APP_ID.:2:&SESSION.::&DEBUG.::P2_REPORT_ID:#REPORT_ID#', link_text='#NAME#'),
        dict(name='DESCRIPTION', label='Description'),
        dict(name='KIND', label='Kind'),
        dict(name='PAGE_SIZE', label='Page'),
        dict(name='QUERIES', label='Queries', type='NUMBER'),
        dict(name='UPDATED_ON', label='Updated', type='DATE', mask='DD-MON-YYYY HH24:MI'),
        dict(name='UPDATED_BY', label='By'),
        dict(name='DESIGN', label='Design', link='f?p=&APP_ID.:2:&SESSION.::&DEBUG.::P2_REPORT_ID:#REPORT_ID#',
             link_text='<span class="fa fa-pencil" aria-hidden="true"></span> Design', align='CENTER'),
        dict(name='TRY', label='Try', link='f?p=&APP_ID.:4:&SESSION.::&DEBUG.:RP,4:P4_REPORT:#CODE#',
             link_text='<span class="fa fa-play" aria-hidden="true"></span> Try', align='CENTER'),
        dict(name='EXPORT', label='Export', link='f?p=&APP_ID.:5:&SESSION.::&DEBUG.::P5_REPORT_ID:#REPORT_ID#',
             link_text='<span class="fa fa-download" aria-hidden="true"></span> JSON', align='CENTER'),
    ], seq=10, sort=('NAME', 'ASC'), rows=50)
    p.button('CREATE', 'New Report', r, action='REDIRECT_URL', position='RIGHT_OF_IR_SEARCH_BAR', hot=True,
             icon='fa-plus', url='f?p=&APP_ID.:3:&SESSION.::&DEBUG.:RP,3::')
    return p


DESIGNER_JS = """pdfd.init({
  el: '#pdfd',
  reportId: $v('P2_REPORT_ID'),
  listUrl: 'f?p=&APP_ID.:1:&SESSION.'
});"""

DESIGNER_CSS = """.t-Body-content .t-Body-contentInner { padding: 8px 12px 0; }
.t-Body-content { min-height: 0; }
.t-Footer { display: none; }"""


def page_designer(ctx):
    p = Page(ctx.app, 2, 'Designer', 'DESIGNER', title='Designer', group=ctx.group_main, component_map='03',
             inline_css=DESIGNER_CSS, js_onload=DESIGNER_JS)
    r = p.static('Designer', html='<div id="pdfd"></div>', template='region_blank', seq=10)
    p.item('P2_REPORT_ID', r, kind='hidden', protection='N')
    return p


NEW_REPORT = """:P3_REPORT_ID := pdf_designer.create_report(
  p_code        => :P3_CODE,
  p_name        => :P3_NAME,
  p_description => :P3_DESCRIPTION,
  p_type        => :P3_TYPE,
  p_size        => :P3_SIZE,
  p_orientation => :P3_ORIENTATION,
  p_copy_of     => :P3_COPY_OF);"""

IMPORT_REPORT = """:P3_REPORT_ID := pdf_designer.import_json(:P3_IMPORT);"""


def page_new(ctx):
    p = Page(ctx.app, 3, 'New Report', 'NEW-REPORT', title='New Report', group=ctx.group_main, component_map='02')
    r = p.static('New Report', seq=10)
    p.item('P3_CODE', r, label='Code', required=True, maxlen=60, placeholder='INVOICE',
           inline_help='Upper case letters, digits and _. Your applications call the report by it: pdf_api.generate(\'INVOICE\').')
    p.item('P3_NAME', r, label='Name', required=True, maxlen=200, placeholder='Tax Invoice')
    p.item('P3_DESCRIPTION', r, kind='textarea', label='Description', height=2)
    p.item('P3_TYPE', r, kind='radio', label='Kind', default='report',
           lov="STATIC2:Document / report (bands);report,Labels (a grid of labels);labels")
    p.item('P3_SIZE', r, kind='select', label='Page size', default='A4',
           lov='STATIC2:A4;A4,A3;A3,A5;A5,Letter;Letter,Legal;Legal', new_line='N')
    p.item('P3_ORIENTATION', r, kind='radio', label='Orientation', default='portrait',
           lov='STATIC2:Portrait;portrait,Landscape;landscape', new_line='N')
    p.item('P3_COPY_OF', r, kind='select', label='Start from a copy of', named_lov='PDF_REPORTS',
           lov_null='- an empty layout -', inline_help='Copies the layout and the queries of that report.',
           attrs_={'page_action_on_selection': 'NONE'})
    p.item('P3_REPORT_ID', r, kind='hidden')
    create = p.button('CREATE', 'Create and Design', r, position='NEXT', hot=True)
    p.button('CANCEL', 'Cancel', r, action='REDIRECT_URL', position='PREVIOUS', url='f?p=&APP_ID.:1:&SESSION.::&DEBUG.:::')
    p.validation('Code format', 'EXPRESSION', "regexp_like(upper(trim(:P3_CODE)), '^[A-Z][A-Z0-9_]*$')",
                 'The code starts with a letter and has only letters, digits and _.', button=create, expr2='PLSQL')
    p.validation('Code unique', 'NOT_EXISTS', "select 1 from pdf_reports where code = upper(trim(:P3_CODE))",
                 'A report with this code exists already.', seq=20, button=create)
    p.process('Create the report', NEW_REPORT, button=create, seq=10)

    ri = p.static('Import a Report (JSON)', seq=20, options='#DEFAULT#:is-collapsed:t-Region--scrollBody',
                  template='region_collapsible')
    p.item('P3_IMPORT', ri, kind='textarea', label='Report JSON (from Export)', height=8,
           inline_help='A report with the same code is replaced; otherwise it is added.')
    imp = p.button('IMPORT', 'Import', ri, position='NEXT')
    p.process('Import the report', IMPORT_REPORT, button=imp, seq=20, success='Report imported.')
    p.branch('f?p=&APP_ID.:2:&SESSION.::&DEBUG.::P2_REPORT_ID:&P3_REPORT_ID.', seq=10)
    return p


TRY_PDF = """declare
  l_params apex_t_varchar2 := apex_t_varchar2();
  l_line   varchar2(4000);
begin
  -- NAME=VALUE, one per line
  for l in (select column_value v from table(apex_string.split(:P4_PARAMS, chr(10)))) loop
    l_line := trim(replace(l.v, chr(13)));
    if instr(l_line, '=') > 1 then
      apex_string.push(l_params, trim(substr(l_line, 1, instr(l_line, '=') - 1)));
      apex_string.push(l_params, trim(substr(l_line, instr(l_line, '=') + 1)));
    end if;
  end loop;
  pdf_api.download(
    p_report   => :P4_REPORT,
    p_params   => l_params,
    p_filename => lower(:P4_REPORT) || '.pdf',
    p_inline   => true);
end;"""

TRY_PARAMS = """-- the test values of the report, as NAME=VALUE lines
declare
  l_json   clob;
  l_params json_object_t;
  l_keys   json_key_list;
  l_out    varchar2(4000);
begin
  select json_query(layout, '$.params' returning clob) into l_json
    from pdf_reports where code = :P4_REPORT;
  l_params := json_object_t.parse(l_json);
  l_keys := l_params.get_keys;
  for i in 1 .. l_keys.count loop
    l_out := l_out || l_keys(i) || '=' || l_params.get_string(l_keys(i)) || chr(10);
  end loop;
  return rtrim(l_out, chr(10));
exception
  when others then
    return null;
end;"""

TRY_JS = """window.pdfTry = function () {
  var code = $v('P4_REPORT'), pairs = [];
  $v('P4_PARAMS').split(/\\r?\\n/).forEach(function (l) {
    var i = l.indexOf('=');
    if (i > 0) { pairs.push("'" + l.slice(0, i).trim() + "', '" + l.slice(i + 1).trim().replace(/'/g, "''") + "'"); }
  });
  var txt = 'declare\\n  l_pdf blob;\\nbegin\\n  l_pdf := pdf_api.generate(\\'' + (code || 'CODE') + '\\'' +
            (pairs.length ? ',\\n           apex_t_varchar2(' + pairs.join(', ') + ')' : '') + ');\\nend;';
  $('#api-call').text(txt);
};
pdfTry();
$('#P4_REPORT, #P4_PARAMS').on('change input', pdfTry);"""



def page_try(ctx):
    p = Page(ctx.app, 4, 'Try the API', 'TRY', title='Try the API', group=ctx.group_main, component_map='03',
             js_onload=TRY_JS, inline_css='.pdfd-snippet { margin: 0; padding: 10px 12px; background: #0f1b2b; color: #e6edf7; border-radius: 6px; font: 12.5px/1.5 ui-monospace, Menlo, Consolas, monospace; white-space: pre-wrap; }')
    r = p.static('Generate a PDF', seq=10, grid=4)
    p.item('P4_REPORT', r, kind='select', label='Report', named_lov='PDF_REPORTS', lov_null='- choose -',
           required=True, protection='N', attrs_={'page_action_on_selection': 'NONE'})
    p.item('P4_PARAMS', r, kind='textarea', label='Parameters (NAME=VALUE, one per line)', height=5,
           inline_help='The bind variables of the queries. In your application they come from the page items.')
    p.computation('P4_PARAMS', 'FUNCTION_BODY', TRY_PARAMS, lang='PLSQL', when_type='ITEM_IS_NULL',
                  when='P4_PARAMS')
    gen = p.button('GENERATE', 'Generate PDF', r, action='DEFINED_BY_DA', position='NEXT', hot=True, icon='fa-file-pdf-o')
    p.static('The call', seq=20, parent=r, html='<pre id="api-call" class="pdfd-snippet"></pre>')
    p.da('Generate', 'click', [
        {'action': 'NATIVE_EXECUTE_PLSQL_CODE', 'wait': 'Y',
         'attrs': {'items_to_submit': 'P4_REPORT,P4_PARAMS', 'language': 'PLSQL', 'plsql_code': 'null;',
                   'show_processing': 'N'}},
        {'action': 'NATIVE_JAVASCRIPT_CODE',
         'attrs': {'js_code': "var url = apex.util.makeApplicationUrl({ pageId: 4, request: 'PDF' });\n"
                              "document.getElementById('pdf-frame').src = url;\n"
                              "var a = document.getElementById('pdf-open'); a.href = url; a.style.display = '';"}}], button=gen, element_type='BUTTON')

    p.static('PDF', seq=30, grid=8, new_row=False, html=(
        '<a id="pdf-open" href="#" target="_blank" style="display:none" class="t-Button t-Button--small">'
        'Open in a new tab</a>'
        '<iframe id="pdf-frame" title="PDF" style="width:100%;height:calc(100vh - 260px);min-height:480px;'
        'border:1px solid #d9dee6;border-radius:4px;margin-top:6px;background:#525659"></iframe>'))
    p.process('Send the PDF', TRY_PDF, point='BEFORE_HEADER', seq=10, when_type='REQUEST_EQUALS_CONDITION',
              when='PDF')
    return p


EXPORT_JSON = """declare
  l_json clob;
  l_code varchar2(60);
begin
  select code into l_code from pdf_reports where report_id = :P5_REPORT_ID;
  l_json := pdf_designer.export_json(:P5_REPORT_ID);
  sys.htp.init;
  sys.owa_util.mime_header('application/json', false, 'utf-8');
  sys.htp.p('Content-Disposition: attachment; filename="' || lower(l_code) || '.pdfreport.json"');
  sys.owa_util.http_header_close;
  apex_util.prn(l_json, false);
  apex_application.stop_apex_engine;
end;"""


def page_export(ctx):
    p = Page(ctx.app, 5, 'Export', 'EXPORT', title='Export', group=ctx.group_main, component_map='03')
    r = p.static('Export', seq=10, html='<p>The report is downloaded as JSON.</p>')
    p.item('P5_REPORT_ID', r, kind='hidden', protection='N')
    p.process('Download the JSON', EXPORT_JSON, point='BEFORE_HEADER', seq=10, when_type='ITEM_IS_NOT_NULL',
              when='P5_REPORT_ID')
    return p


LOG_SQL = """select log_id, created_on, report_code, pages, bytes, elapsed_ms, app_id, page_id, app_user, params,
       error, case when error is null then 'OK' else 'Error' end status
  from pdf_log"""


def page_log(ctx):
    p = Page(ctx.app, 6, 'Log', 'LOG', title='Generation Log', group=ctx.group_main, component_map='18')
    p.ir('Generated PDFs', LOG_SQL, [
        dict(name='LOG_ID', hidden=True),
        dict(name='CREATED_ON', label='When', type='DATE', mask='DD-MON-YYYY HH24:MI:SS'),
        dict(name='REPORT_CODE', label='Report'),
        dict(name='STATUS', label='Status'),
        dict(name='PAGES', label='Pages', type='NUMBER'),
        dict(name='BYTES', label='Bytes', type='NUMBER', mask='999G999G999'),
        dict(name='ELAPSED_MS', label='Time (ms)', type='NUMBER'),
        dict(name='APP_ID', label='App', type='NUMBER'),
        dict(name='PAGE_ID', label='Page', type='NUMBER'),
        dict(name='APP_USER', label='User'),
        dict(name='PARAMS', label='Parameters'),
        dict(name='ERROR', label='Error'),
    ], seq=10, sort=('CREATED_ON', 'DESC'), rows=50)
    return p


HELP_HTML = open(os.path.join(ROOT, 'app', 'help.html')).read() if os.path.exists(os.path.join(ROOT, 'app', 'help.html')) else ''


def page_help(ctx):
    p = Page(ctx.app, 7, 'How to Use', 'HELP', title='How to Use', group=ctx.group_main, component_map='03')
    p.static('How to Use', html=HELP_HTML, seq=10, template='region_blank')
    return p


def login(ctx):
    p = Page(ctx.app, 9999, 'Login', 'LOGIN', title='Sign In | ' + APP_NAME, template=T['page_login'],
             public=True, component_map='16')
    r = p.static(APP_NAME, template='region_login', seq=10)
    p.item('P9999_USERNAME', r, label='Username', placeholder='username', required=True, size=64, maxlen=100,
           template=T['label_hidden'], icon='fa-user', source_type='ALWAYS_NULL')
    p.item('P9999_PASSWORD', r, kind='password', label='Password', placeholder='password', required=True,
           size=64, maxlen=100, template=T['label_hidden'], icon='fa-key', source_type='ALWAYS_NULL', persistent='N')
    p.button('LOGIN', 'Sign In', r, position='NEXT', hot=True)
    p.process('Get Username Cookie', ':P9999_USERNAME := apex_authentication.get_login_username_cookie;',
              point='BEFORE_HEADER', seq=10)
    p.process('Set Username Cookie',
              'apex_authentication.send_login_username_cookie (\n    p_username => lower(:P9999_USERNAME) );', seq=10)
    p.process('Login', 'apex_authentication.login(\n    p_username => :P9999_USERNAME,\n    p_password => :P9999_PASSWORD );',
              seq=20)
    p.process('Clear Page(s) Cache', ptype='NATIVE_SESSION_STATE', seq=30, attrs_={'type': 'CLEAR_CACHE_CURRENT_PAGE'})
    return p


def build(app_id, no_auth, name, alias, with_objects):
    app = App(Ids())
    ctx = Ctx(app)
    pages = [page_reports(ctx), page_designer(ctx), page_new(ctx), page_try(ctx), page_export(ctx),
             page_log(ctx), page_help(ctx)] + demo_pages.pages(ctx)
    if not no_auth:
        pages.append(login(ctx))
    exp = Export()
    header(exp, app_id)
    application(exp, ctx, alias, name)
    plugin_settings(exp, ctx)
    lists(exp, ctx)
    static_files(exp, ctx)
    security(exp, ctx)
    exp.prompt('shared_components/navigation/navigation_bar')
    exp.block()
    logic(exp, ctx)
    lovs(exp, ctx)
    page_groups(exp, ctx)
    breadcrumbs(exp, ctx)
    theme(exp, ctx)
    authentication(exp, ctx, no_auth)
    for p in pages:
        p.render(exp)
    if with_objects:
        deployment(exp, ctx)
    footer(exp)
    return exp.text()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--app-id', type=int, default=2000)
    ap.add_argument('--test-id', type=int, default=2099)
    a = ap.parse_args()
    os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)
    os.makedirs(os.path.join(ROOT, 'local'), exist_ok=True)
    out = os.path.join(ROOT, 'dist', 'pdf_report_designer.sql')
    open(out, 'w').write(build(a.app_id, False, APP_NAME, APP_ALIAS, True))
    test = os.path.join(ROOT, 'local', 'pdf_report_designer_test.sql')
    open(test, 'w').write(build(a.test_id, True, APP_NAME + ' (local test)', APP_ALIAS + '_TEST', False))
    print('written', out, 'and', test)


if __name__ == '__main__':
    main()
