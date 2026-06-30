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
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value) -> None:
        self._data[key] = value
        self.save()
