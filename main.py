#!/usr/bin/env python3
# Kamera_Konfigurationsmanager - Plugin-basierter Konfigurationsmanager fuer Netzwerkkameras.
# Copyright (C) 2026 Mirik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Entrypoint for the Kamera_Konfigurationsmanager GUI.

Run from source:   python3 main.py
Packaged later as a portable Windows .exe and a Linux AppImage (same toolchain as
the Axis_Kamera_Discovery tool).
"""

from kkm.gui import main

if __name__ == "__main__":
    main()
