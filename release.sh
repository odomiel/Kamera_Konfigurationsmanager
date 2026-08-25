#!/usr/bin/env bash
#
# Formalisierter Release-Vorgang: (optional bauen) -> Smoke-Test -> Forgejo-Release.
#
# Setzt voraus, dass die Version bereits per bump_version.py hochgezaehlt und ein
# CHANGELOG.md-Eintrag geschrieben wurde (Repo-Ritual). Dieses Skript baut das
# AppImage der aktuellen Version (falls noch nicht vorhanden), testet es kurz und
# legt daraus ein Forgejo-Release an (Tag v<version>, Release-Notes aus CHANGELOG,
# AppImage als Asset).
#
# Aufruf:
#   ./release.sh                 # bauen (falls noetig) + testen + Release anlegen
#   ./release.sh --no-build      # vorhandenes AppImage der Version verwenden
#   ./release.sh --build         # Neubau erzwingen
#   ./release.sh --no-test       # Smoke-Test ueberspringen
#   ./release.sh --draft         # Release als Entwurf anlegen
#   ./release.sh --dry-run       # nichts hochladen, nur anzeigen
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

FORCE_BUILD=0
NO_BUILD=0
DO_TEST=1
FORGEJO_ARGS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --build)     FORCE_BUILD=1 ;;
    --no-build)  NO_BUILD=1 ;;
    --no-test)   DO_TEST=0 ;;
    --draft)     FORGEJO_ARGS+=(--draft) ;;
    --dry-run)   FORGEJO_ARGS+=(--dry-run) ;;
    -h|--help)
      awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"
      exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

VERSION="$(python3 bump_version.py --print)"
APPIMAGE="Kamerakonfigurationsmanager-${VERSION}-x86_64.AppImage"

echo "== Release ${VERSION} =="

# 1) Bauen (falls noetig) -----------------------------------------------------
if [ "$FORCE_BUILD" = 1 ] || { [ ! -f "$APPIMAGE" ] && [ "$NO_BUILD" = 0 ]; }; then
  echo "-> Baue AppImage ($APPIMAGE) ..."
  ./build_appimage.sh
elif [ ! -f "$APPIMAGE" ]; then
  echo "FEHLER: $APPIMAGE fehlt und --no-build gesetzt." >&2
  exit 1
else
  echo "-> Verwende vorhandenes $APPIMAGE ($(stat -c%s "$APPIMAGE") Bytes)."
fi

# 2) Smoke-Test (rc=124 = Timeout erreicht = sauber gestartet) ----------------
if [ "$DO_TEST" = 1 ]; then
  echo "-> Smoke-Test ..."
  TESTHOME="$(mktemp -d)"
  set +e
  XDG_CONFIG_HOME="$TESTHOME" timeout 12 "./$APPIMAGE" >/dev/null 2>&1
  RC=$?
  set -e
  rm -rf "$TESTHOME"
  if [ "$RC" = 124 ]; then
    echo "   Smoke-Test bestanden (rc=124)."
  elif [ "$RC" = 0 ]; then
    echo "   AppImage sauber beendet (rc=0)."
  else
    echo "FEHLER: Smoke-Test rc=$RC (kein sauberer Start)." >&2
    exit 1
  fi
fi

# 3) Forgejo-Release ----------------------------------------------------------
echo "-> Lege Forgejo-Release an ..."
python3 tools/forgejo_release.py "$APPIMAGE" --version "$VERSION" "${FORGEJO_ARGS[@]}"
