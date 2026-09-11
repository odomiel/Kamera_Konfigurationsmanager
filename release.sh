#!/usr/bin/env bash
#
# Formalisierter Release-Vorgang: (optional bauen) -> Smoke-Test -> Forgejo-Release
# -> (falls konfiguriert) GitHub-Release am oeffentlichen Push-Mirror.
#
# Setzt voraus, dass die Version bereits per bump_version.py hochgezaehlt und ein
# CHANGELOG.md-Eintrag geschrieben wurde (Repo-Ritual). Dieses Skript baut das
# AppImage der aktuellen Version (falls noch nicht vorhanden), testet es kurz und
# legt daraus ein Forgejo-Release an (Tag v<version>, Release-Notes aus CHANGELOG,
# AppImage als Asset). Liegt zusaetzlich ein Windows-Build gleicher Version unter
# dist/Kamerakonfigurationsmanager_<version>.exe (separat auf Windows gebaut), wird
# er als weiteres Asset mitveroeffentlicht. Ist ein GitHub-Mirror konfiguriert
# (Slug + Token, siehe unten), wird der Push-Mirror angestossen und dort dasselbe
# Release mit denselben Assets angelegt (Releases werden vom Mirror selbst NICHT
# uebertragen).
#
# GitHub-Konfiguration ausserhalb des Repos (das Repo wird oeffentlich gespiegelt):
#   ~/.config/kamera_konfigurationsmanager/github_repo   (owner/repo)  oder $KKM_GITHUB_SLUG
#   ~/.config/kamera_konfigurationsmanager/github_token  (Contents:RW) oder $GITHUB_TOKEN
#
# Aufruf:
#   ./release.sh                 # bauen (falls noetig) + testen + Forgejo + GitHub
#   ./release.sh --no-build      # vorhandenes AppImage der Version verwenden
#   ./release.sh --build         # Neubau erzwingen
#   ./release.sh --no-test       # Smoke-Test ueberspringen
#   ./release.sh --no-github     # nur Forgejo, GitHub-Schritt auslassen
#   ./release.sh --draft         # Release(s) als Entwurf anlegen
#   ./release.sh --dry-run       # nichts hochladen, nur anzeigen
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

FORCE_BUILD=0
NO_BUILD=0
DO_TEST=1
GITHUB=1
PASS_ARGS=()          # --draft / --dry-run, an alle Release-Tools durchgereicht

while [ $# -gt 0 ]; do
  case "$1" in
    --build)     FORCE_BUILD=1 ;;
    --no-build)  NO_BUILD=1 ;;
    --no-test)   DO_TEST=0 ;;
    --no-github) GITHUB=0 ;;
    --draft)     PASS_ARGS+=(--draft) ;;
    --dry-run)   PASS_ARGS+=(--dry-run) ;;
    -h|--help)
      awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"
      exit 0 ;;
    *) echo "Unbekannte Option: $1" >&2; exit 2 ;;
  esac
  shift
done

# GitHub-Schritt nur, wenn Slug UND Token konfiguriert sind (env oder lokale Datei).
CFG="$HOME/.config/kamera_konfigurationsmanager"
github_configured() {
  { [ -n "${KKM_GITHUB_SLUG:-}" ] || [ -s "$CFG/github_repo" ]; } &&
  { [ -n "${GITHUB_TOKEN:-}" ]    || [ -s "$CFG/github_token" ]; }
}

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

# 3) Assets zusammenstellen: AppImage + (falls vorhanden) Windows-.exe gleicher
#    Version aus dem dist/-Ordner. Die .exe wird separat auf Windows gebaut; liegt
#    sie zur aktuellen Version bereit, kommt sie ins selbe Release.
WINEXE="dist/Kamerakonfigurationsmanager_${VERSION}.exe"
ASSETS=("$APPIMAGE")
if [ -f "$WINEXE" ]; then
  echo "-> Windows-Build gefunden: $WINEXE ($(stat -c%s "$WINEXE") Bytes) — wird mitveroeffentlicht."
  ASSETS+=("$WINEXE")
else
  echo "-> Kein Windows-Build fuer $VERSION in dist/ — nur AppImage."
fi

# 4) Forgejo-Release ----------------------------------------------------------
echo "-> Lege Forgejo-Release an ..."
python3 tools/forgejo_release.py "${ASSETS[@]}" --version "$VERSION" "${PASS_ARGS[@]}"

# 5) GitHub-Release am Push-Mirror (Releases werden nicht mitgespiegelt) -------
if [ "$GITHUB" = 1 ]; then
  if github_configured; then
    echo "-> Stosse Forgejo-Push-Mirror an ..."
    # Nicht fatal: der Sync-Endpunkt liefert gelegentlich ein transientes HTTP 500,
    # und der GitHub-Schritt wartet ohnehin selbst auf den Tag (sync_on_commit hat
    # ihn i. d. R. schon uebertragen).
    if ! python3 tools/forgejo_release.py --sync-mirror "${PASS_ARGS[@]}"; then
      echo "   WARNUNG: Mirror-Sync-Anstoss fehlgeschlagen — fahre fort, GitHub-Schritt wartet auf den Tag."
    fi
    echo "-> Lege GitHub-Release an ..."
    python3 tools/github_release.py "${ASSETS[@]}" --version "$VERSION" "${PASS_ARGS[@]}"
  else
    echo "-> GitHub-Release uebersprungen (kein Slug/Token konfiguriert; siehe --help)."
  fi
fi
