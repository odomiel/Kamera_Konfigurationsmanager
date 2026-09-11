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

"""Update-Pruefung gegen die oeffentlichen GitHub-Releases (stdlib-only).

Fragt ``/releases/latest`` ab — GitHub liefert dort die neueste **stabile** Release
(Vorabversionen mit ``bN``-Suffix sind als prerelease markiert und fallen raus), also
genau das, worueber der Nutzer benachrichtigt werden soll. Der Vergleich nutzt
``version_tuple`` (Datumsanteil ``JJ.MM.TT``). Netzfehler/Offline sind kein Fehler —
die Funktionen liefern dann still ``None``.
"""

from __future__ import annotations

import json
import urllib.request

from kkm.version import __version__, GITHUB_SLUG, PROJECT_URL
from kkm.core.camera import version_tuple

RELEASES_API = f"https://api.github.com/repos/{GITHUB_SLUG}/releases/latest"


def latest_release(timeout: float = 6.0) -> dict | None:
    """Neueste stabile Release als ``{"version": "26.09.05", "url": …}`` — oder ``None``
    bei Netzfehler/Offline/unerwarteter Antwort."""
    req = urllib.request.Request(RELEASES_API, headers={
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kkm-updatecheck",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except Exception:  # noqa: BLE001 - offline/HTTP/JSON: kein Update-Ergebnis, kein Absturz
        return None
    tag = str(data.get("tag_name", "")).lstrip("vV").strip()
    if not tag:
        return None
    return {"version": tag, "url": data.get("html_url") or PROJECT_URL}


def is_newer(candidate: str, current: str = __version__) -> bool:
    """True, wenn *candidate* eine hoehere Version als *current* ist."""
    return version_tuple(candidate) > version_tuple(current)


def check_for_update(timeout: float = 6.0) -> dict | None:
    """Liefert ``{"version", "url"}`` nur, wenn eine **neuere** Version vorliegt,
    sonst ``None`` (aktuell, offline oder Fehler)."""
    rel = latest_release(timeout)
    if rel and is_newer(rel["version"]):
        return rel
    return None
