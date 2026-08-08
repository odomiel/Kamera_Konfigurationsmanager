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

# Die hier erzeugten Kamera-Dicts folgen der Form von ``kkm.core.camera.FIELD_NAMES``.

MCAST_ADDR = "239.255.255.250"
MCAST_PORT = 37020
BROADCAST = "255.255.255.255"

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
        "_firmware": _text(root, "SoftwareVersion"),
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


def _local_ipv4s() -> list[str]:
    """Best-effort Liste lokaler IPv4-Adressen (stdlib-only) fuer Multicast-Join/-Send
    auf allen Interfaces. Loopback wird ausgelassen."""
    ips: set[str] = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("192.0.2.1", 9))          # TEST-NET-1, nicht routbar; sendet nichts
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


def discover(timeout: int = 10) -> list[dict]:
    """Blockierender SADP-Probe. Liefert Kamera-Dicts (Schluessel = FIELD_NAMES).

    **Entscheidend:** SADP-Geraete schicken ihre ``ProbeMatch``-Antwort an die
    **Multicast-Gruppe** ``239.255.255.250:37020`` — NICHT per Unicast an den Frager.
    Deshalb muss dieser Socket auf Port 37020 gebunden *und* der Gruppe beigetreten
    sein, sonst kommen die Antworten nie an. Genau das findet auch **werksneue** Kameras
    in einem FREMDEN IP-Segment (z. B. Werks-IP ``192.0.0.64``/``192.168.1.64``, waehrend
    der Host in ``192.0.2.0/24`` steht): Multicast wird auf L2 zugestellt, eine
    Unicast-Antwort wuerde die (gatewaylose) Kamera off-subnet nie los.

    Antworten werden bis *timeout* gesammelt und ueber MAC (ersatzweise IP) entdoppelt —
    Geraete mit mehreren Interfaces antworten mehrfach."""
    probe = _PROBE.format(uuid=uuid.uuid4()).encode("utf-8")
    found: dict[str, dict] = {}
    ifaces = _local_ipv4s()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # SO_REUSEPORT (wo vorhanden) erlaubt die Koexistenz mit der offiziellen
        # SADP-Software, die denselben Port 37020 belegt.
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

        # Auf 37020 binden, um die Multicast-Antworten zu empfangen. Klappt das nicht
        # (Port belegt ohne REUSEPORT), auf Ephemeral zurueckfallen — findet dann nur
        # noch Kameras im selben Segment (die per Unicast antworten koennen).
        joined = True
        try:
            sock.bind(("", MCAST_PORT))
        except OSError:
            sock.bind(("", 0))
            joined = False

        if joined:
            # Der Gruppe auf allen Interfaces beitreten (INADDR_ANY + je lokaler IP).
            for iface in ["0.0.0.0", *ifaces]:
                try:
                    mreq = socket.inet_aton(MCAST_ADDR) + socket.inet_aton(iface)
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                except OSError:
                    pass

        targets = [(MCAST_ADDR, MCAST_PORT), (BROADCAST, MCAST_PORT)]

        def _send_probe() -> None:
            # Ueber jedes Interface senden (IP_MULTICAST_IF), damit die Probe auf
            # mehr-NIC-Hosts auch das Segment der werksneuen Kamera erreicht.
            for iface in (ifaces or ["0.0.0.0"]):
                try:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF,
                                    socket.inet_aton(iface))
                except OSError:
                    pass
                for tgt in targets:
                    try:
                        sock.sendto(probe, tgt)
                    except OSError:
                        pass

        sock.settimeout(1.0)
        _send_probe()
        end = time.time() + max(1, timeout)
        next_probe = time.time() + 2.0        # periodisch nachfragen (Pakete gehen verloren)
        while time.time() < end:
            if time.time() >= next_probe:
                _send_probe()
                next_probe = time.time() + 2.0
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
