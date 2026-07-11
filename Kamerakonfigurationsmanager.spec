# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller-Spec fuer den Kamera_Konfigurationsmanager (Windows-.exe).
# Erzeugt ein eigenstaendiges One-File-Programm in dist\:
#   Kamerakonfigurationsmanager-<Version>.exe   - GUI (ohne Konsolenfenster)
#
# Bauen (auf Windows):  pyinstaller --noconfirm Kamerakonfigurationsmanager.spec
#
# Funktionsgleich zur Linux-Version: dasselbe kkm-Paket wird gebuendelt. Unter
# Linux wird stattdessen das AppImage via build_appimage.sh erzeugt — der Name
# traegt dort ebenso die Version ($APP-$VERSION-x86_64.AppImage).

import os
import re
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Version aus kkm/version.py lesen (einzige Quelle der Wahrheit) — per Regex statt
# per Import, damit die Spec nicht vom Suchpfad des bauenden Interpreters abhaengt.
# SPECPATH setzt PyInstaller auf das Verzeichnis dieser Datei; damit stimmt der Pfad
# auch, wenn aus einem anderen Arbeitsverzeichnis heraus gebaut wird.
_root = globals().get("SPECPATH", os.path.dirname(os.path.abspath("__file__")))
with open(os.path.join(_root, "kkm", "version.py"), encoding="utf-8") as fh:
    _m = re.search(r'__version__\s*=\s*"([^"]+)"', fh.read())
VERSION = _m.group(1) if _m else "0"

# README/Lizenzen mit ins Bundle (zur Laufzeit ueber sys._MEIPASS auffindbar).
datas = [
    ("README.md", "."),
    ("HILFE.md", "."),
    ("LICENSE", "."),
    ("THIRD_PARTY_LICENSES.md", "."),
]
# sv_ttk liefert seine Tcl-Theme-Dateien als Paketdaten -> mitnehmen.
datas += collect_data_files("sv_ttk")

# zeroconf/ifaddr laden Teile dynamisch; cryptography hat C-/Rust-Submodule ->
# explizit einsammeln.
hiddenimports = (collect_submodules("zeroconf")
                 + collect_submodules("ifaddr")
                 + collect_submodules("cryptography")
                 + collect_submodules("sv_ttk"))

# Eigenes Paket einsammeln, falls noch nicht installiert/auf dem Pfad.
hiddenimports += collect_submodules("kkm")

ICON = "assets/Kamerakonfigurationsmanager.ico"
icon = ICON if os.path.exists(ICON) else None

block_cipher = None

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name=f"Kamerakonfigurationsmanager-{VERSION}",
    console=False,
    icon=icon,
    upx=False,
    bootloader_ignore_signals=False,
    debug=False,
    strip=False,
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
)
