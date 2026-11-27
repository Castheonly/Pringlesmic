#!/usr/bin/env bash
# Guarda state/ (y config.yaml si cambió) en GitHub sin pisar lo que otras corridas subieron.
# Uso: scripts/save_state.sh "mensaje del commit"
set -u
MSG="${1:-Actualizar registro}"
git config user.name "auto-clipper"
git config user.email "actions@users.noreply.github.com"
TMP=$(mktemp -d)
mkdir -p "$TMP/base" "$TMP/ours"
for f in $(git ls-tree --name-only HEAD state/ 2>/dev/null); do git show "HEAD:$f" > "$TMP/base/$(basename "$f")"; done
cp -r state/. "$TMP/ours/"
CONFIG_CHANGED=0
git diff --quiet HEAD -- config.yaml || { CONFIG_CHANGED=1; cp config.yaml "$TMP/config.yaml"; }
for i in 1 2 3 4 5; do
  git fetch -q origin main && git reset -q --hard origin/main
  mkdir -p state
  python -m clipper.state_merge "$TMP/base" "$TMP/ours" state
  [ "$CONFIG_CHANGED" = 1 ] && cp "$TMP/config.yaml" config.yaml
  git add state/ config.yaml
  git diff --cached --quiet && { echo "Sin cambios que guardar"; exit 0; }
  git commit -q -m "$MSG [skip ci]"
  git push -q origin HEAD:main && { echo "Registro guardado"; exit 0; }
  sleep $((RANDOM % 10 + 3))
done
echo "No pude guardar el registro tras 5 intentos"; exit 1
