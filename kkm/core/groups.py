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
config dir (portable Windows-``.exe``: neben der ausfuehrbaren Datei, sonst
Windows ``%APPDATA%``, unter Linux ``$XDG_CONFIG_HOME``/``~/.config``). There
is one non-deletable, non-renamable group "Alle Kameras" that implicitly contains
every known camera; user-created groups are explicit membership lists keyed by a
stable camera key (MAC/serial).

Per-group online-check settings (enabled + interval) live here too, since the
requirement is a configurable online check *per group*.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import dataclass, field, fields, asdict

from .i18n import t

ALL_CAMERAS_ID = "all"
ALL_CAMERAS_NAME = "Alle Kameras"
# Zweite virtuelle, nicht löschbare Gruppe: alle Kameras im Roster, die (noch)
# keiner Benutzergruppe zugeordnet sind. Ihre Mitgliedschaft wird dynamisch aus
# dem Roster + Index berechnet (keine gespeicherten Mitglieder).
UNGROUPED_ID = "ungrouped"
UNGROUPED_NAME = "Ohne Gruppe"
# IDs der berechneten Sondergruppen (keine echten Mitglieder, kein Zuordnungsziel).
VIRTUAL_GROUP_IDS = (ALL_CAMERAS_ID, UNGROUPED_ID)


def config_dir() -> str:
    if os.name == "nt" and getattr(sys, "frozen", False):
        # Portable Windows-.exe: Konfiguration im Verzeichnis der ausfuehrbaren
        # Datei ablegen (mitnehmbar), nicht in %APPDATA%. Linux bleibt unberuehrt.
        base = os.path.dirname(sys.executable)
    elif os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
            os.path.expanduser("~"), ".config"
        )
    path = os.path.join(base, "kamera_konfigurationsmanager")
    os.makedirs(path, mode=PRIVATE_DIR_MODE, exist_ok=True)
    _harden_permissions(path)
    return path


# Rechte fuer das Config-Verzeichnis und seine Dateien (Tresor, Auto-Entsperr-Token,
# Kameraliste): nur der Eigentuemer darf lesen/schreiben. Ohne das legt Python die
# Dateien gemaess umask meist 0644/0664 an — lesbar fuer jeden lokalen Benutzer.
# Unter Windows greifen POSIX-Rechte nicht (dort schuetzt das Profil/ACL); no-op.
PRIVATE_DIR_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
_hardened: set[str] = set()


def _harden_permissions(path: str) -> None:
    """Setzt einmal pro Prozess 0700 auf *path* und 0600 auf die Dateien darin
    (Nachruesten fuer Installationen, die vor dieser Absicherung angelegt wurden)."""
    if os.name == "nt" or path in _hardened:
        return
    _hardened.add(path)
    try:
        os.chmod(path, PRIVATE_DIR_MODE)
        for name in os.listdir(path):
            full = os.path.join(path, name)
            if os.path.isfile(full) and not os.path.islink(full):
                os.chmod(full, PRIVATE_FILE_MODE)
    except OSError:
        pass   # z. B. fremder Eigentuemer — App laeuft trotzdem weiter


def open_private(path: str, mode: str = "w", encoding: str = "utf-8"):
    """Wie ``open(path, mode)`` zum Schreiben, aber die Datei entsteht mit 0600.

    Auch eine schon vorhandene Datei (z. B. ein liegengebliebenes ``.tmp``) wird
    auf 0600 gesetzt. Gedacht fuer das atomare Muster ``tmp`` + ``os.replace`` —
    ``os.replace`` uebernimmt die Rechte der tmp-Datei."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, PRIVATE_FILE_MODE)
    try:
        if os.name != "nt":
            os.fchmod(fd, PRIVATE_FILE_MODE)
        if "b" in mode:
            return os.fdopen(fd, mode)
        return os.fdopen(fd, mode, encoding=encoding)
    except BaseException:
        os.close(fd)
        raise


def camera_key(camera: dict) -> str:
    """Stable identity of a camera across rescans: MAC/serial, else name+IP."""
    mac = str(camera.get("MAC-Adresse/Seriennummer", "")).strip()
    if mac:
        return mac
    from .camera import get_first_ip
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
        data: dict = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    raise ValueError("kein JSON-Objekt")
            except (OSError, ValueError):
                # Beschädigte Datei darf den Start nicht verhindern — beiseitelegen
                # (nicht löschen!), damit der nächste save() sie nicht überschreibt.
                try:
                    os.replace(self.path, self.path + ".corrupt")
                except OSError:
                    pass
                data = {}
        # Unbekannte Felder ignorieren (Vorwärtskompatibilität: eine neuere Version
        # darf Felder ergänzen, ohne dass ältere Stände hier mit TypeError scheitern).
        known = {f.name for f in fields(Group)}
        self.groups = {}
        for g in data.get("groups", []):
            try:
                self.groups[g["id"]] = Group(
                    **{k: v for k, v in g.items() if k in known})
            except (TypeError, KeyError):
                continue   # einzelner kaputter Eintrag -> überspringen, Rest behalten
        roster = data.get("roster", {})
        self.roster = roster if isinstance(roster, dict) else {}
        # Guarantee the non-deletable "Alle Kameras" group exists.
        if ALL_CAMERAS_ID not in self.groups:
            self.groups[ALL_CAMERAS_ID] = Group(
                id=ALL_CAMERAS_ID, name=ALL_CAMERAS_NAME, deletable=False
            )
        # Zweite Sondergruppe "Ohne Gruppe" (virtuell, nicht löschbar).
        if UNGROUPED_ID not in self.groups:
            self.groups[UNGROUPED_ID] = Group(
                id=UNGROUPED_ID, name=UNGROUPED_NAME, deletable=False
            )
        # Anzeigenamen der virtuellen Gruppen in die aktive UI-Sprache bringen
        # (immer neu setzen, damit ein persistierter Name in alter Sprache nicht
        # hängen bleibt; der Vergleich in der GUI läuft über die IDs, nicht die Namen).
        self.groups[ALL_CAMERAS_ID].name = t(ALL_CAMERAS_NAME)
        self.groups[UNGROUPED_ID].name = t(UNGROUPED_NAME)
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._index = {}
        for gid, g in self.groups.items():
            if gid in VIRTUAL_GROUP_IDS:
                continue
            for key in g.members:
                self._index.setdefault(key, set()).add(gid)

    def save(self) -> None:
        data = {
            "groups": [asdict(g) for g in self.groups.values()],
            "roster": self.roster,
        }
        tmp = self.path + ".tmp"
        with open_private(tmp) as fh:
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
            for fld in ("_firmware", "_model"):
                if not camera.get(fld) and prev.get(fld):
                    camera[fld] = prev[fld]
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

    def merge_camera(self, dup_key: str, into_key: str) -> None:
        """Zwei Identitäten derselben physischen Kamera zusammenführen (z. B.
        generischer ONVIF-Treffer per Geräte-UUID -> Hersteller-Identität per MAC):
        Gruppenzugehörigkeiten wandern zum Ziel (ohne Dubletten), der
        Duplikat-Eintrag verschwindet aus dem Roster. Kein Save — der Aufrufer
        speichert gebündelt."""
        if dup_key == into_key or dup_key not in self.roster:
            return
        for g in self.groups.values():
            if dup_key in g.members:
                g.members = [k for k in g.members if k != dup_key]
                if into_key not in g.members:
                    g.members.append(into_key)
        self.roster.pop(dup_key, None)
        self._rebuild_index()

    def assign(self, gid: str, camera_keys: list[str]) -> None:
        g = self.groups.get(gid)
        if not g or gid in VIRTUAL_GROUP_IDS:
            return
        for key in camera_keys:
            idx = self._index.setdefault(key, set())
            if gid not in idx:          # O(1)-Dedup über den Index
                g.members.append(key)
                idx.add(gid)
        self.save()

    def unassign(self, gid: str, camera_keys: list[str]) -> None:
        g = self.groups.get(gid)
        if not g or gid in VIRTUAL_GROUP_IDS:
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
        if gid == UNGROUPED_ID:
            # Kameras ohne Zuordnung zu einer Benutzergruppe (Index leer/fehlt).
            return [cam for key, cam in self.roster.items()
                    if not self._index.get(key)]
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

    def forget_many(self, keys: list[str]) -> None:
        """Batch-remove cameras with a single save (statt N Dateischreibvorgängen)."""
        for key in keys:
            self._forget_one(key)
        self.save()
