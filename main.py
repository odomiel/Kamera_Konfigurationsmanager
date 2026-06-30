#!/usr/bin/env python3
"""Entrypoint for the Kamera_Konfigurationsmanager GUI.

Run from source:   python3 main.py
Packaged later as a portable Windows .exe and a Linux AppImage (same toolchain as
the Axis_Kamera_Discovery tool).
"""

from kkm.gui import main

if __name__ == "__main__":
    main()
