# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller-Spec fuer den Kamera_Konfigurationsmanager (Windows-.exe).
# Erzeugt ein eigenstaendiges One-File-Programm in dist\:
#   Kamerakonfigurationsmanager.exe   - GUI (ohne Konsolenfenster)
#
# Bauen (auf Windows):  pyinstaller --noconfirm Kamerakonfigurationsmanager.spec
#
# Funktionsgleich zur Linux-Version: dasselbe kkm-Paket wird gebuendelt. Unter
# Linux wird stattdessen das AppImage via build_appimage.sh erzeugt.

import os
from PyInstaller.utils.hooks import collect_submodules

# README/Lizenzen mit ins Bundle (zur Laufzeit ueber sys._MEIPASS auffindbar).
datas = [
    ("README.md", "."),
    ("HILFE.md", "."),
    ("LICENSE", "."),
    ("THIRD_PARTY_LICENSES.md", "."),
]

# zeroconf/ifaddr laden Teile dynamisch; cryptography hat C-/Rust-Submodule ->
# explizit einsammeln.
hiddenimports = (collect_submodules("zeroconf")
                 + collect_submodules("ifaddr")
                 + collect_submodules("cryptography"))

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
    name="Kamerakonfigurationsmanager",
    console=False,
    icon=icon,
    upx=False,
    bootloader_ignore_signals=False,
    debug=False,
    strip=False,
    runtime_tmpdir=None,
    disable_windowed_traceback=False,
)
