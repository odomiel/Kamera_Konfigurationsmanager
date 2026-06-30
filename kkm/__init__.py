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

"""Kamera_Konfigurationsmanager — plugin-based multi-vendor camera config manager.

Top-level package. The application is structured in three layers:

- ``kkm.core``    — vendor-agnostic core (group store, password vault, plugin API).
- ``kkm.plugins`` — vendor plugins. Currently only ``axis`` (wraps a copied,
                    independently maintained VAPIX layer from the Discovery tool).
- ``kkm.gui``     — the Tkinter front-end (group tree + device table + action toolbar).
"""

from .version import __version__, APP_NAME

__all__ = ["__version__", "APP_NAME"]
