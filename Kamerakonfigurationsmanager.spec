# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller-Spec fuer den Kamera_Konfigurationsmanager (Windows-.exe).
# Erzeugt ein eigenstaendiges One-File-Programm in dist\:
#   Kamerakonfigurationsmanager_<Version>.exe   - GUI (ohne Konsolenfenster)
#
# Bauen (auf Windows):  pyinstaller --noconfirm Kamerakonfigurationsmanager.spec
#
# Funktionsgleich zur Linux-Version: dasselbe kkm-Paket wird gebuendelt. Unter
# Linux wird stattdessen das AppImage via build_appimage.sh erzeugt — der Name
# traegt dort ebenso die Version ($APP-$VERSION-x86_64.AppImage).

import os
import re
import sys
import glob
import zipfile
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
    ("HILFE_EN.md", "."),
    ("LICENSE", "."),
    ("THIRD_PARTY_LICENSES.md", "."),
]
# sv_ttk liefert seine Tcl-Theme-Dateien als Paketdaten -> mitnehmen.
datas += collect_data_files("sv_ttk")

# WORKAROUND: Der Windows-Installer von Python 3.14 buendelt Tcl/Tk 9 nicht mehr
# als lose Dateien, sondern in zwei ZIPs (<PythonRoot>\tcl\libtcl9.x.zip /
# libtk9.x.zip), die Tcl zur Laufzeit ueber sein eingebautes zipfs moundet
# (tcl_data_dir sieht dann aus wie "//zipfs:/lib/tcl/tcl_library"). PyInstallers
# Tcl/Tk-Sammellogik (PyInstaller.utils.hooks.tcl_tk) prueft nur mit os.path.isdir()
# auf dem echten Dateisystem -> das schlaegt fuer zipfs-Pfade fehl und es werden
# 0 Dateien eingesammelt. Die .exe startet dann zwar, stirbt aber sofort mit
# "FileNotFoundError: Tcl data directory ..._tcl_data not found", weil der
# Runtime-Hook (pyi_rth__tkinter.py) diese Ordner zwingend voraussetzt.
# Fix: die beiden ZIPs hier selbst entpacken und als datas mit genau den
# Zielordnernamen einspeisen, die der Runtime-Hook erwartet (_tcl_data/_tk_data,
# siehe TclTkInfo.TCL_ROOTNAME/TK_ROOTNAME in PyInstaller.utils.hooks.tcl_tk).
try:
    from PyInstaller.utils.hooks.tcl_tk import tcltk_info
except ImportError:
    tcltk_info = None

if tcltk_info is not None and tcltk_info.available and str(tcltk_info.tcl_data_dir).startswith("//zipfs:"):
    _tcl_zip_dir = os.path.join(sys.base_prefix, "tcl")
    _extract_dir = os.path.join(_root, "build", "tcl9_zipfs_extracted")

    def _extract_lib_zip(pattern, top_name):
        matches = sorted(glob.glob(os.path.join(_tcl_zip_dir, pattern)))
        if not matches:
            return None
        dest = os.path.join(_extract_dir, top_name)
        with zipfile.ZipFile(matches[0]) as zf:
            zf.extractall(dest)
        return os.path.join(dest, top_name)

    def _tree_datas(src_root, dest_prefix):
        entries = []
        for dirpath, _dirnames, filenames in os.walk(src_root):
            rel = os.path.relpath(dirpath, src_root)
            dest_dir = dest_prefix if rel == "." else os.path.join(dest_prefix, rel)
            for fn in filenames:
                entries.append((os.path.join(dirpath, fn), dest_dir))
        return entries

    _tcl_src = _extract_lib_zip("libtcl9*.zip", "tcl_library")
    _tk_src = _extract_lib_zip("libtk9*.zip", "tk_library")

    if _tcl_src and os.path.isdir(_tcl_src):
        datas += _tree_datas(_tcl_src, tcltk_info.TCL_ROOTNAME)
    if _tk_src and os.path.isdir(_tk_src):
        datas += _tree_datas(_tk_src, tcltk_info.TK_ROOTNAME)

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
    name=f"Kamerakonfigurationsmanager_{VERSION}",
    console=False,
    icon=icon,
    upx=False,
    bootloader_ignore_signals=False,
    debug=False,
    strip=False,
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
)
