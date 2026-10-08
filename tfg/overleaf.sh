#!/usr/bin/env bash
set -euo pipefail
P=6762f4f3a84f2b14bc58212b
OL="npx -y claudeleaf"
cd "$(dirname "$0")"
$OL doctor | grep -q "Signed in: yes" || { echo "sesión caducada: npx claudeleaf login" >&2; exit 1; }
R=$(mktemp -d); trap 'rm -rf "$R"' EXIT

pull() {
  rm -rf "$R"/*
  $OL ls $P | awk '$1=="doc"{print $2}' | while read -r f; do
    mkdir -p "$R/$(dirname "$f")"; $OL cat $P "$f" > "$R/$f"
  done
}

show() { diff -ru "$R" . --exclude=build --exclude='*.png' --exclude='*.jpg' --exclude='*.pdf' --exclude='*.sh' || true; }

case ${1:-diff} in
  diff) pull; show ;;
  sync)
    pull
    conflicts=0
    for f in $(cd "$R" && find . -type f | sed 's|^\./||'); do
      [ -f "$f" ] || continue
      cmp -s "$R/$f" "$f" && continue
      if git show "HEAD:tfg/$f" 2>/dev/null | cmp -s - "$R/$f"; then
        $OL set $P "$f" < "$f" && echo "subido      $f"
      elif git diff --quiet HEAD -- "$f"; then
        cp "$R/$f" "$f" && echo "traido      $f"
      else
        echo "CONFLICTO   $f" >&2; conflicts=1
      fi
    done
    pull; echo "--- diff final ---"; show
    exit $conflicts ;;
  imgs)
    curl -sf -o "$R.zip" -H "Cookie: overleaf_session2=$(python3 -c "import json;print(json.load(open('$HOME/.claudeleaf/session.json'))['cookies']['overleaf_session2'])")" https://www.overleaf.com/project/$P/download/zip
    unzip -q "$R.zip" -d "$R"; rm "$R.zip"
    for f in $(cd "$R" && find . -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.pdf' \) | sed 's|^\./||'); do
      if [ ! -f "$f" ]; then echo "solo Overleaf: $f"; elif ! cmp -s "$R/$f" "$f"; then echo "DISTINTO:     $f"; fi
    done
    for f in $(find . -path ./build -prune -o -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.pdf' \) -print | sed 's|^\./||'); do
      [ -f "$R/$f" ] || echo "solo local:   $f"
    done ;;
  all) rc=0; "$0" sync || rc=$?; "$0" imgs; exit $rc ;;
  *) echo "uso: $0 [diff|sync|imgs|all]"; exit 1 ;;
esac
