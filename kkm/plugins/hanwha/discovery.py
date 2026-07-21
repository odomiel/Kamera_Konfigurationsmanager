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

"""Hanwha discovery — reuses ONVIF WS-Discovery, filtered to Hanwha devices.

Hanwha has no openly documented vendor discovery protocol (unlike Hikvision SADP or
Dahua DHIP); Wisenet cameras announce themselves via **ONVIF WS-Discovery**, which the
shared :mod:`kkm.plugins.onvif.discovery` already speaks. This module runs that probe
and keeps only devices whose ONVIF ``manufacturer`` scope names Hanwha (or the legacy
"Samsung Techwin"), so the Hanwha plugin does not claim Axis/Hikvision/other ONVIF
devices.

WS-Discovery carries no MAC (only the device UUID), so the camera dict initially keys
off the UUID; the plugin backfills the real MAC from SUNAPI ``deviceinfo`` once
credentials are known (``device_info``), and the main window re-keys it.
"""

from __future__ import annotations

from kkm.plugins.onvif import discovery as onvif_discovery

#: ONVIF-``manufacturer``-Scopes, die als Hanwha/Wisenet gelten (Kleinschreibung).
_HANWHA_MARKERS = ("hanwha", "wisenet", "samsung techwin")


def _is_hanwha(cam: dict) -> bool:
    manu = (cam.get("_manufacturer") or "").lower()
    model = (cam.get("_model") or "").lower()
    name = (cam.get("Name") or "").lower()
    if any(m in manu for m in _HANWHA_MARKERS):
        return True
    # Rueckfall: viele Wisenet-Modellcodes (QNO/PNO/XNO/QND/…) sind eindeutig, falls
    # der manufacturer-Scope einmal fehlt.
    return any(hit.startswith(("qn", "pn", "xn", "qs", "ln", "hcp", "tnu"))
               for hit in (model, name))


def discover(timeout: int = 10) -> list[dict]:
    """WS-Discovery, auf Hanwha-/Wisenet-Geraete gefiltert."""
    return [cam for cam in onvif_discovery.discover(timeout=timeout) if _is_hanwha(cam)]
