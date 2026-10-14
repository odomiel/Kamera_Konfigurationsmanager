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

"""Discovery for Senstar Thin Clients — a light unicast subnet scan.

The Thin Client advertises **no** camera-discovery protocol (no WS-Discovery/mDNS as an
ONVIF device — verified on hardware). So discovery is a scan of the local ``/24``(s):
a fast TCP pre-filter on the HTTPS port, then an unauthenticated 404-page fingerprint
(``session.kennung``) to confirm it is a Thin Client and read model + version. No login
attempts are made against any host. Because the plugin is experimental and off by
default, only users who enable it pay the scan cost; a device may alternatively be
added by hand (IP + manufacturer) via the search button's split menu.
"""

from __future__ import annotations

import socket
from concurrent.futures import ThreadPoolExecutor

from kkm.core.camera import FIELD_NAMES
from . import session


def _lokale_ipv4s() -> list[str]:
    """Best-effort Liste lokaler IPv4-Adressen (stdlib-only); Loopback ausgelassen."""
    ips: set[str] = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 9))      # TEST-NET-1, nicht routbar; sendet nichts
            ips.add(s.getsockname()[0])
        finally:
            s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    return [ip for ip in ips if not ip.startswith("127.")]


def _zielhosts(eigene: list[str]) -> list[str]:
    """Alle Host-Adressen der /24-Netze der eigenen IPv4s (ohne .0/.255 und sich selbst)."""
    ziele: list[str] = []
    gesehen: set[str] = set()
    eigene_set = set(eigene)
    for ip in eigene:
        teile = ip.split(".")
        if len(teile) != 4:
            continue
        praefix = ".".join(teile[:3])
        if praefix in gesehen:
            continue
        gesehen.add(praefix)
        for n in range(1, 255):
            ziel = f"{praefix}.{n}"
            if ziel not in eigene_set:
                ziele.append(ziel)
    return ziele


def _cam(ip: str, info: dict) -> dict:
    cam = {name: "" for name in FIELD_NAMES}
    cam["Name"] = info.get("name") or f"Senstar Thin Client ({ip})"
    cam["IP Adresse: Konfiguriert"] = ip
    cam["Port"] = str(session.PORT)
    cam["_vendor"] = "senstar"
    cam["_model"] = info.get("modell") or "Thin Client"
    if info.get("version"):
        cam["_firmware"] = info["version"]
    cam["_online"] = True
    return cam


def suche(timeout: int = 10) -> list[dict]:
    """Scannt die lokalen /24-Netze nach Senstar Thin Clients.

    Zweistufig: erst ein schneller TCP-Vortest auf Port 443, dann der 404-Fingerprint
    nur auf offenen Hosts. Rein lesend, keine Loginversuche. Gibt bei Netzfehlern eine
    (ggf. leere) Liste zurueck, wirft nie.
    """
    ziele = _zielhosts(_lokale_ipv4s())
    if not ziele:
        return []
    # Kurze Einzel-Timeouts, damit der ganze Scan im Suchzeitfenster bleibt.
    tcp_timeout = 0.4
    http_timeout = min(max(timeout, 3), 8)
    treffer: list[dict] = []

    def pruefe(ip: str):
        if not session.erreichbar(ip, tcp_timeout):
            return None
        info = session.kennung(ip, http_timeout)
        return (ip, info) if info else None

    try:
        with ThreadPoolExecutor(max_workers=64) as ex:
            for erg in ex.map(pruefe, ziele):
                if erg:
                    ip, info = erg
                    treffer.append(_cam(ip, info))
    except Exception:  # noqa: BLE001 - Scan darf die Suche nie sprengen
        return treffer
    return treffer
