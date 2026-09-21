#!/usr/bin/env python3
"""Verify a generated APEX export without an APEX installation.

1. Creates stub versions of the APEX import packages in a scratch schema of the
   local Oracle container. Every procedure only accepts the parameter names
   observed in a real APEX 26.1.1 export (vocab_26_1.json), so an unknown
   parameter, a misspelling or a wrong boolean/string type fails to compile
   exactly like it would on apex.oracle.com (PLS-00306).
2. Runs the export file in SQL*Plus against the stubs (whenever sqlerror exit).
3. Every stub call is logged; SQL checks then verify the cross references
   (items -> regions, buttons -> regions, LOV names, authorization schemes,
   list parents, duplicate ids / item names / button names per page).

Usage: check_export.py EXPORT.sql
"""
import json
import os
import subprocess
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = 'HMS_APEXCHK'
# the local APEX test database (tools/local/local_apex.sh); only the scratch schema above is touched
CONTAINER = os.environ.get('CONTAINER', 'rounds-apex')
PDB = os.environ.get('PDB', 'FREEPDB1')

INFRA = r"""
CREATE OR REPLACE TYPE wwv_flow_t_varchar2 AS TABLE OF VARCHAR2(4000)
/
CREATE OR REPLACE TYPE wwv_flow_t_plugin_attributes AS OBJECT (
  vals wwv_flow_t_varchar2,
  MEMBER FUNCTION to_clob RETURN CLOB)
/
CREATE OR REPLACE TYPE BODY wwv_flow_t_plugin_attributes AS
  MEMBER FUNCTION to_clob RETURN CLOB IS
    l CLOB;
  BEGIN
    IF MOD(vals.COUNT, 2) <> 0 THEN
      raise_application_error(-20100, 'plug-in attributes need name/value pairs');
    END IF;
    FOR i IN 1 .. vals.COUNT LOOP
      l := l || vals(i) || CHR(10);
    END LOOP;
    RETURN l;
  END;
END;
/
CREATE TABLE chk_log (seq NUMBER, page_id NUMBER, api VARCHAR2(100), pname VARCHAR2(100), pval VARCHAR2(4000))
/
CREATE SEQUENCE chk_seq
/
CREATE OR REPLACE PACKAGE wwv_flow AS
  g_flow_id NUMBER := 100;
  LF CONSTANT VARCHAR2(1) := CHR(10);
END;
/
CREATE OR REPLACE PACKAGE wwv_flow_string AS
  FUNCTION join(p_strings IN wwv_flow_t_varchar2, p_sep IN VARCHAR2 DEFAULT CHR(10)) RETURN VARCHAR2;
END;
/
CREATE OR REPLACE PACKAGE BODY wwv_flow_string AS
  FUNCTION join(p_strings IN wwv_flow_t_varchar2, p_sep IN VARCHAR2 DEFAULT CHR(10)) RETURN VARCHAR2 IS
    l VARCHAR2(32767);
  BEGIN
    FOR i IN 1 .. p_strings.COUNT LOOP
      l := l || CASE WHEN i > 1 THEN p_sep END || p_strings(i);
    END LOOP;
    RETURN l;
  END;
END;
/
CREATE OR REPLACE PACKAGE wwv_flow_application_install AS
  FUNCTION get_schema RETURN VARCHAR2;
  FUNCTION get_application_name RETURN VARCHAR2;
  FUNCTION get_application_alias RETURN VARCHAR2;
  FUNCTION get_image_prefix RETURN VARCHAR2;
  FUNCTION get_proxy RETURN VARCHAR2;
  FUNCTION get_no_proxy_domains RETURN VARCHAR2;
  FUNCTION get_static_app_file_prefix RETURN VARCHAR2;
  FUNCTION get_static_theme_file_prefix(p_theme_number IN NUMBER) RETURN VARCHAR2;
  FUNCTION get_auto_install_sup_obj RETURN BOOLEAN;
END;
/
CREATE OR REPLACE PACKAGE BODY wwv_flow_application_install AS
  FUNCTION get_schema RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_application_name RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_application_alias RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_image_prefix RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_proxy RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_no_proxy_domains RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_static_app_file_prefix RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_static_theme_file_prefix(p_theme_number IN NUMBER) RETURN VARCHAR2 IS BEGIN RETURN NULL; END;
  FUNCTION get_auto_install_sup_obj RETURN BOOLEAN IS BEGIN RETURN FALSE; END;
END;
/
CREATE OR REPLACE PACKAGE wwv_imp_util AS
  FUNCTION get_subscription_id(p_id IN NUMBER, p_type IN NUMBER, p_static IN VARCHAR2, p_version IN NUMBER) RETURN NUMBER;
END;
/
CREATE OR REPLACE PACKAGE BODY wwv_imp_util AS
  FUNCTION get_subscription_id(p_id IN NUMBER, p_type IN NUMBER, p_static IN VARCHAR2, p_version IN NUMBER) RETURN NUMBER IS
  BEGIN RETURN p_id; END;
END;
/
CREATE OR REPLACE PACKAGE wwv_flow_imp AS
  TYPE t_vc IS TABLE OF VARCHAR2(32767) INDEX BY BINARY_INTEGER;
  g_varchar2_table t_vc;
  g_page NUMBER;
  FUNCTION empty_varchar2_table RETURN t_vc;
  FUNCTION varchar2_to_clob(p_table IN t_vc) RETURN CLOB;
  FUNCTION varchar2_to_blob(p_table IN t_vc) RETURN BLOB;
  FUNCTION id(p_id IN NUMBER) RETURN NUMBER;
  PROCEDURE import_begin(p_version_yyyy_mm_dd IN VARCHAR2, p_release IN VARCHAR2, p_default_workspace_id IN NUMBER,
                         p_default_application_id IN NUMBER, p_default_id_offset IN NUMBER, p_default_owner IN VARCHAR2);
  PROCEDURE remove_flow(p_id IN NUMBER);
  PROCEDURE import_end(p_auto_install_sup_obj IN BOOLEAN, p_has_subscriptions IN BOOLEAN DEFAULT FALSE);
  PROCEDURE log(p_api IN VARCHAR2, p_name IN VARCHAR2, p_value IN VARCHAR2);
END;
/
CREATE OR REPLACE PACKAGE BODY wwv_flow_imp AS
  FUNCTION empty_varchar2_table RETURN t_vc IS l t_vc; BEGIN RETURN l; END;
  FUNCTION varchar2_to_clob(p_table IN t_vc) RETURN CLOB IS
    l CLOB;
  BEGIN
    FOR i IN 1 .. p_table.COUNT LOOP
      l := l || p_table(i);
    END LOOP;
    RETURN l;
  END;
  FUNCTION varchar2_to_blob(p_table IN t_vc) RETURN BLOB IS
    l BLOB;
  BEGIN
    DBMS_LOB.CREATETEMPORARY(l, TRUE);
    FOR i IN 1 .. p_table.COUNT LOOP
      DBMS_LOB.WRITEAPPEND(l, LENGTH(p_table(i)) / 2, HEXTORAW(p_table(i)));
    END LOOP;
    RETURN l;
  END;
  FUNCTION id(p_id IN NUMBER) RETURN NUMBER IS BEGIN RETURN p_id; END;
  PROCEDURE import_begin(p_version_yyyy_mm_dd IN VARCHAR2, p_release IN VARCHAR2, p_default_workspace_id IN NUMBER,
                         p_default_application_id IN NUMBER, p_default_id_offset IN NUMBER, p_default_owner IN VARCHAR2) IS
  BEGIN
    log('import_begin', 'p_release', p_release);
  END;
  PROCEDURE remove_flow(p_id IN NUMBER) IS BEGIN NULL; END;
  PROCEDURE import_end(p_auto_install_sup_obj IN BOOLEAN, p_has_subscriptions IN BOOLEAN DEFAULT FALSE) IS
  BEGIN
    log('import_end', 'done', 'Y');
  END;
  PROCEDURE log(p_api IN VARCHAR2, p_name IN VARCHAR2, p_value IN VARCHAR2) IS
    PRAGMA AUTONOMOUS_TRANSACTION;
  BEGIN
    INSERT INTO chk_log VALUES (chk_seq.NEXTVAL, g_page, p_api, p_name, SUBSTR(p_value, 1, 4000));
    COMMIT;
  END;
END;
/
"""

CHECKS = r"""
set lines 250 pages 500 feedback off heading on
col problem for a120
prompt ==== cross-reference problems (no rows = OK)
WITH calls AS (
  SELECT seq, page_id, api, pname, pval FROM chk_log),
ids AS (
  SELECT api, pval id FROM calls WHERE pname = 'p_id'),
regions AS (
  SELECT id FROM ids WHERE api IN ('create_page_plug', 'create_report_region')),
refs AS (
  SELECT page_id, api, pname, pval FROM calls
   WHERE pname IN ('p_item_plug_id', 'p_button_plug_id', 'p_parent_plug_id', 'p_region_id', 'p_affected_region_id'))
SELECT 'page ' || page_id || ' ' || api || '.' || pname || ' -> missing region ' || pval problem
  FROM refs WHERE pval NOT IN (SELECT id FROM regions)
UNION ALL
SELECT 'page ' || page_id || ' da action -> missing event ' || pval FROM calls
 WHERE api = 'create_page_da_action' AND pname = 'p_event_id'
   AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_page_da_event')
UNION ALL
SELECT 'page ' || page_id || ' ' || api || ' -> missing button ' || pval FROM calls
 WHERE pname IN ('p_triggering_button_id', 'p_process_when_button_id', 'p_branch_when_button_id', 'p_when_button_pressed')
   AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_page_button')
UNION ALL
SELECT 'page ' || page_id || ' ' || api || ' -> missing LOV ' || pval FROM calls
 WHERE pname = 'p_named_lov'
   AND pval NOT IN (SELECT pval FROM calls WHERE api = 'create_list_of_values' AND pname = 'p_lov_name')
UNION ALL
SELECT 'page ' || page_id || ' ' || api || '.' || pname || ' -> missing authorization ' || pval FROM calls
 WHERE pname IN ('p_required_role', 'p_security_scheme', 'p_plug_required_role', 'p_detail_link_auth_scheme')
   AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_security_scheme')
UNION ALL
SELECT 'page ' || page_id || ' -> missing page group ' || pval FROM calls
 WHERE api = 'create_page' AND pname = 'p_group_id'
   AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_page_group')
UNION ALL
SELECT 'list item -> missing parent ' || pval FROM calls
 WHERE pname = 'p_parent_list_item_id'
   AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_list_item')
UNION ALL
SELECT 'menu option -> missing parent ' || pval FROM calls
 WHERE api = 'create_menu_option' AND pname = 'p_parent_id'
   AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_menu_option')
UNION ALL
SELECT 'region -> missing breadcrumb ' || pval FROM calls
 WHERE pname = 'p_menu_id' AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_menu')
UNION ALL
SELECT 'region/app -> missing list ' || pval FROM calls
 WHERE pname IN ('p_list_id', 'p_navigation_list_id', 'p_nav_bar_list_id')
   AND pval NOT IN (SELECT id FROM ids WHERE api = 'create_list')
UNION ALL
SELECT 'duplicate id ' || id || ' (' || MIN(api) || ', ' || MAX(api) || ')' FROM ids
 WHERE api NOT IN ('create_flow', 'create_page') GROUP BY id HAVING COUNT(*) > 1
UNION ALL
SELECT 'duplicate item name ' || pval FROM calls WHERE api = 'create_page_item' AND pname = 'p_name'
 GROUP BY pval HAVING COUNT(*) > 1
UNION ALL
SELECT 'item ' || pval || ' on page ' || page_id || ' does not start with P' || page_id || '_' FROM calls
 WHERE api = 'create_page_item' AND pname = 'p_name' AND pval NOT LIKE 'P' || page_id || '\_%' ESCAPE '\'
UNION ALL
SELECT 'page ' || page_id || ' duplicate button ' || pval FROM calls
 WHERE api = 'create_page_button' AND pname = 'p_button_name' GROUP BY page_id, pval HAVING COUNT(*) > 1
UNION ALL
SELECT 'duplicate page ' || pval FROM calls WHERE api = 'create_page' AND pname = 'p_id'
 GROUP BY pval HAVING COUNT(*) > 1
UNION ALL
SELECT 'duplicate page alias ' || pval FROM calls WHERE api = 'create_page' AND pname = 'p_alias'
 GROUP BY pval HAVING COUNT(*) > 1
UNION ALL
SELECT 'page ' || page_id || ' duplicate static id ' || api || ' ' || pval FROM calls
 WHERE pname = 'p_static_id' AND api IN ('create_page_plug', 'create_report_region', 'create_page_button',
                                         'create_page_process', 'create_page_da_event')
 GROUP BY page_id, api, pval HAVING COUNT(*) > 1;
prompt ==== component counts
SELECT api, COUNT(*) cnt FROM chk_log WHERE pname = 'p_id' GROUP BY api ORDER BY api;
SELECT 'install script bytes', SUM(LENGTH(pval)) FROM chk_log WHERE api = 'create_install_script' AND pname = 'p_name';
"""


def stubs(vocab):
    pkgs = defaultdict(dict)
    for api, params in vocab['params'].items():
        pkg, proc = api.split('.')
        if pkg in ('wwv_flow_imp', 'wwv_flow_string', 'wwv_flow_application_install', 'wwv_imp_util'):
            continue
        pkgs[pkg][proc] = sorted(params)
    values = vocab.get('values', {})
    out = []
    for pkg, procs in sorted(pkgs.items()):
        spec, body = [], []
        for proc, params in sorted(procs.items()):
            sample = values.get('%s.%s' % (pkg, proc), {})
            decl = []
            for p in params:
                s = sample.get(p, [])
                if s and all(x in ('true', 'false') for x in s):
                    t = 'BOOLEAN'
                elif p == 'p_file_content':
                    t = 'BLOB'
                elif p == 'p_attributes' or p.endswith('_clob'):
                    t = 'CLOB'
                else:
                    t = 'VARCHAR2'
                decl.append((p, t))
            sig = '%s(%s)' % (proc, ', '.join('%s IN %s DEFAULT NULL' % (p, t) for p, t in decl))
            spec.append('  PROCEDURE ' + sig + ';')
            logs = []
            for p, t in decl:
                if t == 'BOOLEAN':
                    v = "CASE WHEN %s THEN 'true' WHEN NOT %s THEN 'false' END" % (p, p)
                elif t == 'CLOB':
                    v = 'DBMS_LOB.SUBSTR(%s, 4000, 1)' % p
                elif t == 'BLOB':
                    v = "'blob of ' || DBMS_LOB.GETLENGTH(%s) || ' bytes'" % p
                else:
                    v = p
                logs.append("    IF %s IS NOT NULL THEN wwv_flow_imp.log('%s', '%s', %s); END IF;" % (p, proc, p, v))
            extra = "    wwv_flow_imp.g_page := p_id;\n" if proc == 'create_page' else ''
            body.append('  PROCEDURE ' + sig + ' IS\n  BEGIN\n' + extra + '\n'.join(logs) + '\n  END;')
        out.append('CREATE OR REPLACE PACKAGE %s AS\n%s\nEND;\n/\nCREATE OR REPLACE PACKAGE BODY %s AS\n%s\nEND;\n/'
                   % (pkg, '\n'.join(spec), pkg, '\n'.join(body)))
    return '\n'.join(out)


def sqlplus(script):
    p = subprocess.run(['docker', 'exec', '-i', CONTAINER, 'sqlplus', '-s', '/ as sysdba'],
                       input=script, capture_output=True, text=True)
    return p.stdout + p.stderr


def main():
    export = sys.argv[1]
    vocab = json.load(open(os.path.join(HERE, 'vocab_26_1.json')))
    # quota on SYSTEM and on the database's default tablespace (USERS on the full Oracle Free image)
    setup = ("alter session set container={pdb};\nwhenever sqlerror continue\n"
             "begin execute immediate 'drop user {s} cascade'; exception when others then null; end;\n/\n"
             "create user {s} no authentication;\n"
             "alter user {s} quota unlimited on system;\n"
             "begin\n  for t in (select default_tablespace ts from dba_users where username = '{s}') loop\n"
             "    execute immediate 'alter user {s} quota unlimited on ' || t.ts;\n  end loop;\nend;\n/\n"
             "alter session set current_schema={s};\n{infra}\n{stubs}\n"
             "select object_name, object_type from dba_objects where owner='{s}' and status <> 'VALID';\n"
             "select name, line, text from dba_errors where owner='{s}' and rownum <= 20;\nexit\n"
             ).format(pdb=PDB, s=SCHEMA, infra=INFRA, stubs=stubs(vocab))
    out = sqlplus(setup)
    bad = [l for l in out.splitlines() if 'ORA-' in l or 'PLS-' in l or 'INVALID' in l]
    if bad:
        print(out[-4000:])
        sys.exit('stub setup failed')
    subprocess.run(['docker', 'cp', export, '%s:/tmp/check_export.sql' % CONTAINER], check=True)
    run = ("alter session set container=%s;\nalter session set current_schema=%s;\n"
           "@/tmp/check_export.sql\nexit\n" % (PDB, SCHEMA))
    out = sqlplus(run)
    errors = [l for l in out.splitlines() if 'ORA-' in l or 'PLS-' in l or 'SP2-' in l]
    if errors or '...done' not in out:
        print(out[-6000:])
        sys.exit('EXPORT FAILED against the APEX 26.1 stubs')
    print('export ran cleanly against the APEX 26.1 stubs')
    print(sqlplus("alter session set container=%s;\nalter session set current_schema=%s;\n%s\nexit\n"
                  % (PDB, SCHEMA, CHECKS)))


if __name__ == '__main__':
    main()
