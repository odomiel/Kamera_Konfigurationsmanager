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

"""Minimal stdlib-only HTTPS client for the Senstar (Aimetis) Thin Client.

Stufe 1 (Anzeige) braucht nur eine **unauthentifizierte Kennung** des Geraets: der
Thin Client (Software 3.x) liefert auf jede unbekannte URL eine 404-Seite, die in der
Kopfleiste ``Senstar <Modell> Thin Client`` und die Softwarefassung nennt. Das reicht,
um das Geraet zu erkennen und Modell/Version anzuzeigen — **ohne jeden Loginversuch**
(wichtig beim Subnetz-Scan, damit keine Anmeldeversuche gegen fremde Geraete laufen).

Die 3.10-REST-API (Token-Login ueber ``POST /Session`` mit ``{"user","pwd"}`` -> Token
im Body, danach als Cookie ``authtoken``; Endpunkte ``/Settings``, ``/System/...``,
``/User``, kartiert aus ``server.js`` des Geraets) bleibt Stufe 2 vorbehalten und ist
hier bewusst noch nicht umgesetzt.
"""

from __future__ import annotations

import re
import socket
import ssl
import urllib.error
import urllib.request

# Das Geraet spricht nur HTTPS (HTTP leitet dorthin um) mit selbstsigniertem
# Zertifikat -> Pruefung aus (wie die anderen Plugins fuer LAN-HTTPS).
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

PORT = 443

# „Senstar A10D Thin Client" (Modell = mittleres Wort). Die Softwarefassung steht
# in der sysInfo-Kopfleiste *hinter* dieser Zeile — darum wird sie erst im Text
# NACH dem Modell-Treffer gesucht (sonst faengt man die jquery-ui-1.12.1 der Seite).
_MODELL = re.compile(r"Senstar\s+(\S+)\s+Thin\s+Client", re.I)
_FASSUNG = re.compile(r"(\d+\.\d+\.\d+(?:\.\d+)?)")


def erreichbar(ip: str, timeout: float = 0.4) -> bool:
    """Schneller TCP-Vortest auf den HTTPS-Port (vor dem teureren TLS-GET)."""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, PORT)) == 0
    except OSError:
        return False
    finally:
        s.close()


def kennung(ip: str, timeout: float = 4.0) -> dict | None:
    """Erkennt einen Senstar Thin Client unauthentifiziert anhand seiner 404-Seite.

    Liefert ``{"modell", "version", "name"}`` oder ``None``, wenn es keiner ist /
    nicht antwortet. Rein lesend (ein GET), kein Loginversuch.
    """
    url = f"https://{ip}:{PORT}/kkm-sondierung"
    req = urllib.request.Request(url, headers={"Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_SSL) as resp:
            roh = resp.read(8192)
    except urllib.error.HTTPError as exc:          # 404 ist der Normalfall -> Body lesen
        try:
            roh = exc.read(8192)
        except Exception:  # noqa: BLE001
            return None
    except Exception:  # noqa: BLE001 - offline / kein TLS / kein HTTP
        return None
    text = roh.decode("utf-8", errors="replace")
    m = _MODELL.search(text)
    if not m:
        return None                                 # kein Senstar Thin Client
    modell = m.group(1)
    mf = _FASSUNG.search(text, m.end())             # Fassung erst NACH der Modellzeile
    return {
        "modell": modell,
        "version": mf.group(1) if mf else "",
        "name": f"Senstar {modell} Thin Client",
    }
