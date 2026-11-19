#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT=demo/out/datos
mkdir -p "$OUT"
docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}' \
  | grep -E 'NAMES|cie-10|cie10|ai_engine' > "$OUT/compose_ps.txt" || true
make -s help 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | head -40 > "$OUT/make_help.txt" || true
git log --oneline -8 > "$OUT/git_log.txt"
ls .github/workflows 2>/dev/null > "$OUT/workflows.txt" || true
echo "datos escritos en $OUT"
