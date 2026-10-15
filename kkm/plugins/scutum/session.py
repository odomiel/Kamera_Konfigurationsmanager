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

"""Minimal stdlib-only probe for the Scutum/Inform Netcon 3 I/O module.

The Netcon 3 is an **I/O module** with 8 additional serial interfaces (Scutum/Inform) —
not a camera and with no web UI. Verified on a real unit (192.168.0.236): **no web UI,
no SNMP, no mDNS/WS-Discovery** — the only open TCP port is **22 (SSH, OpenSSH 6.7)**,
and the SSH banner is generic (any Debian-8 host looks the same).

The single manufacturer-specific marker reachable **without a login** is the device's
DHCP hostname ``netcon3-<id>`` (e.g. ``netcon3-1436520562``), visible via reverse DNS
where the network registers DHCP client names. That is what identifies the unit here;
``<id>`` doubles as a stable per-device identity. There is intentionally **no login**
attempt (never guess passwords — lockout risk), so the plugin only *shows* the device —
configuration needs the installer's SSH credentials and vendor documentation, which are
not publicly available.
"""

from __future__ import annotations

import re
import socket

#: Der einzige offene Dienst des Geraets (SSH). Zugleich der Online-Pruefpunkt.
PORT = 22

#: Marker im (DHCP-/Reverse-DNS-)Hostnamen, z. B. ``netcon3-1436520562``.
_NETCON = re.compile(r"netcon\s*([0-9]+)?[-_]?([0-9a-f]+)?", re.I)


def erreichbar(ip: str, timeout: float = 0.4) -> bool:
    """Lebenszeichen: laesst sich der SSH-Port (22) oeffnen?"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, PORT)) == 0
    except OSError:
        return False
    finally:
        s.close()


def ssh_banner(ip: str, timeout: float = 3.0) -> str:
    """Liest die SSH-Kennung (``SSH-2.0-…``). Nur Lesen, keine Anmeldung. Leer bei
    Fehler/kein SSH."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, PORT))
        zeile = s.recv(256).decode("latin1", "replace").strip()
        return zeile if zeile.startswith("SSH-") else ""
    except OSError:
        return ""
    finally:
        s.close()


def _reverse_dns(ip: str, timeout: float = 2.0) -> str:
    """Reverse-DNS-Name (PTR) der IP, Kurzform ohne Domain; leer bei keinem PTR."""
    alt = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        name = socket.gethostbyaddr(ip)[0]
    except OSError:
        return ""
    finally:
        socket.setdefaulttimeout(alt)
    return name.split(".")[0]


def kennung(ip: str, timeout: float = 4.0) -> dict | None:
    """Erkennt eine Netcon ohne Login. Grundlage ist der **Hostname** (``netcon…``)
    aus Reverse-DNS; der offene SSH-Port dient als Lebenszeichen/Plausibilitaet.

    Liefert ``{name, modell, serial, ssh}`` bei einem Treffer, sonst ``None`` — nur
    Geraete, deren Reverse-DNS-Name den ``netcon``-Marker traegt, werden gelistet
    (konservativ, keine Fehltreffer auf beliebige SSH-Hosts)."""
    if not erreichbar(ip, min(timeout, 1.5)):
        return None
    host = _reverse_dns(ip, min(timeout, 2.0))
    if not host:
        return None
    treffer = _NETCON.match(host)
    if not treffer:
        return None
    nummer = treffer.group(1) or ""          # Modellnummer, z. B. "3"
    serial = treffer.group(2) or ""          # Geraete-ID aus dem Default-Hostnamen
    banner = ssh_banner(ip, min(timeout, 3.0))
    return {
        "name": host,
        "modell": f"Netcon {nummer}".strip() if nummer else "Netcon",
        "serial": serial,
        "ssh": banner,
    }
