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

"""WS-Discovery — find ONVIF devices on the LAN (stdlib socket, no zeroconf).

ONVIF devices answer a SOAP-over-UDP ``Probe`` sent to the multicast group
239.255.255.250:3702. The reply carries the device service address (``XAddrs``) and
``Scopes`` — free-form URIs from which name, hardware and location can be read.

What it does *not* carry is a MAC address, so the device's endpoint UUID (stable per
device, that is its purpose) serves as the identity that :func:`kkm.core.camera_key`
keys off.
"""

from __future__ import annotations

import re
import socket
import time
import uuid
from urllib.parse import urlparse

from kkm.core.camera import FIELD_NAMES  # noqa: F401  (Dict-Form dieses Moduls)

MCAST_ADDR = "239.255.255.250"
MCAST_PORT = 3702

_PROBE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"'
    ' xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
    ' xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"'
    ' xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
    "<e:Header>"
    "<w:MessageID>uuid:{msg_id}</w:MessageID>"
    "<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>"
    "<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>"
    "</e:Header>"
    "<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>"
    "</e:Envelope>"
)

_XADDRS_RE = re.compile(r"<[^>]*XAddrs[^>]*>([^<]+)<", re.IGNORECASE)
_SCOPES_RE = re.compile(r"<[^>]*Scopes[^>]*>([^<]+)<", re.IGNORECASE)
_TYPES_RE = re.compile(r"<[^>]*Types[^>]*>([^<]+)<", re.IGNORECASE)
_UUID_RE = re.compile(r"<[^>]*Address[^>]*>\s*(urn:uuid:[^<\s]+|uuid:[^<\s]+)\s*<",
                      re.IGNORECASE)


def _scope(scopes: str, key: str) -> str:
    """Wert eines ONVIF-Scopes, z. B. ``onvif://www.onvif.org/name/Halle-Nord``."""
    for scope in scopes.split():
        marker = f"/{key}/"
        if marker in scope:
            value = scope.split(marker, 1)[1].strip("/")
            return value.replace("%20", " ").replace("+", " ")
    return ""


def _parse_match(data: str) -> dict | None:
    """Eine ProbeMatch-Antwort -> Kamera-Dict in der Form von ``FIELD_NAMES``.

    Liefert None fuer alles, was keine ONVIF-Kamera ist: Auf einen WS-Discovery-Probe
    antworten naemlich auch Windows-Rechner und Drucker (WSD, Port 5357) — die
    Typ-Angabe wird deshalb geprueft, statt jeder Antwort zu glauben.
    """
    xaddrs = _XADDRS_RE.search(data)
    if not xaddrs:
        return None
    # Mehrere XAddrs (IPv4/IPv6, mehrere Interfaces) -> erste http(s)-Adresse nehmen.
    url = next((x for x in xaddrs.group(1).split() if x.startswith("http")), "")
    if not url:
        return None
    types = _TYPES_RE.search(data)
    types = types.group(1) if types else ""
    if "NetworkVideoTransmitter" not in types and "/onvif/" not in url.lower():
        return None
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if ":" in host:            # IPv6 — die Anwendung arbeitet mit IPv4
        return None

    scopes = _SCOPES_RE.search(data)
    scopes = scopes.group(1) if scopes else ""
    name = _scope(scopes, "name") or _scope(scopes, "hardware") or host
    epr = _UUID_RE.search(data)
    ident = epr.group(1).rsplit(":", 1)[-1] if epr else ""

    return {
        "Name": name,
        "IP Adresse: Zeroconfig": "",
        "IP Adresse: Konfiguriert": host,
        "Port": parsed.port or (443 if parsed.scheme == "https" else 80),
        "Hostname": host,
        # WS-Discovery meldet keine MAC — die Geraete-UUID ist die stabile Kennung.
        "MAC-Adresse/Seriennummer": ident,
        "_onvif_xaddr": url,
        "_model": _scope(scopes, "hardware"),
        "_location": _scope(scopes, "location"),
    }


def discover(timeout: int = 10) -> list[dict]:
    """Blockierender WS-Discovery-Probe. Liefert Kamera-Dicts (Schluessel = FIELD_NAMES).

    Antworten werden bis *timeout* gesammelt und ueber die Geraete-UUID (ersatzweise
    die IP) entdoppelt — Geraete mit mehreren Netzwerkkarten antworten mehrfach.
    """
    probe = _PROBE.format(msg_id=uuid.uuid4()).encode("utf-8")
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
                data, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            cam = _parse_match(data.decode("utf-8", errors="replace"))
            if cam:
                key = cam["MAC-Adresse/Seriennummer"] or cam["IP Adresse: Konfiguriert"]
                found.setdefault(key, cam)
    finally:
        sock.close()
    return list(found.values())
