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

"""Senstar (Aimetis) Thin Client plugin — Stufe 1: discovery + display only.

The Thin Client (e.g. A10D) is a network **video decoder**, not a camera: it receives
ONVIF Profile S / RTSP streams and shows them on a monitor. It is therefore *not* an
ONVIF **server** — the generic ONVIF plugin cannot see or manage it (verified on
hardware: WS-Discovery does not find it, ``/onvif/device_service`` serves only the web
UI). This dedicated plugin makes it appear in the device list with model and software
version, discovered by a light subnet scan (see ``discovery``) or added by hand.

**Stufe 1 is read-only (display).** It offers ``DISCOVER`` / ``ONLINE_CHECK`` /
``DEVICE_INFO`` via the device's unauthenticated 404-page fingerprint — no login. The
writing capabilities the 3.10 REST API would allow (``SET_IP`` via ``POST /Settings``,
``USERS`` via ``/User``, ``FIRMWARE``/``FIRMWARE_CHECK`` via ``/System/Update``,
``FACTORY_RESET`` via ``/System/Restore``, token login via ``POST /Session``) are
mapped but deliberately left for Stufe 2, once verified against a device with
credentials. The plugin is ``experimental`` and shipped off by default.
"""

from __future__ import annotations

from kkm.core.camera import get_first_ip
from kkm.core.plugins import VendorPlugin, Credentials, Capability
from . import discovery
from . import session


class SenstarPlugin(VendorPlugin):
    id = "senstar"
    name = "Senstar Thin Client"
    #: Decoder, keine Kamera; noch nicht schreibend an Hardware verifiziert -> ab Werk aus.
    experimental = True
    default_username = "admin"
    capabilities = {
        Capability.DISCOVER,
        Capability.ONLINE_CHECK,
        Capability.DEVICE_INFO,
    }

    # --- discovery & status -------------------------------------------------
    def discover(self, timeout: int = 10) -> list[dict]:
        cams = discovery.suche(timeout=timeout)
        for cam in cams:
            cam["_vendor"] = self.id
        return cams

    def check_online(self, camera: dict, creds: Credentials | None = None) -> bool:
        ip = get_first_ip(camera)
        if not ip:
            return False
        # Unauthentifizierter Fingerprint als Lebenszeichen (kein Loginversuch).
        try:
            return session.kennung(ip, timeout=5) is not None
        except Exception:  # noqa: BLE001 - offline ist kein Fehlerfall
            return False

    def device_info(self, camera: dict, creds: Credentials) -> dict:
        """Modell + Softwarefassung — unauthentifiziert aus der 404-Kennung.

        Braucht (in Stufe 1) keine Zugangsdaten; ``creds`` bleibt ungenutzt."""
        ip = get_first_ip(camera)
        info = session.kennung(ip, timeout=6) if ip else None
        if not info:
            return {}
        return {"model": info.get("modell", ""), "firmware": info.get("version", "")}
