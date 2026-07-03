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

"""Vendor plugin interface and registry.

A *plugin* encapsulates everything vendor-specific: how to discover devices, read
their info, check whether they are online, and apply settings (IP, users, ONVIF
users, firmware, configuration import/export). The GUI talks only to this
interface, never to a vendor SDK directly — so adding a manufacturer later means
writing one new ``VendorPlugin`` subclass and registering it.

The Axis plugin (:mod:`kkm.plugins.axis.plugin`) implements this by wrapping the
copied VAPIX/discovery modules.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Credentials:
    """Admin access data for a camera write operation."""
    username: str = "root"
    password: str = ""
    scheme: str = "auto"          # auto | https | http
    port: int | None = None
    timeout: int = 10


class Capability:
    """Named operations a plugin may support. The GUI greys out unsupported ones."""
    DISCOVER = "discover"
    ONLINE_CHECK = "online_check"
    DEVICE_INFO = "device_info"
    SET_IP = "set_ip"
    USERS = "users"
    ONVIF_USERS = "onvif_users"
    FIRMWARE = "firmware"
    CONFIG = "config"
    FACTORY_RESET = "factory_reset"


# A progress callback receives (ip, ok, message) per camera for live result logs.
ProgressFn = Callable[[str, bool, str], None]


class VendorPlugin(abc.ABC):
    """Base class for all manufacturer plugins."""

    #: stable identifier used in settings/persistence, e.g. "axis"
    id: str = ""
    #: human-readable name shown in the plugin manager
    name: str = ""
    #: set of Capability.* this plugin implements
    capabilities: set[str] = set()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    # --- discovery & status -------------------------------------------------
    @abc.abstractmethod
    def discover(self, timeout: int = 10) -> list[dict]:
        """Scan the LAN and return camera dicts (must include the base fields)."""

    @abc.abstractmethod
    def check_online(self, camera: dict, creds: Credentials | None = None) -> bool:
        """Return True if the camera currently answers."""

    def device_info(self, camera: dict, creds: Credentials) -> dict:
        """Read extended info (model, firmware, serial). Optional."""
        raise NotImplementedError

    def is_unconfigured(self, camera: dict, creds: Credentials | None = None) -> bool:
        """True, wenn sich die Kamera noch im Auslieferungszustand befindet (kein
        Passwort gesetzt, Ersteinrichtung nötig). Optional; Standard: False."""
        return False

    def factory_reset(self, camera: dict, creds: Credentials, keep_ip: bool = True):
        """Setzt die Kamera auf Werkseinstellungen zurück. ``keep_ip`` erhält die
        Netzwerk-/IP-Einstellungen. Nur verfügbar, wenn das Plugin
        ``Capability.FACTORY_RESET`` meldet."""
        raise NotImplementedError

    # --- configuration actions ---------------------------------------------
    # These mirror the Discovery tool's "Kameraeinstellungen" tabs, which become
    # front-view toolbar buttons. Each acts on the selected cameras; per-camera
    # outcomes are reported via ``progress``. Concrete signatures are defined by
    # the plugin; the GUI dialogs are also plugin-provided (see ``action_dialogs``).
    def action_dialogs(self) -> dict[str, type]:
        """Map Capability.* -> a Toplevel dialog class for that action. Optional."""
        return {}


@dataclass
class PluginRegistry:
    """Holds available plugins and their enabled/disabled state."""
    _plugins: dict[str, VendorPlugin] = field(default_factory=dict)
    _enabled: set[str] = field(default_factory=set)

    def register(self, plugin: VendorPlugin, enabled: bool = True) -> None:
        self._plugins[plugin.id] = plugin
        if enabled:
            self._enabled.add(plugin.id)

    def all(self) -> list[VendorPlugin]:
        return list(self._plugins.values())

    def enabled(self) -> list[VendorPlugin]:
        return [p for pid, p in self._plugins.items() if pid in self._enabled]

    def get(self, plugin_id: str) -> VendorPlugin | None:
        return self._plugins.get(plugin_id)

    def is_enabled(self, plugin_id: str) -> bool:
        return plugin_id in self._enabled

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        if plugin_id not in self._plugins:
            return
        if enabled:
            self._enabled.add(plugin_id)
        else:
            self._enabled.discard(plugin_id)

    def enabled_ids(self) -> list[str]:
        return sorted(self._enabled)
