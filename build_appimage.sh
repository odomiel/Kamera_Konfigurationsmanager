#!/usr/bin/env bash
#
# Baut ein eigenstaendiges AppImage des Kamera_Konfigurationsmanagers mit Tcl/Tk 9.
#
# Wie beim Axis_Kamera_Discovery-Tool: da kein Basis-Image mit Tk 9 existiert,
# werden Tcl 9, Tk 9 und Python 3.14 aus dem Quellcode gebaut. libffi (fuer
# _ctypes -> ifaddr/zeroconf) und OpenSSL (fuer das ssl-Modul -> HTTPS/VAPIX)
# ebenfalls. Reine Laufzeit-Pakete kommen als fertige Wheels (kein pip noetig):
# zeroconf (+ifaddr) fuer die Discovery, cryptography (+cffi/pycparser) fuer den
# Passwort-Tresor (AES-256-GCM).
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$ROOT/.tk9build"
SRC="$BUILD/src"
APPDIR="$BUILD/AppDir"
PREFIX="$APPDIR/usr"
JOBS="$(nproc)"

TCL_VER=9.0.4
TK_VER=9.0.4
PY_VER=3.14.7
PY_XY=3.14
FFI_VER=3.8.0
SSL_VER=3.5.7

APP=Kamerakonfigurationsmanager

mkdir -p "$SRC"
rm -rf "$APPDIR"
mkdir -p "$PREFIX"

dl() {  # dl <url> <zieldatei>
    local url="$1" out="$2"
    [ -f "$out" ] || { echo ">> download $(basename "$out")"; curl -fSL "$url" -o "$out"; }
}

# --------------------------------------------------------------- 1. Quellen
# Cache-Dateinamen enthalten die Version, damit ein Versions-Bump automatisch neu
# lädt (sonst bliebe ein alter Tarball gleichen Namens liegen -> falsche Version).
dl "https://downloads.sourceforge.net/project/tcl/Tcl/$TCL_VER/tcl$TCL_VER-src.tar.gz" "$SRC/tcl-$TCL_VER.tar.gz"
dl "https://downloads.sourceforge.net/project/tcl/Tcl/$TK_VER/tk$TK_VER-src.tar.gz"    "$SRC/tk-$TK_VER.tar.gz"
dl "https://www.python.org/ftp/python/$PY_VER/Python-$PY_VER.tgz"                       "$SRC/python-$PY_VER.tgz"
dl "https://github.com/libffi/libffi/releases/download/v$FFI_VER/libffi-$FFI_VER.tar.gz" "$SRC/libffi-$FFI_VER.tar.gz"
dl "https://github.com/openssl/openssl/releases/download/openssl-$SSL_VER/openssl-$SSL_VER.tar.gz" "$SRC/openssl-$SSL_VER.tar.gz"

cd "$SRC"
rm -rf "tcl$TCL_VER" "tk$TK_VER" "Python-$PY_VER" "libffi-$FFI_VER" "openssl-$SSL_VER"
tar xf "tcl-$TCL_VER.tar.gz"; tar xf "tk-$TK_VER.tar.gz"; tar xf "python-$PY_VER.tgz"
tar xf "libffi-$FFI_VER.tar.gz"; tar xf "openssl-$SSL_VER.tar.gz"

export PKG_CONFIG_PATH="$PREFIX/lib/pkgconfig"
export LD_LIBRARY_PATH="$PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# --------------------------------------------------------------- 2. libffi
echo "==== libffi $FFI_VER ===="
cd "$SRC/libffi-$FFI_VER"
./configure --prefix="$PREFIX" --disable-static --disable-docs >/dev/null
make -j"$JOBS" >/dev/null
make install >/dev/null

# --------------------------------------------------------------- 2b. OpenSSL
echo "==== OpenSSL $SSL_VER ===="
cd "$SRC/openssl-$SSL_VER"
./Configure --prefix="$PREFIX" --libdir=lib --openssldir="$PREFIX/ssl" \
            shared -Wl,-rpath,'$ORIGIN/../lib' >/dev/null
make -j"$JOBS" >/dev/null
make install_sw >/dev/null

# --------------------------------------------------------------- 3. Tcl 9
echo "==== Tcl $TCL_VER ===="
cd "$SRC/tcl$TCL_VER/unix"
# Tcl 9 baut beim zipfs-Schritt eine frische libtcl9.0.so und fuehrt den ebenso
# frischen tclsh aus -> dieser muss die Lib im Build-Verzeichnis finden (sonst
# "cannot open libtcl9.0.so"). Build-Verzeichnis daher auf den Loader-Pfad legen.
export LD_LIBRARY_PATH="$PWD${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
./configure --prefix="$PREFIX" --enable-shared --enable-64bit >/dev/null
make -j"$JOBS" >/dev/null
make install >/dev/null
ln -sf "$PREFIX/bin/tclsh$TCL_VER" "$PREFIX/bin/tclsh${TCL_VER%.*}" 2>/dev/null || true

# --------------------------------------------------------------- 4. Tk 9
echo "==== Tk $TK_VER ===="
cd "$SRC/tk$TK_VER/unix"
./configure --prefix="$PREFIX" --with-tcl="$PREFIX/lib" \
            --enable-shared --enable-64bit --enable-xft >/dev/null
make -j"$JOBS" >/dev/null
make install >/dev/null

# --------------------------------------------------------------- 5. Python 3.14
echo "==== Python $PY_VER (gegen Tcl/Tk 9) ===="
cd "$SRC/Python-$PY_VER"
./configure \
    --prefix="$PREFIX" \
    --enable-shared \
    --with-ensurepip=no \
    --with-openssl="$PREFIX" \
    --with-openssl-rpath=auto \
    --with-tcltk-includes="-I$PREFIX/include" \
    --with-tcltk-libs="-L$PREFIX/lib -ltcl9.0 -ltk9.0" \
    CPPFLAGS="-I$PREFIX/include" \
    LDFLAGS="-L$PREFIX/lib -Wl,-rpath,\$\$ORIGIN/../lib" \
    >/dev/null
make -j"$JOBS" >/dev/null 2>&1
make install >/dev/null 2>&1

PYBIN="$PREFIX/bin/python$PY_XY"
echo ">> Tcl/Tk-Version im neuen Python:"
"$PYBIN" -c "import tkinter; r=tkinter.Tk(); print('  Tcl/Tk', r.tk.call('info','patchlevel')); r.destroy()"
echo ">> OpenSSL-Version im neuen Python:"
"$PYBIN" -c "import ssl; print('  ', ssl.OPENSSL_VERSION)"

# --------------------------------------------------------------- 6. Wheels vendoren
echo "==== Laufzeit-Pakete (Wheels) ===="
SITE="$PREFIX/lib/python$PY_XY/site-packages"
mkdir -p "$SITE"
wheel() {  # wheel <pypi-paket> <filter>
    local pkg="$1" filt="$2"
    local url
    url=$(curl -s "https://pypi.org/pypi/$pkg/json" | "$PYBIN" -c "
import json,sys
d=json.load(sys.stdin); v=d['info']['version']
for f in d['releases'][v]:
    n=f['filename']
    if $filt:
        print(f['url']); break
")
    [ -n "$url" ] || { echo "FEHLER: kein passendes Wheel fuer $pkg gefunden"; exit 1; }
    echo ">> $pkg: $(basename "$url")"
    curl -fsSL "$url" -o "$BUILD/$pkg.whl"
    "$PYBIN" -m zipfile -e "$BUILD/$pkg.whl" "$SITE/"
}
# Discovery (mDNS/Zeroconf). Filter 'cp314-cp314-' waehlt die regulaere ABI und
# schliesst die free-threaded 't'-Wheels (cp314t) aus -- unser Python ist GIL-Build.
wheel zeroconf     "'cp314-cp314-' in n and 'manylinux' in n and 'x86_64' in n"
wheel ifaddr       "n.endswith('.whl')"
# Passwort-Tresor (AES-256-GCM). cryptography-Wheels sind abi3 (cp39+).
wheel cryptography "'abi3' in n and 'manylinux' in n and 'x86_64' in n"
wheel cffi         "'cp314-cp314-' in n and 'manylinux' in n and 'x86_64' in n"
wheel pycparser    "n.endswith('.whl')"
# Modernes Sun-Valley-Theme (reines py3-none-any-Wheel inkl. Tcl-Dateien)
wheel sv-ttk       "n.endswith('.whl')"

echo ">> Importtest der gebuendelten Pakete:"
"$PYBIN" -c "import zeroconf, ifaddr, cryptography, sv_ttk; \
from cryptography.hazmat.primitives.ciphers.aead import AESGCM; \
print('  zeroconf', zeroconf.__version__, '| cryptography', cryptography.__version__, \
'| sv_ttk ok')"

# --------------------------------------------------------------- 7. App + AppDir
echo "==== AppDir zusammenstellen ===="
mkdir -p "$APPDIR/app"
cp "$ROOT/main.py" "$ROOT/README.md" "$ROOT/HILFE.md" "$ROOT/HILFE_EN.md" "$ROOT/LICENSE" "$ROOT/THIRD_PARTY_LICENSES.md" "$APPDIR/app/"
cp -r "$ROOT/kkm" "$APPDIR/app/"
find "$APPDIR/app" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true

# Icon: vorhandenes nehmen, sonst minimalen Platzhalter erzeugen.
ICON_SRC="$ROOT/assets/$APP.png"
if [ -f "$ICON_SRC" ]; then
    cp "$ICON_SRC" "$APPDIR/$APP.png"
else
    echo ">> kein assets/$APP.png -> Platzhalter-Icon wird erzeugt"
    base64 -d > "$APPDIR/$APP.png" <<'PNG'
iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAHElEQVR42mNkYPhfz0AEYBxVSF+F
o4qEgAEAQ7AL8a9aQ1cAAAAASUVORK5CYII=
PNG
fi

cat > "$APPDIR/$APP.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$APP
GenericName=Kamera-Konfigurationsmanager
Comment=Verwaltet und konfiguriert Netzwerkkameras (Axis-Plugin)
Exec=AppRun %u
Icon=$APP
Categories=Network;Utility;
Terminal=false
DESKTOP

# AppRun: eigenstaendige Python/Tcl/Tk-Umgebung, startet die GUI (main.py).
cat > "$APPDIR/AppRun" <<APPRUN
#!/bin/bash
HERE="\$(dirname "\$(readlink -f "\$0")")"
export APPDIR="\$HERE"
export PYTHONHOME="\$HERE/usr"
export PYTHONDONTWRITEBYTECODE=1
export LD_LIBRARY_PATH="\$HERE/usr/lib\${LD_LIBRARY_PATH:+:\$LD_LIBRARY_PATH}"
# Das selbst gebaute OpenSSL bringt keinen CA-Speicher mit (ssl: cafile=None).
# Fuer die Kameras ist das egal (ungeprueftes SSL, selbstsignierte Zertifikate),
# aber HTTPS ins Internet — die Firmware-Update-Suche — scheitert daran. Daher
# den CA-Speicher des Systems suchen, falls der Nutzer nichts vorgibt.
if [ -z "\$SSL_CERT_FILE" ]; then
    for ca in /etc/ssl/certs/ca-certificates.crt /etc/pki/tls/certs/ca-bundle.crt \\
              /etc/ssl/ca-bundle.pem /etc/ssl/cert.pem; do
        if [ -r "\$ca" ]; then export SSL_CERT_FILE="\$ca"; break; fi
    done
fi
if [ -z "\$SSL_CERT_DIR" ] && [ -d /etc/ssl/certs ]; then
    export SSL_CERT_DIR=/etc/ssl/certs
fi
# Tcl/Tk 9 betten ihre Script-Library per zipfs in die .so ein -> kein
# TCL_LIBRARY/TK_LIBRARY noetig.
exec "\$HERE/usr/bin/python$PY_XY" "\$HERE/app/main.py" "\$@"
APPRUN
chmod +x "$APPDIR/AppRun"

# --------------------------------------------------------------- 7b. Verschlanken
# Alles Folgende ist reiner Build-Ballast, der zur Laufzeit nie angefasst wird —
# entfernen halbiert die AppImage grob (siehe CHANGELOG). Bewusst NICHT angetastet:
# die selbst gebauten .so (nur gestrippt), cryptographys _rust.abi3.so, Tcl/Tk-tzdata.
echo "==== AppDir verschlanken ===="
_before=$(du -sm "$PREFIX" | cut -f1)

# (1) statische Bibliotheken (libpython*.a ~69 MB, libcrypto/ssl.a ~14 MB): wir
#     linken ausschliesslich die shared libs.
find "$PREFIX" -name "*.a" -delete 2>/dev/null || true
# (2) Header, Manpages, Doku, pkg-config/cmake-Metadaten: alles nur zum Kompilieren.
rm -rf "$PREFIX/include" "$PREFIX/share/man" "$PREFIX/share/doc" \
       "$PREFIX/lib/pkgconfig" "$PREFIX/lib/cmake" 2>/dev/null || true
# (3) ensurepip inkl. gebuendeltem pip-Wheel (wir bauen mit --with-ensurepip=no,
#     Reste bleiben trotzdem liegen) und die openssl-Kommandozeile.
rm -rf "$PREFIX/lib/python$PY_XY/ensurepip" "$PREFIX/bin/openssl" 2>/dev/null || true
# (4) Test-Suiten der Standardbibliothek und Test-Erweiterungsmodule.
rm -rf "$PREFIX/lib/python$PY_XY/test" "$PREFIX/lib/python$PY_XY/"*/test \
       "$PREFIX/lib/python$PY_XY/idlelib" "$PREFIX/lib/python$PY_XY/turtledemo" \
       "$PREFIX/lib/python$PY_XY/lib2to3" 2>/dev/null || true
find "$PREFIX/lib/python$PY_XY/lib-dynload" \
     \( -name "_test*.so" -o -name "_xxtestfuzz*.so" -o -name "xxlimited*.so" \) \
     -delete 2>/dev/null || true
find "$PREFIX" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
# (4b) Ungenutzte Tcl-Erweiterungen + SQLite. Das Programm ist datenbankfrei
#      (CLAUDE.md) und nutzt weder [incr Tcl], tdbc, das Thread-Paket noch sqlite —
#      die kommen nur aus dem "batteries-included" Tcl-9-Quellbaum bzw. der
#      Standardbibliothek mit. Entfernen spart Platz UND Attributionsflaeche
#      (nur noch tatsaechlich genutzte Komponenten wandern mit, s. THIRD_PARTY_LICENSES.md).
#      Expat (XML, ueber Pythons xml.etree) bleibt — das wird gebraucht.
rm -rf "$PREFIX/lib/"itcl* "$PREFIX/lib/"tdbc* "$PREFIX/lib/"thread* \
       "$PREFIX/lib/"sqlite3.* 2>/dev/null || true
rm -rf "$PREFIX/lib/python$PY_XY/sqlite3" \
       "$PREFIX/lib/python$PY_XY/lib-dynload/"_sqlite3*.so 2>/dev/null || true

# (5) Debug-Symbole aus allen mitgelieferten Binaerdateien strippen (.so + python).
#     --strip-unneeded ist fuer shared libs sicher (behaelt exportierte Symbole).
#     ABER: Tcl/Tk 9 haengen ihre Script-Library (init.tcl usw.) per zipfs hinter
#     die .so an. strip verwirft diese Trailing-Daten -> "cannot find init.tcl".
#     Daher libtcl*/libtk* zwingend auslassen.
if command -v strip >/dev/null 2>&1; then
    find "$PREFIX" -type f \( -name "*.so" -o -name "*.so.*" \) \
        -not -name "libtcl*" -not -name "libtk*" \
        -exec strip --strip-unneeded {} + 2>/dev/null || true
    strip "$PREFIX/bin/python$PY_VER" 2>/dev/null || true
fi
_after=$(du -sm "$PREFIX" | cut -f1)
echo ">> usr/ verschlankt: ${_before} MB -> ${_after} MB"

# --------------------------------------------------------------- 8. AppImage packen
echo "==== AppImage packen ===="
AIT="$BUILD/appimagetool-x86_64.AppImage"
dl "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" "$AIT"
chmod +x "$AIT"

[ "${1:-}" = "--bump" ] && python3 "$ROOT/bump_version.py" >/dev/null
VERSION="$(python3 "$ROOT/bump_version.py" --print)"
OUT="$ROOT/$APP-${VERSION}-x86_64.AppImage"
# zstd auf hoher Stufe: nahe an xz, aber schnelleres Entpacken beim Start.
ARCH=x86_64 "$AIT" --appimage-extract-and-run \
    --comp zstd --mksquashfs-opt -Xcompression-level --mksquashfs-opt 19 \
    "$APPDIR" "$OUT" 2>&1 | tail -5

# Gear Lever (Forgejo-Updater) erkennt Updates an der DATEIGROESSE des Assets, nicht an
# der Versionsnummer. Zwei Builds koennen sich zufaellig identisch gross komprimieren
# -> dann bietet Gear Lever kein Update an (real passiert: 26.08.08b1 und b2 waren
# byte-genau gleich gross). Der fertigen AppImage daher einen harmlosen Trailer mit
# BUILD-ABHAENGIGER Laenge anhaengen: der squashfs-Superblock deklariert seine eigene
# Laenge, Trailing-Bytes ignoriert das AppImage-Runtime (an echter Hardware verifiziert,
# laeuft + --appimage-extract funktioniert weiter). Damit ist die Groesse je Build
# praktisch eindeutig.
NS="$(date +%s%N)"
printf '\n# KKM %s build %s\n' "$VERSION" "$NS" >> "$OUT"
head -c "$(( NS % 65536 + 4096 ))" /dev/zero >> "$OUT"

ln -sfn "$(basename "$OUT")" "$ROOT/$APP-x86_64.AppImage"

echo ">> Fertig: $OUT"
