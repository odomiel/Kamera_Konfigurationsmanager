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

"""Application-level settings persisted as JSON (no database).

Separate from the group store: this holds UI/plugin preferences, not camera data.
Stored next to ``groups.json`` in the user config dir. Currently:

- ``enabled_plugins`` — list of plugin ids the user has switched on (the plugin
  manager). ``None`` (key absent) means "all available plugins on by default".
- ``hidden_columns`` — device-table columns the user has hidden.
"""

from __future__ import annotations

import json
import os

from .groups import config_dir

DEFAULTS = {
    "enabled_plugins": None,     # None -> all on
    "hidden_columns": [],
    "column_widths": {},         # Spaltenbreiten der Geräteliste (vom Nutzer gezogen)
    "theme": "dark",             # "dark" | "light" (Sun-Valley-Theme)
    "firmware_parallel": True,   # Firmware-Updates nebenläufig statt nacheinander
    "firmware_max_parallel": 4,  # max. gleichzeitige Firmware-Updates
    "firmware_check_online": True,   # Update-Suche im Firmware-Dialog anbieten
    "firmware_prefer_track": True,   # Vorschlag in der Hauptversion der Kamera bleiben
    "firmware_repo_url": "",     # leer -> Vorgabe des Plugins (interner Spiegel möglich)
    "start_maximized": False,    # Hauptfenster beim Start maximiert öffnen
    "disclaimer_accepted": False, # Haftungshinweis dauerhaft bestätigt (nicht wieder zeigen)
}


class AppSettings:
    FILENAME = "settings.json"

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), self.FILENAME)
        self._data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    self._data.update(json.load(fh))
            except (OSError, ValueError):
                pass  # corrupt/unreadable -> fall back to defaults

    def save(self) -> None:
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except OSError:
            # z. B. Config-Verzeichnis nicht beschreibbar: Einstellungen gelten dann
            # nur für die laufende Sitzung. save() hängt u. a. am Spaltenziehen —
            # ein Fehler hier darf keinen Tk-Callback sprengen.
            pass

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value) -> None:
        self._data[key] = value
        self.save()
