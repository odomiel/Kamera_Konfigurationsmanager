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

"""Vendor-agnostic core: plugin API, group store, password vault."""

from .camera import (FIELD_NAMES, get_first_ip, next_ip, version_tuple,
                     export_results, looks_like_zip)
from .plugins import (VendorPlugin, PluginRegistry, Credentials, Capability,
                      FirmwareInfo, FirmwareRelease)
from .groups import (GroupStore, Group, ALL_CAMERAS_ID, UNGROUPED_ID,
                     VIRTUAL_GROUP_IDS, camera_key)
from .vault import PasswordVault, VaultLocked, VaultError
from .settings import AppSettings
from .i18n import t, set_language, get_language, language_label, LANGUAGES
from . import certpin

__all__ = [
    "t", "set_language", "get_language", "language_label", "LANGUAGES",
    "VendorPlugin", "PluginRegistry", "Credentials", "Capability",
    "FirmwareInfo", "FirmwareRelease",
    "FIELD_NAMES", "get_first_ip", "next_ip", "version_tuple", "export_results",
    "looks_like_zip",
    "GroupStore", "Group", "ALL_CAMERAS_ID", "UNGROUPED_ID",
    "VIRTUAL_GROUP_IDS", "camera_key",
    "PasswordVault", "VaultLocked", "VaultError",
    "AppSettings", "certpin",
]
