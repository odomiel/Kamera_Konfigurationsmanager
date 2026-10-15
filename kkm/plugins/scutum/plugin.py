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

"""Scutum/Inform Netcon I/O-module plugin (display only).

The Netcon 3 is an I/O module with 8 additional serial interfaces (Scutum/Inform), not a
camera. Verified on a real unit: it exposes only SSH (port 22, OpenSSH 6.7) — no web UI,
no SNMP, no mDNS/WS-Discovery — so there is no unauthenticated vendor fingerprint beyond
its DHCP hostname ``netcon…`` (seen via reverse DNS). This plugin therefore only makes
the device *appear* in the list: ``DISCOVER`` (subnet scan + reverse-DNS marker),
``ONLINE_CHECK`` (TCP 22) and ``DEVICE_INFO`` (model/serial from the hostname). There is
**no** configuration path — that needs the installer's SSH credentials and vendor
documentation, which are not publicly available; the plugin never attempts a login
(never guess passwords — lockout risk). ``experimental``, shipped off by default. A unit
can also be added by hand (IP + manufacturer) via the search split menu.
"""

from __future__ import annotations

from kkm.core.camera import get_first_ip
from kkm.core.plugins import VendorPlugin, Credentials, Capability
from . import discovery
from . import session


class ScutumPlugin(VendorPlugin):
    id = "scutum"
    name = "Scutum/Inform Netcon"
    #: I/O-Modul (8 serielle Schnittstellen), nur Anzeige; keine Konfig-Schnittstelle.
    experimental = True
    #: Das Netcon kennt keine (vom Programm nutzbaren) Zugangsdaten — die Suche soll
    #: daher nicht nach Benutzer/Passwort fragen.
    uses_credentials = False
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
        # Offener SSH-Port als Lebenszeichen (kein Loginversuch).
        try:
            return session.erreichbar(ip, timeout=2.0)
        except Exception:  # noqa: BLE001 - offline ist kein Fehlerfall
            return False

    def device_info(self, camera: dict, creds: Credentials | None = None) -> dict:
        """Modell + MAC/Seriennummer aus der (unauthentifizierten) Kennung: die MAC
        kommt per ARP (im selben Subnetz), ersatzweise die Geräte-ID aus dem Hostnamen.
        Eine Firmware-/Softwarefassung ist ohne Login nicht ermittelbar (SSH-Version
        ist nicht die Gerätefirmware) und bleibt daher leer."""
        ip = get_first_ip(camera)
        if not ip:
            return {}
        info = session.kennung(ip, timeout=6) or {}
        ergebnis = {"model": info.get("modell", "") or "Netcon"}
        kennzeichen = info.get("mac") or info.get("serial")
        if kennzeichen:
            ergebnis["mac"] = kennzeichen
        return ergebnis
