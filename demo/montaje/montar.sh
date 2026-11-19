#!/usr/bin/env bash
set -euo pipefail
AQUI="$(cd "$(dirname "$0")" && pwd)"
RAIZ="$(cd "$AQUI/../.." && pwd)"
CLIPS_DIR="${CLIPS_DIR:-$RAIZ/demo/out/clips}"
VIDEOS_DIR="${VIDEOS_DIR:-$RAIZ/demo/out/videos}"
FFMPEG_IMAGE="${FFMPEG_IMAGE:-linuxserver/ffmpeg:latest}"
PW_IMAGE="${PW_IMAGE:-mcr.microsoft.com/playwright:v1.56.1-jammy}"
PW_CACHE="${PW_CACHE:-$RAIZ/demo/out/.pw}"
TRABAJO="${TRABAJO:-$RAIZ/demo/out/.montaje}"
VARS_CFG="RECORTE_INI TITULO SUBTITULO COLOR_A COLOR_B COLOR_ACENTO COLOR_TEXTO COLOR_FONDO FONDO_BASE INTRO_S CIERRE_S \
MARCA CIERRE_1 CIERRE_2 CIERRE_3 URL_BARRA MARCO PROGRESO INTRO_TITULO_PX INTRO_SUB_PX \
MUSICA MUSICA_VOL MUSICA_TONOS MUSICA_BPM MUSICA_ESCALA VELOCIDAD"
mkdir -p "$VIDEOS_DIR" "$TRABAJO"

if [ "$#" -gt 0 ]; then NUMS=("$@"); else
  NUMS=(); for f in "$CLIPS_DIR"/*.webm; do [ -e "$f" ] && NUMS+=("$(basename "${f%.webm}")"); done
fi
[ "${#NUMS[@]}" -gt 0 ] || { echo "No hay clips en $CLIPS_DIR" >&2; exit 1; }

num() {
  local min="${4:-0}"
  if awk -v v="$2" -v m="$min" 'BEGIN{exit !(v ~ /^[0-9]+(\.[0-9]+)?$/ && v+0>0 && v+0>=m)}'; then printf '%s' "$2"
  else echo "$1='$2' no es válido (mín. $min); uso $3" >&2; printf '%s' "$3"; fi
}
hex() {
  local c; c="$(printf '%s' "$2" | tr -d '# ' | tr 'A-F' 'a-f')"
  case "$c" in
    [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) printf '#%s' "$c" ;;
    *) echo "$1='$2' no es #rrggbb; uso $3" >&2; printf '%s' "$3" ;;
  esac
}
si() { case "${1:-}" in 0|false|no|NO|False) printf 0 ;; *) printf 1 ;; esac; }
json() { printf '%s' "$1" | tr '\n' ' ' | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
en_ffmpeg() { printf '0x%s' "${1#\#}"; }

asegurar_fuente() {
  [ -d "$PW_CACHE/node_modules/@fontsource-variable/inter" ] && return 0
  mkdir -p "$PW_CACHE"
  local ca=(); [ -n "${CA_PEM:-}" ] && ca=(-v "$CA_PEM:/ca.pem:ro" -e NODE_EXTRA_CA_CERTS=/ca.pem)
  echo "Instalando la fuente Inter"
  docker run --rm -v "$PW_CACHE:/pw" ${ca[@]+"${ca[@]}"} "$PW_IMAGE" \
    sh -c 'cd /pw && npm i --no-audit --no-fund --no-save playwright@1.56.1 @fontsource-variable/inter >/dev/null' \
    || echo "No se pudo instalar Inter; se usa la fuente del sistema" >&2
}

montar_uno() {
  local nn="$1" titulo sub
  local ENVF="$CLIPS_DIR/$nn.env"
  [ -f "$CLIPS_DIR/$nn.webm" ] || { echo "No existe $CLIPS_DIR/$nn.webm" >&2; return 1; }
  if [ -f "$ENVF" ]; then echo "$nn: configuración de $ENVF"; set -a; . "$ENVF"; set +a; fi
  titulo="${TITULO:-Clicoder}"; sub="${SUBTITULO:-}"

  local A B ACC TXT CF BASE VEL INTRO OUTRO MVOL BPM TPX SPX
  A="$(hex COLOR_A "${COLOR_A:-#4338ca}" '#4338ca')"
  B="$(hex COLOR_B "${COLOR_B:-#2563eb}" '#2563eb')"
  ACC="$(hex COLOR_ACENTO "${COLOR_ACENTO:-#22d3ee}" '#22d3ee')"
  TXT="$(hex COLOR_TEXTO "${COLOR_TEXTO:-#ffffff}" '#ffffff')"
  CF="$(hex COLOR_FONDO "${COLOR_FONDO:-#eef2ff}" '#eef2ff')"
  BASE=""; [ -n "${FONDO_BASE:-}" ] && BASE="$(hex FONDO_BASE "$FONDO_BASE" '#0f1434')"
  VEL="$(num VELOCIDAD "${VELOCIDAD:-1}" 1 0.25)"
  local TRIM="${RECORTE_INI:-0.5}"
  awk -v v="$TRIM" 'BEGIN{exit !(v ~ /^[0-9]+(\.[0-9]+)?$/ && v+0<=3)}' || { echo "RECORTE_INI='$TRIM' no es válido (0 a 3 s); uso 0.5" >&2; TRIM=0.5; }
  INTRO="$(num INTRO_S "${INTRO_S:-4}" 4 2.5)"
  OUTRO="$(num CIERRE_S "${CIERRE_S:-4}" 4 2.5)"
  MVOL="$(num MUSICA_VOL "${MUSICA_VOL:-0.10}" 0.10)"
  BPM="$(num MUSICA_BPM "${MUSICA_BPM:-96}" 96 40)"
  TPX="$(num INTRO_TITULO_PX "${INTRO_TITULO_PX:-84}" 84 20)"
  SPX="$(num INTRO_SUB_PX "${INTRO_SUB_PX:-44}" 44 12)"
  local ESC="${MUSICA_ESCALA:-mayor}"; case "$ESC" in mayor|menor) ;; *) echo "MUSICA_ESCALA='$ESC' (mayor|menor); uso mayor" >&2; ESC=mayor ;; esac
  local MUS USA_MARCO USA_PROG; MUS="$(si "${MUSICA:-1}")"; USA_MARCO="$(si "${MARCO:-1}")"; USA_PROG="$(si "${PROGRESO:-1}")"
  local TONOS="${MUSICA_TONOS:-}"
  [ "$TONOS" = "110,164.81,220,277.18" ] && TONOS=""
  local TONOS_JSON=null
  if [ -n "$TONOS" ]; then
    case "$TONOS" in *[!0-9.,]*) echo "MUSICA_TONOS inválido; se ignora" >&2; TONOS="" ;; *) TONOS_JSON="[$TONOS]" ;; esac
  fi

  local DC; DC="$(docker run --rm --entrypoint ffprobe -v "$CLIPS_DIR:/clips:ro" "$FFMPEG_IMAGE" \
      -v error -show_entries format=duration -of csv=p=0 "/clips/$nn.webm" | head -1)"
  case "$DC" in ''|N/A) echo "No puedo leer la duración de $nn.webm" >&2; return 1 ;; esac
  local XF=0.6 DCE OFF1 OFF2 TOTAL
  DCE="$(awk "BEGIN{printf \"%.3f\", ($DC-$TRIM)/$VEL}")"
  OFF1="$(awk "BEGIN{printf \"%.3f\", $INTRO-$XF}")"
  OFF2="$(awk "BEGIN{printf \"%.3f\", $INTRO+$DCE-2*$XF}")"
  TOTAL="$(awk "BEGIN{printf \"%.3f\", $INTRO+$DCE-$XF+$OUTRO-$XF}")"

  local W="$TRABAJO/$nn"; mkdir -p "$W"
  asegurar_fuente
  cat > "$W/params.json" <<EOF
{"A":"$A","B":"$B","ACC":"$ACC","TXT":"$TXT","CF":"$CF","BASE":"${BASE}",
 "marca":"$(json "${MARCA:-Clicoder}")","titulo":"$(json "$titulo")","sub":"$(json "$sub")",
 "c1":"$(json "${CIERRE_1:-Codificación clínica asistida por IA}")","c2":"$(json "${CIERRE_2:-Proyecto de fin de grado}")","c3":"$(json "${CIERRE_3:-}")",
 "url":"$(json "${URL_BARRA:-${MARCA:-Clicoder}}")","tituloPx":$TPX,"subPx":$SPX,
 "introS":$INTRO,"cierreS":$OUTRO,"t0Clip":$OFF1,"t0Cierre":$OFF2,"totalS":$TOTAL,
 "musica":$([ "$MUS" = 1 ] && echo true || echo false),"bpm":$BPM,"escala":"$ESC","tonos":$TONOS_JSON}
EOF
  local t0=$SECONDS
  echo "+ docker run $PW_IMAGE  (render de intro, cierre y marco: $nn)"
  docker run --rm --ipc=host -v "$AQUI/plantillas:/plantillas:ro" -v "$PW_CACHE:/pw:ro" -v "$W:/salida" \
    "$PW_IMAGE" node /plantillas/render.mjs
  echo "$nn: recursos listos en $((SECONDS - t0)) s"

  cat > "$W/montaje.env" <<EOF
NN='$nn'; INTRO='$INTRO'; OUTRO='$OUTRO'; DCE='$DCE'; OFF1='$OFF1'; OFF2='$OFF2'; TOTAL='$TOTAL'; XF='$XF'
VEL='$VEL'; TRIM='$TRIM'; CF='$(en_ffmpeg "$CF")'; CA='$(en_ffmpeg "$A")'; CACC='$(en_ffmpeg "$ACC")'
MUSICA='$MUS'; MVOL='$MVOL'; MARCO='$USA_MARCO'; PROGRESO='$USA_PROG'
EOF
  t0=$SECONDS
  echo "+ docker run $FFMPEG_IMAGE  (composicion con ffmpeg: $nn)"
  docker run --rm --entrypoint sh -e FFLOG="${FFLOG:-error}" \
    -v "$AQUI/componer.sh:/montar.sh:ro" -v "$CLIPS_DIR:/clips:ro" -v "$W:/work:ro" -v "$VIDEOS_DIR:/videos" \
    "$FFMPEG_IMAGE" /montar.sh
  echo "$nn: composición en $((SECONDS - t0)) s"
}

for nn in "${NUMS[@]}"; do
  ( for v in $VARS_CFG; do unset "$v"; done; montar_uno "$nn" )
done
