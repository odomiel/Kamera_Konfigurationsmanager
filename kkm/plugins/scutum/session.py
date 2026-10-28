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


def _erkennen(host: str, mac: str) -> dict | None:
    """Entscheidet **ohne Netzwerk**, ob Hostname/MAC eine Netcon kennzeichnen.

    Zwei Wege: der Reverse-DNS-Name ``netcon…`` (trägt ggf. Modellnummer + Geräte-ID)
    oder ein bekannter Hersteller-OUI der Netzkarte. Liefert ``{modell, serial}`` oder
    ``None``. Rein zeichenkettenbasiert, damit ohne echtes Gerät testbar.

    Die Modellnummer kommt bevorzugt aus dem Hostnamen (``netcon<n>`` / ``netcon<n>-<id>``);
    fehlt sie dort — etwa weil der Name nur die Serien-ID trägt (``netcon1793132771``) oder
    gar kein ``netcon…`` ist —, liefert der OUI der Netzkarte das Modell."""
    treffer = _NETCON.match(host) if host else None
    oui_modell = _NETCON_OUIS.get(mac[:8].upper()) if mac else None
    if not treffer and not oui_modell:
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
    """Erkennt eine Netcon ohne Login über zwei Wege: den **Hostnamen** (``netcon…``)
    aus Reverse-DNS **oder** den **MAC-OUI** der Netzkarte (bekannte Netcon-Hardware).
    Der offene SSH-Port dient als Lebenszeichen und wird zuerst geprüft.

    Liefert ``{name, modell, serial, mac, ssh}`` bei einem Treffer, sonst ``None`` —
    nur Geräte mit Hostnamen-Marker oder bekanntem Hersteller-OUI werden gelistet
    (keine Fehltreffer auf beliebige SSH-Hosts)."""
    if not erreichbar(ip, min(timeout, 1.5)):
        return None
    host = _reverse_dns(ip, min(timeout, 2.0))
    # MAC aus dem ARP-Cache (gefuellt durch das obige erreichbar()); zugleich der
    # zweite Erkennungsweg (Hersteller-OUI) und die stabile Identitaet.
    mac = mac_adresse(ip)
    treffer = _erkennen(host, mac)
    if not treffer:
        return None
    return {
        "name": host,
        "modell": treffer["modell"],
        "serial": treffer["serial"],
        "mac": mac,
        "ssh": ssh_banner(ip, min(timeout, 3.0)),
    }
