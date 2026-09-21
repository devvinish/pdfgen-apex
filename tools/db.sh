#!/usr/bin/env bash
# PDF Report Designer - local database helper (the Rounds test container, APEX 26.1).
#
# Usage: tools/db.sh <step> [arguments]
#   schema            create the PDFGEN schema and add it to the APEX workspace
#   run FILE...       run SQL files as PDFGEN, then list compile errors
#   sql               run SQL from stdin as PDFGEN
#   import FILE ID    import an application export into the workspace (parsing schema PDFGEN)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONTAINER="${CONTAINER:-rounds-apex}"
PDB="${PDB:-FREEPDB1}"
set -a; . "$ROOT/local/credentials.env"; set +a
mkdir -p "$ROOT/local/logs"

sysdba() { docker exec -e NLS_LANG=AMERICAN_AMERICA.AL32UTF8 -i "$CONTAINER" sqlplus -s / as sysdba; }
asuser() { docker exec -e NLS_LANG=AMERICAN_AMERICA.AL32UTF8 -i "$CONTAINER" sqlplus -s /nolog; }

schema() {
  sysdba <<EOF
alter session set container=$PDB;
whenever sqlerror exit failure
set serveroutput on feedback off
declare
  l number;
begin
  select count(*) into l from dba_users where username = '$SCHEMA';
  if l = 0 then
    execute immediate 'create user $SCHEMA identified by "$SCHEMA_PASSWORD" default tablespace users quota unlimited on users';
  end if;
  execute immediate 'grant create session, create table, create view, create sequence, create procedure, '
                    || 'create trigger, create type, create synonym to $SCHEMA';
  select count(*) into l from apex_workspace_schemas where workspace_name = '$WORKSPACE' and schema = '$SCHEMA';
  if l = 0 then
    apex_instance_admin.add_schema(p_workspace => '$WORKSPACE', p_schema => '$SCHEMA');
  end if;
  commit;
  dbms_output.put_line('schema $SCHEMA ready in workspace $WORKSPACE');
end;
/
exit
EOF
}

run() {
  for f in "$@"; do docker cp "$f" "$CONTAINER:/tmp/$(basename "$f")"; done
  {
    echo "connect $SCHEMA/\"$SCHEMA_PASSWORD\"@localhost:1521/$PDB"
    echo "set define off"
    echo "set serveroutput on size unlimited"
    for f in "$@"; do echo "@/tmp/$(basename "$f")"; done
    cat <<EOF
set lines 220 pages 200 feedback off
col name for a24
col text for a150
select name, type, line, position, text from user_errors order by name, type, sequence;
select object_type, object_name from user_objects where status <> 'VALID' order by 1, 2;
exit
EOF
  } | asuser 2>&1 | grep -vE '^[[:space:]]*$' \
    | grep -vE '^(Package|Package body|Table|View|Trigger|Procedure|Function|Sequence|Index|Type|Synonym) (created|altered|dropped)\.$' \
    | grep -vE '^(Commit complete|PL/SQL procedure successfully completed)\.$|^Connected\.$' || true
}

sql() {
  { echo "connect $SCHEMA/\"$SCHEMA_PASSWORD\"@localhost:1521/$PDB"; echo "set define off"; echo "set serveroutput on size unlimited"; cat; echo "exit"; } \
    | asuser 2>&1 | grep -v '^Connected\.$'
}

import_app() {
  local file="$1" app_id="$2"
  docker cp "$file" "$CONTAINER":/tmp/app_import.sql
  sysdba > "$ROOT/local/logs/import_$app_id.log" 2>&1 <<EOF
alter session set container=$PDB;
begin
  apex_application_install.set_workspace('$WORKSPACE');
  apex_application_install.set_application_id($app_id);
  apex_application_install.generate_offset;
  apex_application_install.set_schema('$SCHEMA');
end;
/
@/tmp/app_import.sql
exit
EOF
  if grep -q '\.\.\.done' "$ROOT/local/logs/import_$app_id.log" && ! grep -qE 'ORA-|PLS-|SP2-' "$ROOT/local/logs/import_$app_id.log"; then
    echo "application $app_id imported"
  else
    grep -E 'ORA-|PLS-|SP2-' "$ROOT/local/logs/import_$app_id.log" | head -20
    echo "import of $file FAILED - see local/logs/import_$app_id.log"
    return 1
  fi
}

case "${1:-}" in
  schema) schema ;;
  run) shift; run "$@" ;;
  sql) sql ;;
  import) shift; import_app "$@" ;;
  *) sed -n '2,9p' "$0"; exit 1 ;;
esac
