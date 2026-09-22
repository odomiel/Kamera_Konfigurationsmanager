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

"""Timezone action: set the camera's time zone via the vendor's time API.

On Axis this uses the Time API (``setTimeZone``, IANA names such as ``Europe/Berlin``),
which replaces the ``Time.POSIXTimeZone`` parameter removed in AXIS OS 13. The dialog
offers an editable combo box filled from the stdlib ``zoneinfo`` list (with a small
built-in fallback if no tz database is present) and a button to load the current zone —
and the zones the device itself supports — from the first selected camera.

Only shown for plugins that declare ``Capability.TIMEZONE``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from kkm.core import Capability, camera_key, certpin, t
from .base import ActionDialog

# Fallback, falls die Laufzeit keine tz-Datenbank hat (zoneinfo leer). Die Combobox ist
# ohnehin frei editierbar — der Nutzer kann jeden IANA-Namen eingeben.
_FALLBACK_ZONES = [
    "UTC", "Europe/Berlin", "Europe/Vienna", "Europe/Zurich", "Europe/London",
    "Europe/Paris", "Europe/Madrid", "Europe/Rome", "Europe/Amsterdam",
    "Europe/Stockholm", "Europe/Warsaw", "Europe/Moscow", "America/New_York",
    "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Sao_Paulo",
    "Asia/Dubai", "Asia/Kolkata", "Asia/Shanghai", "Asia/Tokyo", "Australia/Sydney",
]


def _iana_zones() -> list[str]:
    try:
        from zoneinfo import available_timezones
        zones = sorted(available_timezones())
        if zones:
            return zones
    except Exception:  # noqa: BLE001 - keine tz-Datenbank o. Ä.
        pass
    return list(_FALLBACK_ZONES)


class TimezoneDialog(ActionDialog):
    title_text = "Zeitzone"
    capability = Capability.TIMEZONE

    def build_body(self, parent):
        self._tz = tk.StringVar()

        ttk.Label(parent, text=t("Zeitzone (IANA, z. B. Europe/Berlin):")).pack(anchor=tk.W)
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=(2, 0))
        self._combo = ttk.Combobox(row, textvariable=self._tz, values=_iana_zones(), width=34)
        self._combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(row, text=t("Von erster Kamera laden"),
                   command=self._load_from_cam).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Label(parent, wraplength=440, justify=tk.LEFT,
                  text=t("Setzt die Zeitzone über die Time API (AXIS OS 9.30+). Ersetzt den "
                         "in AXIS OS 13 entfernten Parameter Time.POSIXTimeZone; die "
                         "Sommerzeit wird anhand des IANA-Namens automatisch angewandt.")).pack(
            anchor=tk.W, pady=(6, 0))

        ttk.Button(parent, text=t("Anwenden"), command=self._apply).pack(anchor=tk.W, pady=(8, 0))

    # ---------------------------------------------------------------- helpers
    def _load_from_cam(self):
        """Aktuelle Zeitzone (und, wenn das Gerät sie liefert, die unterstützten Zonen)
        der ersten Kamera laden. Kurzer synchroner Aufruf — vom Nutzer ausgelöst."""
        cam = self.cameras[0]
        plugin = self.plugin_for(cam)
        if plugin is None:
            return
        creds = self.creds_for(cam)
        try:
            with certpin.bound(camera_key(cam), creds.scheme):
                current = plugin.get_timezone(cam, creds)
        except Exception as exc:  # noqa: BLE001 - Netz-/Auth-Fehler dem Nutzer zeigen
            messagebox.showerror(t(self.title_text),
                                 t("Abruf fehlgeschlagen: {err}", err=exc), parent=self)
            return
        try:
            with certpin.bound(camera_key(cam), creds.scheme):
                zones = plugin.list_timezones(cam, creds)
            if zones:
                self._combo.config(values=sorted(zones))
        except Exception:  # noqa: BLE001 - optionale Geräte-Liste
            pass
        if current:
            self._tz.set(current)
        messagebox.showinfo(
            t(self.title_text),
            t("Aktuelle Zeitzone der Kamera: {tz}", tz=current or t("(unbekannt)")),
            parent=self)

    def _apply(self):
        tz = self._tz.get().strip()
        if not tz:
            messagebox.showinfo(t(self.title_text),
                                t("Bitte eine Zeitzone wählen."), parent=self)
            return
        self.run_per_camera(
            lambda plugin, camera, creds: plugin.set_timezone(camera, creds, tz),
            done_msg=t("Zeitzone-Umstellung abgeschlossen."))
