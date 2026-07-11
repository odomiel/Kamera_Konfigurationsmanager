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

"""The camera dict — shape and helpers shared by *all* plugins.

A camera is a plain dict. ``FIELD_NAMES`` are the base fields every plugin's
``discover()`` must fill; the manager adds its own keys on top (``_vendor``,
``_model``, ``_firmware``, ``_serial``, ``_group``, ``_online``).

This module used to live in the Axis plugin (``axis/discovery.py``) and was imported
from there by the GUI and by ``core.groups`` — which quietly made the whole program
depend on one vendor. Nothing in here is Axis-specific, so it belongs in core: a
second plugin fills the same dict and the GUI keeps working.
"""

from __future__ import annotations

import csv
import re

# Basisfelder eines Kamera-Dicts. Die Discovery jedes Plugins fuellt sie; die
# Zusatzschluessel des Managers (_vendor, _model, _firmware, _online, _group)
# stehen bewusst NICHT hier drin.
FIELD_NAMES = [
    "Name",
    "IP Adresse: Zeroconfig",
    "IP Adresse: Konfiguriert",
    "Port",
    "Hostname",
    "MAC-Adresse/Seriennummer",
]


def get_first_ip(camera: dict) -> str:
    """Erste erreichbare IP einer Kamera: konfigurierte vor Zeroconf-Adresse."""
    for field in ("IP Adresse: Konfiguriert", "IP Adresse: Zeroconfig"):
        ip = str(camera.get(field, "")).split(",")[0].strip()
        if ip:
            return ip
    return ""


def version_tuple(version: str) -> tuple[int, ...]:
    """Firmware-Version vergleichbar machen: „12.11.72" -> (12, 11, 72).

    Nicht-numerische Teile werden zu 0, damit auch alte Schreibweisen („5.51.7.3")
    und Platzhalter vergleichbar bleiben. Herstellerneutral — jedes Plugin liefert
    Versionen als Punktfolge.
    """
    out = []
    for part in re.split(r"[._-]", (version or "").strip()):
        m = re.match(r"\d+", part)
        out.append(int(m.group()) if m else 0)
    return tuple(out) or (0,)


def next_ip(ip_str: str, step: int = 1) -> str:
    """Liefert die um *step* erhoehte IPv4-Adresse (fuer den Start-IP-Modus).
    Wirft ValueError bei ungueltiger Eingabe."""
    parts = [int(p) for p in ip_str.split(".")]
    if len(parts) != 4 or any(p < 0 or p > 255 for p in parts):
        raise ValueError(f"Ungültige IPv4-Adresse: {ip_str}")
    value = (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
    value += step
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


def parse_user_list(path, valid_roles, default_role):
    """Liest eine Benutzerliste fuer den Stapel-Import: ``Name,Passwort[,Rolle]``.

    Leerzeilen und ``#``-Zeilen werden uebersprungen; fehlt die Rolle, gilt
    *default_role*. *valid_roles* sind die erlaubten Rollen/Stufen des Plugins
    (Gross-/Kleinschreibung egal). Wirft ValueError mit Zeilennummern, damit nichts
    Halbfertiges angelegt wird. Liefert eine Liste von ``{name, password, role}``.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            rows = list(csv.reader(fh))
    except OSError as exc:
        raise ValueError(f"Datei nicht lesbar: {exc}") from exc

    valid = {str(r).lower(): r for r in valid_roles}
    users, errors = [], []
    for num, row in enumerate(rows, 1):
        if not row:
            continue
        name = row[0].strip()
        if not name or name.startswith("#"):
            continue
        if len(row) < 2 or not row[1]:
            errors.append(f"Zeile {num}: Passwort fehlt")
            continue
        role_raw = row[2].strip() if len(row) >= 3 else ""
        if role_raw:
            role = valid.get(role_raw.lower())
            if role is None:
                errors.append(f"Zeile {num}: ungültige Rolle/Stufe '{role_raw}'")
                continue
        else:
            role = default_role
        users.append({"name": name, "password": row[1], "role": role})
    if errors:
        raise ValueError("; ".join(errors))
    if not users:
        raise ValueError("Keine Benutzer in der Datei gefunden.")
    return users


def export_results(cameras, output_file, fmt=None, columns=None):
    """Exportiert die Kameraliste als CSV oder ausgerichtete Texttabelle."""
    if columns is None:
        columns = FIELD_NAMES
    if fmt is None:
        fmt = "csv" if output_file.lower().endswith(".csv") else "txt"

    if fmt == "csv":
        with open(output_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            for cam in cameras:
                writer.writerow({c: cam.get(c, "") for c in columns})
    else:
        widths = {c: max(len(c), *(len(str(cam.get(c, ""))) for cam in cameras)) if cameras
                  else len(c) for c in columns}
        rows = ["  ".join(c.ljust(widths[c]) for c in columns),
                "  ".join("-" * widths[c] for c in columns)]
        for cam in cameras:
            rows.append("  ".join(str(cam.get(c, "")).ljust(widths[c]) for c in columns))
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
