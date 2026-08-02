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

"""Dahua discovery — find Dahua devices on the LAN (stdlib socket).

Dahua's own tool (ConfigTool) locates devices with a **DHIP** probe over UDP to
``239.255.255.255:37810``: a 32-byte binary header followed by a JSON body
(``{"method":"DHDiscover.search",...}``). Devices answer with the same 32-byte header
plus a JSON ``deviceInfo`` carrying IPv4, **MAC**, model (``DeviceType``), serial and
firmware — richer than ONVIF WS-Discovery and, crucially, with the MAC, so
:func:`kkm.core.camera_key` gets a stable identity.

**Experimental:** the DHIP framing and field names are modelled on the
reverse-engineered protocol. Parsing is defensive — the JSON body is located by its
first ``{`` (header length varies slightly across firmware) and fields are read
case-insensitively, so per-model differences degrade to a partially filled camera
dict rather than a miss.
"""

from __future__ import annotations

import json
import socket
import time

# Die hier erzeugten Kamera-Dicts folgen der Form von ``kkm.core.camera.FIELD_NAMES``.

MCAST_ADDR = "239.255.255.255"
BROADCAST = "255.255.255.255"
PORT = 37810

# DHIP-Suchanfrage (JSON). uni=1 = auch Unicast-Antwort erlauben.
_PROBE_JSON = b'{"method":"DHDiscover.search","params":{"mac":"","uni":1}}'


def _dhip_packet(payload: bytes) -> bytes:
    """32-Byte-DHIP-Header + JSON-Payload.

    Header (little-endian): [0:4]=Headerlaenge 0x20, [4:8]='DHIP', [8:16]=Session/ID
    (0 bei der Suche), [16:20]+[24:28]=Payloadlaenge, Rest 0."""
    n = len(payload)
    header = (b"\x20\x00\x00\x00" + b"DHIP"
              + b"\x00" * 8
              + n.to_bytes(4, "little") + b"\x00\x00\x00\x00"
              + n.to_bytes(4, "little") + b"\x00\x00\x00\x00")
    return header + payload


def _json_body(raw: bytes) -> dict | None:
    """JSON-Body aus einer (ggf. DHIP-umrahmten) Antwort ziehen.

    Der Header ist je nach Firmware unterschiedlich lang -> am ersten ``{`` ansetzen
    statt eine feste Laenge abzuschneiden."""
    start = raw.find(b"{")
    if start < 0:
        return None
    try:
        return json.loads(raw[start:].decode("utf-8", errors="replace"))
    except ValueError:
        return None


def _ci_get(d: dict, *names: str):
    """Wert eines Schluessels case-insensitiv (Dahua wechselt die Schreibweise)."""
    lower = {k.lower(): v for k, v in d.items()} if isinstance(d, dict) else {}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _parse_device(body: dict) -> dict | None:
    """DHIP-Antwort -> Kamera-Dict (Form ``FIELD_NAMES``). Erfordert eine IPv4."""
    params = _ci_get(body, "params") or {}
    info = _ci_get(params, "deviceInfo") or _ci_get(body, "deviceInfo") or params
    if not isinstance(info, dict):
        return None

    ipv4 = _ci_get(info, "IPv4Address")
    if isinstance(ipv4, dict):
        ip = _ci_get(ipv4, "IPAddress") or ""
    else:
        ip = ipv4 or _ci_get(info, "IPAddress") or ""
    if not ip:
        return None

    mac = (_ci_get(info, "mac", "MAC", "MACAddress") or "").replace("-", ":").upper()
    model = _ci_get(info, "DeviceType", "deviceType", "machineName") or ""
    serial = _ci_get(info, "SerialNo", "serialNo") or ""
    http_port = _ci_get(info, "HttpPort", "httpPort") or 80
    try:
        http_port = int(http_port)
    except (TypeError, ValueError):
        http_port = 80
    version = _ci_get(info, "Version", "version", "SoftwareVersion") or ""

    cam = {
        "Name": str(model) or str(ip),
        "IP Adresse: Zeroconfig": "",
        "IP Adresse: Konfiguriert": str(ip),
        "IP Adresse: IPv6": str(_ci_get(info, "IPv6Address") or ""),
        "Port": http_port,
        "Hostname": str(_ci_get(info, "machineName", "DeviceName") or ip),
        # MAC als stabile Kennung; ersatzweise Seriennummer.
        "MAC-Adresse/Seriennummer": mac or str(serial),
        "_model": str(model),
        "_serial": str(serial),
        "_firmware": str(version),
    }
    return cam


def discover(timeout: int = 10) -> list[dict]:
    """Blockierender DHIP-Probe. Liefert Kamera-Dicts (Schluessel = FIELD_NAMES).

    Antworten werden bis *timeout* gesammelt und ueber MAC (ersatzweise IP)
    entdoppelt — Geraete mit mehreren Interfaces antworten mehrfach."""
    packet = _dhip_packet(_PROBE_JSON)
    found: dict[str, dict] = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        sock.settimeout(1.0)
        sock.bind(("", 0))
        for addr in (MCAST_ADDR, BROADCAST):
            try:
                sock.sendto(packet, (addr, PORT))
            except OSError:
                pass

        end = time.time() + max(1, timeout)
        while time.time() < end:
            try:
                raw, _addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            body = _json_body(raw)
            if not body:
                continue
            cam = _parse_device(body)
            if cam:
                key = cam["MAC-Adresse/Seriennummer"] or cam["IP Adresse: Konfiguriert"]
                found.setdefault(key, cam)
    finally:
        sock.close()
    return list(found.values())
