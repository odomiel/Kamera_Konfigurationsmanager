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

"""Discovery for Scutum/Inform Netcon alarm transmitters — a light unicast subnet scan.

The Netcon advertises **no** discovery protocol (no mDNS/WS-Discovery — verified on
hardware), so discovery scans the local ``/24``(s): a fast TCP pre-filter on the SSH
port, then :func:`session.kennung`, which confirms the unit by its reverse-DNS hostname
(``netcon…``). No login is attempted against any host. This only finds devices in
networks that register the DHCP client name in DNS; everywhere else the unit is added by
hand (IP + manufacturer) via the search button's split menu.
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
    cam["Name"] = info.get("name") or f"Scutum Netcon ({ip})"
    cam["IP Adresse: Konfiguriert"] = ip
    cam["Port"] = str(session.PORT)
    cam["_vendor"] = "scutum"
    cam["_model"] = info.get("modell") or "Netcon"
    # Die Geraete-ID aus dem Default-Hostnamen ist eine stabile Identitaet
    # (ueberlebt einen IP-Wechsel), daher als Seriennummer fuehren.
    if info.get("serial"):
        cam["MAC-Adresse/Seriennummer"] = info["serial"]
    cam["_online"] = True
    return cam


def suche(timeout: int = 10) -> list[dict]:
    """Scannt die lokalen /24-Netze nach Scutum/Inform Netcon-Geraeten.

    Zweistufig: erst ein schneller TCP-Vortest auf Port 22, dann die
    Reverse-DNS-Kennung nur auf offenen Hosts. Rein lesend, keine Loginversuche. Gibt
    bei Netzfehlern eine (ggf. leere) Liste zurueck, wirft nie.
    """
    ziele = _zielhosts(_lokale_ipv4s())
    if not ziele:
        return []
    tcp_timeout = 0.4
    dns_timeout = min(max(timeout, 3), 8)
    treffer: list[dict] = []

    def pruefe(ip: str):
        if not session.erreichbar(ip, tcp_timeout):
            return None
        info = session.kennung(ip, dns_timeout)
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
