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

"""Group management without a database.

Cameras are organised in groups persisted as a single JSON file in the user's
config dir (Windows ``%APPDATA%``, else ``$XDG_CONFIG_HOME``/``~/.config``). There
is one non-deletable, non-renamable group "Alle Kameras" that implicitly contains
every known camera; user-created groups are explicit membership lists keyed by a
stable camera key (MAC/serial).

Per-group online-check settings (enabled + interval) live here too, since the
requirement is a configurable online check *per group*.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict

ALL_CAMERAS_ID = "all"
ALL_CAMERAS_NAME = "Alle Kameras"


def config_dir() -> str:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    path = os.path.join(base, "kamera_konfigurationsmanager")
    os.makedirs(path, exist_ok=True)
    return path


def camera_key(camera: dict) -> str:
    """Stable identity of a camera across rescans: MAC/serial, else name+IP."""
    mac = str(camera.get("MAC-Adresse/Seriennummer", "")).strip()
    if mac:
        return mac
    from kkm.plugins.axis.discovery import get_first_ip  # local import: avoid cycle
    return f"{camera.get('Name', '?')}@{get_first_ip(camera)}"


@dataclass
class Group:
    id: str
    name: str
    members: list[str] = field(default_factory=list)   # camera keys
    online_check: bool = False
    online_interval: int = 60                            # seconds
    deletable: bool = True


class GroupStore:
    """Loads/saves groups and the known-camera roster from one JSON file."""

    FILENAME = "groups.json"

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), self.FILENAME)
        self.groups: dict[str, Group] = {}
        # roster: camera_key -> last-seen camera dict (so "Alle Kameras" persists
        # even when a camera is currently offline / not in the latest scan).
        self.roster: dict[str, dict] = {}
        # Reverse index camera_key -> {group ids} for O(1) groups_of / membership
        # checks (built from the groups' member lists; not persisted).
        self._index: dict[str, set[str]] = {}
        self.load()

    # --- persistence --------------------------------------------------------
    def load(self) -> None:
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            self.groups = {
                g["id"]: Group(**g) for g in data.get("groups", [])
            }
            self.roster = data.get("roster", {})
        # Guarantee the non-deletable "Alle Kameras" group exists.
        if ALL_CAMERAS_ID not in self.groups:
            self.groups[ALL_CAMERAS_ID] = Group(
                id=ALL_CAMERAS_ID, name=ALL_CAMERAS_NAME, deletable=False
            )
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._index = {}
        for gid, g in self.groups.items():
            if gid == ALL_CAMERAS_ID:
                continue
            for key in g.members:
                self._index.setdefault(key, set()).add(gid)

    def save(self) -> None:
        data = {
            "groups": [asdict(g) for g in self.groups.values()],
            "roster": self.roster,
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    # --- group CRUD ---------------------------------------------------------
    def create_group(self, name: str) -> Group:
        gid = uuid.uuid4().hex[:8]
        g = Group(id=gid, name=name)
        self.groups[gid] = g
        self.save()
        return g

    def rename_group(self, gid: str, name: str) -> None:
        g = self.groups.get(gid)
        if g and g.deletable:
            g.name = name
            self.save()

    def delete_group(self, gid: str) -> bool:
        g = self.groups.get(gid)
        if not g or not g.deletable:
            return False
        for key in g.members:
            idx = self._index.get(key)
            if idx:
                idx.discard(gid)
                if not idx:
                    del self._index[key]
        del self.groups[gid]
        self.save()
        return True

    def set_online_check(self, gid: str, enabled: bool, interval: int | None = None) -> None:
        g = self.groups.get(gid)
        if not g:
            return
        g.online_check = enabled
        if interval is not None:
            g.online_interval = max(5, int(interval))
        self.save()

    # --- membership ---------------------------------------------------------
    def remember(self, camera: dict) -> str:
        """Add/refresh a camera in the roster ("Alle Kameras"). Returns its key.

        Bereits gelesene Zusatzinfos (Firmware/Modell) bleiben erhalten, wenn die
        neue (mDNS-)Fassung sie nicht mitbringt — sonst würde jede Suche die per
        VAPIX nachgelesene Firmware/Modell wieder löschen.
        """
        key = camera_key(camera)
        prev = self.roster.get(key)
        if prev:
            for field in ("_firmware", "_model"):
                if not camera.get(field) and prev.get(field):
                    camera[field] = prev[field]
        self.roster[key] = camera
        return key

    def remember_all(self, cameras: list[dict]) -> None:
        for cam in cameras:
            self.remember(cam)
        self.save()

    def rekey_camera(self, old_key: str, new_key: str) -> None:
        """Ändert die Identität einer Kamera im Roster und in allen Gruppen.

        Nötig, wenn sich der aus Name+IP abgeleitete Schlüssel ändert (Kamera ohne
        MAC/Seriennummer, deren IP umgestellt wurde). Kein Save — der Aufrufer
        speichert gebündelt.
        """
        if old_key == new_key or old_key not in self.roster:
            return
        self.roster[new_key] = self.roster.pop(old_key)
        for g in self.groups.values():
            if old_key in g.members:
                g.members = [new_key if k == old_key else k for k in g.members]
        self._rebuild_index()

    def assign(self, gid: str, camera_keys: list[str]) -> None:
        g = self.groups.get(gid)
        if not g or gid == ALL_CAMERAS_ID:
            return
        for key in camera_keys:
            idx = self._index.setdefault(key, set())
            if gid not in idx:          # O(1)-Dedup über den Index
                g.members.append(key)
                idx.add(gid)
        self.save()

    def unassign(self, gid: str, camera_keys: list[str]) -> None:
        g = self.groups.get(gid)
        if not g or gid == ALL_CAMERAS_ID:
            return
        drop = set(camera_keys)
        g.members = [k for k in g.members if k not in drop]
        for key in camera_keys:
            idx = self._index.get(key)
            if idx:
                idx.discard(gid)
                if not idx:
                    del self._index[key]
        self.save()

    def cameras_in(self, gid: str) -> list[dict]:
        """Resolve a group's cameras from the roster."""
        if gid == ALL_CAMERAS_ID:
            return list(self.roster.values())
        g = self.groups.get(gid)
        if not g:
            return []
        return [self.roster[k] for k in g.members if k in self.roster]

    def groups_of(self, key: str) -> list[str]:
        """Names of the user groups a camera belongs to (excl. 'Alle Kameras')."""
        return [self.groups[gid].name for gid in self._index.get(key, ())
                if gid in self.groups]

    def _forget_one(self, key: str) -> None:
        """Remove a camera from roster + all groups WITHOUT saving."""
        self.roster.pop(key, None)
        for gid in self._index.pop(key, set()):
            g = self.groups.get(gid)
            if g and key in g.members:
                g.members.remove(key)

    def forget(self, key: str) -> None:
        """Remove a camera entirely: from the roster and from every group."""
        self._forget_one(key)
        self.save()

    def forget_many(self, keys: list[str]) -> None:
        """Batch-remove cameras with a single save (statt N Dateischreibvorgängen)."""
        for key in keys:
            self._forget_one(key)
        self.save()
