# Kamera_Konfigurationsmanager - Import von AXIS Device Manager Export-Dateien.
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

"""Parser für **AXIS Device Manager**-Export-Dateien (Datei-Format 1.x und 2.x).

stdlib-only und GUI-unabhängig — bewusst **ohne** Seiteneffekte auf ``GroupStore``
oder ``PasswordVault``; das Anwenden übernimmt die GUI. So bleibt der Parser
isoliert testbar.

Aufbau der Exporte::

    { encrypted, fileFormatVersionMayor, fileFormatVersionMinor,
      data: { serverInformation, deviceData } }

``deviceData`` enthält immer ``devices`` (Liste). Die Gruppen ("Tags") liegen je
nach Format unterschiedlich:

* **v1** (Format 1.x): ``deviceTag`` = ``[{id, name}]`` und die Verknüpfung
  ``deviceTagRelation`` = ``[{deviceTag, device}]`` (beides über ``id``).
* **v2** (Format 2.x): ``deviceTags`` = ``[{name, devices:[id, ...]}]`` (die
  Geräte-IDs sind direkt in den Tag eingebettet).

Ergebnis (``AdmImportResult``): App-Kameradicts, Gruppen (Name → ``camera_key``)
und optionale Zugangsdaten (``camera_key`` → ``{username, password}``).
"""

from __future__ import annotations

import base64
import json

from kkm.core.groups import camera_key


class AdmImportError(Exception):
    """Datei ist kein (unterstützter) AXIS-Device-Manager-Export."""


class AdmImportResult:
    """Ergebnis eines Imports — reine Daten, noch nicht angewandt."""

    def __init__(self):
        self.version = ""                       # z. B. "1.1" / "2.0"
        self.cameras: list[dict] = []           # App-Kameradicts
        self.groups: dict[str, list[str]] = {}  # Gruppenname -> camera_keys
        self.credentials: dict[str, dict] = {}  # camera_key -> {username, password}
        self.warnings: list[str] = []

    @property
    def n_cameras(self) -> int:
        return len(self.cameras)

    @property
    def n_groups(self) -> int:
        return len(self.groups)

    @property
    def n_credentials(self) -> int:
        return len(self.credentials)


def _decode_password(raw: str, mayor) -> str:
    """Geräte-Passwort entschlüsseln — abhängig vom Dateiformat.

    Format 1.x speichert das Passwort im Klartext, ab Format 2.x **base64-kodiert**
    (der Benutzername bleibt in beiden Formaten Klartext). Schlägt das Dekodieren
    unerwartet fehl, wird der Rohwert behalten statt Daten zu verlieren.
    """
    if not raw or not (isinstance(mayor, int) and mayor >= 2):
        return raw
    try:
        return base64.b64decode(raw, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return raw


def _device_to_camera(dev: dict) -> dict:
    """Ein Export-Gerät in ein App-Kameradict übersetzen (Basiskeys + _-Felder)."""
    mac = str(dev.get("macAddress") or "").strip()
    ip = str(dev.get("address") or "").strip()
    if ip in ("0.0.0.0", "::", "0"):            # Platzhalter = keine echte IP
        ip = ""
    model = str(dev.get("model") or "").strip()
    port = dev.get("httpPort")
    return {
        "Name": model or mac or "?",            # kein Anzeigename im Export -> Modell
        "IP Adresse: Zeroconfig": "",
        "IP Adresse: Konfiguriert": ip,
        "Port": port if port not in (None, "") else "",
        "Hostname": str(dev.get("hostName") or "").strip(),
        "MAC-Adresse/Seriennummer": mac,
        "_vendor": "axis",
        "_online": None,
        "_model": model,
        "_firmware": str(dev.get("firmwareVersion") or "").strip(),
    }


def parse_export(path: str) -> AdmImportResult:
    """Einen Export einlesen und in ein :class:`AdmImportResult` überführen.

    Wirft :class:`AdmImportError` bei nicht lesbaren, verschlüsselten oder
    strukturell unpassenden Dateien.
    """
    try:
        with open(path, encoding="utf-8-sig") as fh:   # Exporte tragen ein BOM
            raw = json.load(fh)
    except OSError as exc:
        raise AdmImportError(f"Datei nicht lesbar: {exc}") from exc
    except ValueError as exc:
        raise AdmImportError(f"Keine gültige JSON-Datei: {exc}") from exc

    if not isinstance(raw, dict) or "data" not in raw:
        raise AdmImportError("Kein AXIS-Device-Manager-Export ('data' fehlt).")
    if raw.get("encrypted"):
        raise AdmImportError("Verschlüsselte Exporte werden nicht unterstützt.")

    mayor = raw.get("fileFormatVersionMayor")
    minor = raw.get("fileFormatVersionMinor")
    device_data = (raw.get("data") or {}).get("deviceData") or {}
    devices = device_data.get("devices")
    if not isinstance(devices, list):
        raise AdmImportError("Unerwartete Struktur (deviceData.devices fehlt).")

    res = AdmImportResult()
    res.version = f"{mayor}.{minor}"

    # --- Geräte -> Kameras, id->key-Abbildung und Zugangsdaten sammeln ---
    id_to_key: dict = {}
    seen: set[str] = set()
    for dev in devices:
        if not isinstance(dev, dict):
            continue
        cam = _device_to_camera(dev)
        key = camera_key(cam)
        if not key:
            res.warnings.append("Gerät ohne MAC/Identität übersprungen.")
            continue
        did = dev.get("id")
        if did is not None:
            id_to_key[did] = key
        if key not in seen:            # gleiche MAC nicht doppelt in die Liste
            seen.add(key)
            res.cameras.append(cam)
        user = str(dev.get("deviceUserName") or "")
        pw = _decode_password(str(dev.get("devicePassword") or ""), mayor)
        if user or pw:
            res.credentials[key] = {"username": user, "password": pw}

    # --- Gruppen je nach Datei-Format ---
    if mayor == 1 or "deviceTagRelation" in device_data:
        _parse_groups_v1(device_data, id_to_key, res)
    elif mayor == 2 or "deviceTags" in device_data:
        _parse_groups_v2(device_data, id_to_key, res)
    else:
        res.warnings.append(
            f"Unbekanntes Gruppenformat (Version {res.version}) — nur Geräte importiert.")
    return res


def _add_member(groups: dict[str, list[str]], name: str, key: str) -> None:
    members = groups.setdefault(name, [])
    if key not in members:
        members.append(key)


def _parse_groups_v1(device_data: dict, id_to_key: dict, res: AdmImportResult) -> None:
    """Format 1.x: Tag-Tabelle + Verknüpfungstabelle über IDs auflösen."""
    tag_names = {t.get("id"): t.get("name")
                 for t in device_data.get("deviceTag", []) if isinstance(t, dict)}
    groups: dict[str, list[str]] = {}
    dangling = 0
    for rel in device_data.get("deviceTagRelation", []):
        if not isinstance(rel, dict):
            continue
        name = tag_names.get(rel.get("deviceTag"))
        key = id_to_key.get(rel.get("device"))
        if not name or not key:
            dangling += 1
            continue
        _add_member(groups, name, key)
    res.groups = groups
    if dangling:
        res.warnings.append(f"{dangling} Gruppenzuordnung(en) ohne passendes Gerät/Tag übersprungen.")


def _parse_groups_v2(device_data: dict, id_to_key: dict, res: AdmImportResult) -> None:
    """Format 2.x: Geräte-IDs sind direkt im Tag eingebettet."""
    groups: dict[str, list[str]] = {}
    dangling = 0
    for tag in device_data.get("deviceTags", []):
        if not isinstance(tag, dict):
            continue
        name = tag.get("name")
        if not name:
            continue
        groups.setdefault(name, [])
        for did in tag.get("devices", []):
            key = id_to_key.get(did)
            if key:
                _add_member(groups, name, key)
            else:
                dangling += 1
    res.groups = groups
    if dangling:
        res.warnings.append(f"{dangling} Gruppen-Geräteverweis(e) ohne passendes Gerät übersprungen.")
