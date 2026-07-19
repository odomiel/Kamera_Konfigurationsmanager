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

"""SADP discovery — find Hikvision devices on the LAN (stdlib socket).

Hikvision's own tool ("SADP") locates devices with a SOAP-ish XML probe over UDP
multicast to ``239.255.255.250:37020``. Devices answer with an XML ``<ProbeMatch>``
carrying MAC, IPv4/IPv6, model (``deviceDescription``), serial and the activation
state — richer than the ONVIF WS-Discovery reply (which the generic ONVIF plugin
already covers), and, crucially, it reports the **MAC address**, so
:func:`kkm.core.camera_key` gets a stable identity.

**Experimental:** the probe/response shape is modelled on the reverse-engineered SADP
protocol; field names are matched by local tag (case-insensitive), so minor per-model
differences degrade to a partially filled camera dict rather than a miss.
"""

from __future__ import annotations

import socket
import time
import uuid
import xml.etree.ElementTree as ET

from kkm.core.camera import FIELD_NAMES  # noqa: F401  (Dict-Form dieses Moduls)

MCAST_ADDR = "239.255.255.250"
MCAST_PORT = 37020

# SADP-„inquiry": Uuid dient der Zuordnung Antwort<->Anfrage; Types=inquiry fragt
# alle Geraete ab.
_PROBE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    "<Probe><Uuid>{uuid}</Uuid><Types>inquiry</Types></Probe>"
)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(root, name: str) -> str:
    name = name.lower()
    for node in root.iter():
        if _local(node.tag) == name and node.text:
            return node.text.strip()
    return ""


def _parse_match(data: str) -> dict | None:
    """Eine SADP-ProbeMatch-Antwort -> Kamera-Dict (Form ``FIELD_NAMES``).

    Erfordert wenigstens eine IPv4-Adresse; ohne die ist das Geraet nicht
    ansprechbar (die Aktionen laufen ueber IPv4)."""
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return None
    if "inquiry" not in _text(root, "Types").lower() and _find_any(root) is False:
        # Kein SADP-Match (fremde Multicast-Antwort).
        return None
    ipv4 = _text(root, "IPv4Address")
    if not ipv4:
        return None
    mac = _text(root, "MAC").replace("-", ":").upper()
    model = _text(root, "DeviceDescription") or _text(root, "DeviceType")
    serial = _text(root, "DeviceSN")
    http_port = _text(root, "HttpPort") or "80"
    activated = _text(root, "Activated").lower()
    cam = {
        "Name": model or ipv4,
        "IP Adresse: Zeroconfig": "",
        "IP Adresse: Konfiguriert": ipv4,
        "IP Adresse: IPv6": _text(root, "IPv6Address"),
        "Port": int(http_port) if http_port.isdigit() else 80,
        "Hostname": _text(root, "DeviceName") or ipv4,
        # MAC als stabile Kennung; ersatzweise Seriennummer.
        "MAC-Adresse/Seriennummer": mac or serial,
        "_model": model,
        "_serial": serial,
    }
    if activated == "false":
        cam["_factory"] = True
    return cam


def _find_any(root) -> bool:
    """Heuristik: sieht die Antwort ueberhaupt nach SADP aus (hat sie ein
    typisches Feld)?"""
    for name in ("MAC", "IPv4Address", "DeviceDescription", "DeviceSN"):
        if _text(root, name):
            return True
    return False


def discover(timeout: int = 10) -> list[dict]:
    """Blockierender SADP-Probe. Liefert Kamera-Dicts (Schluessel = FIELD_NAMES).

    Antworten werden bis *timeout* gesammelt und ueber MAC (ersatzweise IP)
    entdoppelt — Geraete mit mehreren Interfaces antworten mehrfach."""
    probe = _PROBE.format(uuid=uuid.uuid4()).encode("utf-8")
    found: dict[str, dict] = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(1.0)
        sock.bind(("", 0))
        sock.sendto(probe, (MCAST_ADDR, MCAST_PORT))

        end = time.time() + max(1, timeout)
        while time.time() < end:
            try:
                raw, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            cam = _parse_match(raw.decode("utf-8", errors="replace"))
            if cam:
                key = cam["MAC-Adresse/Seriennummer"] or cam["IP Adresse: Konfiguriert"]
                found.setdefault(key, cam)
    finally:
        sock.close()
    return list(found.values())
