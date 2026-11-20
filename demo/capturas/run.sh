#!/usr/bin/env bash
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
VALIDAR=""; ARG=""
for a in "$@"; do
  if [ "$a" = "--validar" ]; then VALIDAR="--validar "; else ARG="$a"; fi
done
ARG="${ARG:-all}"

ordenes=()
anadir() {
  local nn; nn="$(printf '%02d' "$((10#$1))")"
  [ -f "$RAIZ/demo/guiones/$nn.yml" ] || { echo "No existe demo/guiones/$nn.yml" >&2; exit 2; }
  ordenes+=("node runner.mjs $VALIDAR$nn")
}

case "$ARG" in
  all) for f in "$RAIZ"/demo/guiones/[0-9][0-9].yml; do anadir "$(basename "$f" .yml)"; done ;;
  *.yml)
    f="$ARG"; [ -f "$f" ] || f="$RAIZ/$ARG"; [ -f "$f" ] || f="$RAIZ/demo/guiones/$ARG"
    [ -f "$f" ] || { echo "No existe $ARG" >&2; exit 2; }
    f="$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"
    ordenes+=("node runner.mjs $VALIDAR/work/${f#"$RAIZ"/}") ;;
  *) anadir "$ARG" ;;
esac

LOCK="$RAIZ/demo/out/.grabando"
mkdir -p "$RAIZ/demo/out"
if [ -z "$VALIDAR" ]; then
  while ! mkdir "$LOCK" 2>/dev/null; do
    pid="$(cat "$LOCK/pid" 2>/dev/null || true)"
    if [ -n "$pid" ] && ! kill -0 "$pid" 2>/dev/null; then
      echo "Libero el bloqueo del proceso $pid"; rm -rf "$LOCK"; continue
    fi
    if [ -z "$pid" ] && [ -n "$(find "$LOCK" -maxdepth 0 -mmin +10 2>/dev/null)" ]; then
      echo "Libero un bloqueo sin dueño"; rm -rf "$LOCK"; continue
    fi
    echo "Hay otra grabación en marcha (proceso ${pid:-?}), espero"; sleep 5
  done
  echo "$$" > "$LOCK/pid"
  trap 'rm -rf "$LOCK"' EXIT INT TERM
fi

leer_env() {
  [ -f "$RAIZ/.env" ] || return 0
  sed -n "s/^$1=//p" "$RAIZ/.env" | head -1 | sed -e "s/^[\"']//" -e "s/[\"']\$//"
}
: "${DEMO_EMAIL:=$(leer_env SEED_ADMIN_EMAIL)}"
: "${DEMO_PASSWORD:=$(leer_env SEED_ADMIN_PASSWORD)}"
PW_CACHE="${PW_CACHE:-$RAIZ/demo/out/.pw}"
mkdir -p "$PW_CACHE"

EXTRA=()
if [ -n "${CA_PEM:-}" ]; then EXTRA+=(-v "$CA_PEM:/ca.pem:ro" -e NODE_EXTRA_CA_CERTS=/ca.pem); fi
for n in AI_URL GRAFANA_URL GRAFANA_USER GRAFANA_PASSWORD PROM_URL; do
  if [ -n "${!n:-}" ]; then EXTRA+=(-e "$n"); fi
done

CMD='set -e
[ -d /tmp/pw/node_modules/playwright ] && [ -d /tmp/pw/node_modules/yaml ] || \
  PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm i --prefix /tmp/pw --no-audit --no-fund playwright@1.56.1 yaml@2 >/dev/null'
CMD+=$'\n'"trap 'chown -R $(id -u):$(id -g) /work/demo/out' EXIT"
for o in "${ordenes[@]}"; do CMD+=$'\n'"echo '>> $o'"$'\n'"$o"; done

echo "+ docker run mcr.microsoft.com/playwright:v1.56.1-jammy  (runner.mjs, BASE_URL=${BASE_URL:-http://localhost:3100})"
docker run --rm --ipc=host --add-host=host.docker.internal:host-gateway \
  ${EXTRA[@]+"${EXTRA[@]}"} \
  -v "$RAIZ:/work" -v "$PW_CACHE:/tmp/pw" -w /work/demo/capturas \
  -e BASE_URL="${BASE_URL:-http://localhost:3100}" \
  -e MAILPIT_URL="${MAILPIT_URL:-http://host.docker.internal:8025}" \
  -e DEMO_EMAIL="${DEMO_EMAIL:-}" -e DEMO_PASSWORD="${DEMO_PASSWORD:-}" \
  -e PW_MODULES=/tmp/pw/node_modules \
  mcr.microsoft.com/playwright:v1.56.1-jammy sh -c "$CMD"
