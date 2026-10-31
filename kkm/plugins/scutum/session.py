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
import subprocess

#: Der einzige offene Dienst des Geraets (SSH). Zugleich der Online-Pruefpunkt.
PORT = 22

_MAC_RE = re.compile(r"([0-9a-fA-F]{2}(?:[:-][0-9a-fA-F]{2}){5})")

#: Marker im (DHCP-/Reverse-DNS-)Hostnamen, z. B. ``netcon3-1436520562``.
#: Reverse-DNS-Marker. ``netcon`` gefolgt von optionaler Modellnummer und/oder Geräte-ID.
#: Ein Trenner (``-``/``_``) scheidet Modellnummer von Geräte-ID; ohne Trenner ist eine
#: **lange** Ziffernfolge die Geräte-ID (keine Modellnummer) — die Netcon 2 heißt im DNS
#: ``netcon1793132771`` (reine Seriennummer), die Netcon 3 ``netcon3-1436520562``.
_NETCON = re.compile(r"netcon[\s_-]*([0-9]+)?(?:[-_]+([0-9a-z]+))?", re.I)

#: Ab wie vielen Ziffern eine trennerlose Zahl nach ``netcon`` als Geräte-ID statt als
#: Modellnummer gilt (``netcon4`` = Modell 4, ``netcon1793132771`` = Serien-ID).
_MAX_MODELLNUMMER_STELLEN = 2

#: MAC-OUIs bekannter Netcon-Hardware -> Modell. Der Hostname ist frei konfigurierbar
#: und oft gar nicht im DNS registriert (dann kein Reverse-DNS-Marker); der OUI der
#: Netzkarte dagegen liegt fest und identifiziert die Geraeteserie zuverlaessig.
#: 74:6A:8F = VS Vision Systems GmbH (Norderstedt) = Netcon-3-Hardware.
#: 00:04:D9 = Titan Electronics Inc. (Taiwan) = Netcon-2-Hardware (älteres Gerät, dropbear-SSH).
_NETCON_OUIS = {
    "74:6A:8F": "Netcon 3",
    "00:04:D9": "Netcon 2",
}

#: Raspberry-Pi-OUIs — die Hardwarebasis der Netcon 4. Allein **nicht** eindeutig (jeder
#: Raspberry Pi trägt sie), darum bewusst nicht in ``_NETCON_OUIS``. Sie kennzeichnen eine
#: Netcon 4 nur **zusammen mit** dem exakten Netcon-4-SSH-Banner (siehe ``_NETCON4_SSH``).
_RPI_OUIS = frozenset({
    "B8:27:EB",                           # Raspberry Pi Foundation (Pi 1–3, klassisch)
    "DC:A6:32", "E4:5F:01",               # Raspberry Pi Trading (Pi 4)
    "28:CD:C1", "D8:3A:DD", "2C:CF:67",   # neuere Modelle
})

#: Exaktes SSH-Banner der an echter Hardware verifizierten Netcon 4 (Raspberry Pi OS
#: „Buster"). Eine Netcon 4 ohne ``netcon``-Hostnamen (DHCP vergibt z. B. ``enet``) lässt
#: sich im Netz nur hierüber von einem beliebigen Raspberry Pi unterscheiden: nur bei
#: **genau** diesem Banner (plus RPi-OUI) gilt das Gerät als Netcon 4. Ein moderner Pi
#: (Bookworm, OpenSSH 9.x) löst damit nicht aus.
_NETCON4_SSH = "SSH-2.0-OpenSSH_7.9p1 Raspbian-10+deb10u2+rpt1"


def _ist_netcon4_pi(mac: str, ssh: str) -> bool:
    """Hostnamenlose Netcon 4 auf Raspberry-Pi-Basis: Treffer nur bei RPi-OUI **und**
    exaktem Netcon-4-Buster-Banner — der OUI allein träfe jeden Pi."""
    oui = mac[:8].upper() if mac else ""
    return oui in _RPI_OUIS and (ssh or "").strip() == _NETCON4_SSH


def _erkennen(host: str, mac: str, ssh: str = "") -> dict | None:
    """Entscheidet **ohne Netzwerk**, ob Hostname/MAC/SSH-Banner eine Netcon kennzeichnen.

    Drei Wege: der Reverse-DNS-Name ``netcon…`` (trägt ggf. Modellnummer + Geräte-ID),
    ein bekannter Hersteller-OUI der Netzkarte (Netcon 2/3) oder — für die hostnamenlose
    Netcon 4 — ein Raspberry-Pi-OUI zusammen mit dem exakten Netcon-4-SSH-Banner. Liefert
    ``{modell, serial}`` oder ``None``. Rein zeichenkettenbasiert, damit ohne echtes Gerät
    testbar.

    Die Modellnummer kommt bevorzugt aus dem Hostnamen (``netcon<n>`` / ``netcon<n>-<id>``);
    fehlt sie dort — etwa weil der Name nur die Serien-ID trägt (``netcon1793132771``) oder
    gar kein ``netcon…`` ist —, liefert der OUI (Netcon 2/3) bzw. der Raspberry-Pi+Banner-Weg
    (Netcon 4) das Modell."""
    treffer = _NETCON.match(host) if host else None
    oui_modell = _NETCON_OUIS.get(mac[:8].upper()) if mac else None
    rpi4 = _ist_netcon4_pi(mac, ssh)
    if not treffer and not oui_modell and not rpi4:
        return None

    nummer = ""
    serial = ""
    if treffer:
        z1 = treffer.group(1) or ""
        z2 = treffer.group(2) or ""
        if z2:                                         # netcon<n>-<serial>: n=Modell, Rest=ID
            nummer, serial = z1, z2
        elif len(z1) <= _MAX_MODELLNUMMER_STELLEN:     # netcon<n>: kurze Zahl = Modellnummer
            nummer = z1
        else:                                          # netcon<lange-zahl>: reine Geräte-ID
            serial = z1

    if nummer:
        modell = f"Netcon {nummer}"
    elif oui_modell:                                   # Hostname ohne Modellnr. -> OUI entscheidet
        modell = oui_modell
    elif rpi4:                                         # hostnamenlos, RPi + exaktes Buster-Banner
        modell = "Netcon 4"
    else:
        modell = "Netcon"
    return {"modell": modell, "serial": serial}


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


def mac_adresse(ip: str) -> str:
    """MAC-Adresse der IP aus dem ARP-Cache (nur im selben Subnetz ermittelbar).

    Das Netcon (I/O-Modul auf Linux/Raspberry Pi) bietet keinen Dienst, der eine MAC
    nennt — aber im selben LAN-Segment liefert ARP sie ohne Login. Voraussetzung ist
    ein gefuellter ARP-Cache; ein vorheriger TCP-Connect (``erreichbar``) sorgt dafuer.
    Plattformuebergreifend: erst Linux-``/proc/net/arp``, dann ``ip neigh`` / ``arp``.
    Liefert die MAC gross mit Doppelpunkten (``B8:27:EB:…``) oder ``""``."""
    def norm(mac: str) -> str:
        return mac.upper().replace("-", ":")

    # 1) Linux: /proc/net/arp (stdlib, kein Subprozess)
    try:
        with open("/proc/net/arp", encoding="ascii", errors="replace") as fh:
            next(fh, "")  # Kopfzeile
            for zeile in fh:
                felder = zeile.split()
                if len(felder) >= 4 and felder[0] == ip:
                    mac = felder[3]
                    if _MAC_RE.fullmatch(mac) and mac != "00:00:00:00:00:00":
                        return norm(mac)
    except OSError:
        pass
    # 2) Fallback (Windows/macOS/Linux): ip neigh / arp
    for cmd in (["ip", "neigh", "show", ip], ["arp", "-a", ip], ["arp", "-n", ip]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=4).stdout
        except (OSError, subprocess.SubprocessError):
            continue
        for treffer in _MAC_RE.findall(out):
            if treffer.replace("-", ":") != "00:00:00:00:00:00":
                return norm(treffer)
    return ""


def _nur_ssh_offen(ip: str, timeout: float = 1.0) -> bool:
    """True, wenn die typischen Web-Ports (80/443) **zu** sind — eine Netcon bietet im
    Netz ausschließlich SSH. Dient als Zusatzbestätigung des hostnamenlosen
    Raspberry-Pi-Erkennungswegs (ein normaler Pi mit Webdienst fällt so heraus)."""
    for port in (80, 443):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(min(timeout, 0.8))
        try:
            if s.connect_ex((ip, port)) == 0:
                return False
        except OSError:
            pass
        finally:
            s.close()
    return True


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
    """Erkennt eine Netcon ohne Login über drei Wege: den **Hostnamen** (``netcon…``)
    aus Reverse-DNS, den **MAC-OUI** der Netzkarte (bekannte Netcon-2/3-Hardware) **oder**
    — für die hostnamenlose Netcon 4 — einen **Raspberry-Pi-OUI zusammen mit dem exakten
    Netcon-4-SSH-Banner**. Der offene SSH-Port dient als Lebenszeichen und wird zuerst
    geprüft.

    Liefert ``{name, modell, serial, mac, ssh}`` bei einem Treffer, sonst ``None`` — nur
    Geräte mit Hostnamen-Marker, bekanntem Hersteller-OUI oder dem Raspberry-Pi+Banner-
    Profil werden gelistet (keine Fehltreffer auf beliebige SSH-Hosts)."""
    if not erreichbar(ip, min(timeout, 1.5)):
        return None
    host = _reverse_dns(ip, min(timeout, 2.0))
    # MAC aus dem ARP-Cache (gefuellt durch das obige erreichbar()); zugleich der
    # zweite Erkennungsweg (Hersteller-OUI) und die stabile Identitaet.
    mac = mac_adresse(ip)
    ssh = ssh_banner(ip, min(timeout, 3.0))
    treffer = _erkennen(host, mac, ssh)
    if not treffer:
        return None
    # Der hostnamenlose Raspberry-Pi-Weg (Netcon 4) ist eine Heuristik. Wenn weder ein
    # netcon-Hostname noch ein bekannter Netcon-OUI vorliegt, zusätzlich bestätigen, dass
    # das Gerät — wie eine Netcon — NUR SSH anbietet (ein normaler Pi mit Web fällt raus).
    hostname_marker = bool(_NETCON.match(host)) if host else False
    bekannter_oui = (mac[:8].upper() if mac else "") in _NETCON_OUIS
    if not hostname_marker and not bekannter_oui and not _nur_ssh_offen(ip, timeout):
        return None
    return {
        "name": host,
        "modell": treffer["modell"],
        "serial": treffer["serial"],
        "mac": mac,
        "ssh": ssh,
    }
