#!/usr/bin/env bash
# Build the customer zip: release/vinaura-<version>.zip (the application export, the SQL scripts and the guides).
# Usage: tools/make_zip.sh [version]   (default 1.0)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-1.0}"
NAME="vinaura-$VER"
OUT="$ROOT/release"
STAGE="$(mktemp -d)/$NAME"
mkdir -p "$STAGE/sql" "$STAGE/docs" "$OUT"
cp "$ROOT/dist/pdf_report_designer.sql" "$STAGE/"
cp "$ROOT"/sql/*.sql "$STAGE/sql/"
cp "$ROOT/docs/INSTALL.md" "$STAGE/docs/"
cp "$ROOT/README.md" "$STAGE/"
rm -f "$OUT/$NAME.zip"
(cd "$(dirname "$STAGE")" && zip -qr "$OUT/$NAME.zip" "$NAME")
rm -rf "$(dirname "$STAGE")"
echo "$OUT/$NAME.zip"
