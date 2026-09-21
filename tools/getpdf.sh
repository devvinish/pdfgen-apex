#!/usr/bin/env bash
# Save a BLOB to a local file: tools/getpdf.sh "<select returning one blob>" OUT.pdf
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
Q="$1"
OUT="$2"
{
  echo "set heading off feedback off pagesize 0 linesize 4100 trimspool on"
  echo "with d as ($Q)"
  echo "select rawtohex(dbms_lob.substr((select * from d), 2000, (level - 1) * 2000 + 1))"
  echo "  from dual connect by level <= ceil(dbms_lob.getlength((select * from d)) / 2000);"
} | "$ROOT/tools/db.sh" sql | grep -E '^[0-9A-F]+$' | tr -d '\n' | xxd -r -p > "$OUT"
ls -l "$OUT" | awk '{print $5, $9}'
