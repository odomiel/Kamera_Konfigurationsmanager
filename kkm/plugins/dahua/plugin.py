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

"""Dahua plugin — adapts the HTTP-API/DHIP modules to ``VendorPlugin``.

Thin wrapper like the Axis/Hikvision plugins: the work lives in
:mod:`kkm.plugins.dahua.httpapi` (Dahua HTTP API over Digest, stdlib-only) and
:mod:`kkm.plugins.dahua.discovery` (DHIP UDP discovery). ONVIF users go through the
**shared** ONVIF SOAP client (:mod:`kkm.plugins.onvif.soap`) — a Dahua device speaks
standard ONVIF for that part.

**Experimental** (``experimental = True``): the HTTP-API/DHIP paths follow the
(semi-public) Dahua documentation but are not yet verified against real hardware, so
the plugin is flagged in the plugin manager and shipped **off by default**.
Capabilities mirror `DAHUA_PLUGIN_RECHERCHE.md`: no ``FIRMWARE_CHECK`` (no open
firmware repo) and no ``CONFIG`` (a param-based export via ``configManager`` is
possible but has no fleet-template standard — deferred).

One Dahua bonus: this plugin also covers the many **Dahua-OEM rebrands** — notably
the **Honeywell Performance Series** and Amcrest.
"""

from __future__ import annotations

from kkm.core.camera import get_first_ip
from kkm.core.plugins import VendorPlugin, Credentials, Capability
from kkm.plugins.onvif import soap   # ONVIF-Benutzer laufen ueber den Standard-Client
from . import httpapi
from . import discovery


class DahuaPlugin(VendorPlugin):
    id = "dahua"
    name = "Dahua"
    experimental = True
    capabilities = {
        Capability.DISCOVER,
        Capability.ONLINE_CHECK,
        Capability.DEVICE_INFO,
        Capability.SET_IP,
        Capability.USERS,
        Capability.ONVIF_USERS,
        Capability.FIRMWARE,
        Capability.FACTORY_RESET,
    }

    USER_ROLES = httpapi.USER_ROLES
    ONVIF_LEVELS = ("Administrator", "Operator", "User")

    # --- helpers ------------------------------------------------------------
    @staticmethod
    def _conn(creds: Credentials) -> dict:
        return {"scheme": creds.scheme, "port": creds.port, "timeout": creds.timeout}

    @staticmethod
    def ip_of(camera: dict) -> str:
        return get_first_ip(camera)

    def _onvif_auth(self, camera: dict, creds: Credentials):
        """URL + Zeitversatz fuer die ONVIF-Benutzerverwaltung (uhrzeitabhaengig)."""
        ip = self.ip_of(camera)
        if not ip:
            raise soap.OnvifError("Kamera hat keine IP-Adresse.")
        scheme = creds.scheme if creds.scheme in ("http", "https") else "http"
        url = soap.device_url(ip, scheme, creds.port)
        offset = soap.time_offset(url, timeout=min(creds.timeout, 5))
        return url, offset

    # --- discovery & status -------------------------------------------------
    def discover(self, timeout: int = 10) -> list[dict]:
        cams = discovery.discover(timeout=timeout)
        for cam in cams:
            cam["_vendor"] = self.id
        return cams

    def check_online(self, camera: dict, creds: Credentials | None = None) -> bool:
        ip = self.ip_of(camera)
        if not ip:
            return False
        creds = creds or Credentials()
        try:
            return httpapi.is_online(ip, scheme=creds.scheme, port=creds.port,
                                     timeout=min(creds.timeout, 5))
        except Exception:  # noqa: BLE001 - offline ist kein Fehlerfall
            return False

    def device_info(self, camera: dict, creds: Credentials) -> dict:
        ip = self.ip_of(camera)
        return httpapi.get_device_info(ip, creds.username, creds.password,
                                       **self._conn(creds))

    def is_unconfigured(self, camera: dict, creds: Credentials | None = None) -> bool:
        ip = self.ip_of(camera)
        if not ip:
            return False
        creds = creds or Credentials()
        try:
            return httpapi.is_unconfigured(ip, scheme=creds.scheme, port=creds.port,
                                           timeout=min(creds.timeout, 5))
        except Exception:  # noqa: BLE001
            return False

    # --- actions ------------------------------------------------------------
    def set_static_ip(self, camera, creds: Credentials, new_ip, mask, gateway):
        ip = self.ip_of(camera)
        return httpapi.set_static_ip(ip, creds.username, creds.password,
                                     new_ip, mask, gateway, **self._conn(creds))

    def set_dhcp(self, camera, creds: Credentials):
        ip = self.ip_of(camera)
        return httpapi.set_dhcp(ip, creds.username, creds.password, **self._conn(creds))

    def add_user(self, camera, creds: Credentials, new_user, new_password,
                 role="viewer", factory=False):
        ip = self.ip_of(camera)
        return httpapi.add_user(ip, creds.username, creds.password, new_user,
                                new_password, role=role, **self._conn(creds))

    def set_user_password(self, camera, creds: Credentials, target_user, new_password):
        ip = self.ip_of(camera)
        return httpapi.set_user_password(ip, creds.username, creds.password,
                                         target_user, new_password, **self._conn(creds))

    def add_onvif_user(self, camera, creds: Credentials, new_user, new_password,
                       level="Administrator"):
        url, offset = self._onvif_auth(camera, creds)
        return soap.create_user(url, creds.username, creds.password, offset,
                                new_user, new_password, level, creds.timeout)

    def set_onvif_user_password(self, camera, creds: Credentials, target_user,
                                new_password, level="Administrator"):
        url, offset = self._onvif_auth(camera, creds)
        return soap.set_user(url, creds.username, creds.password, offset,
                             target_user, new_password, level, creds.timeout)

    def upgrade_firmware(self, camera, creds: Credentials, firmware_path,
                         factory_default=False):
        ip = self.ip_of(camera)
        return httpapi.upgrade_firmware(ip, creds.username, creds.password,
                                        firmware_path, **self._conn(creds))

    def factory_reset(self, camera, creds: Credentials, keep_ip: bool = True):
        ip = self.ip_of(camera)
        return httpapi.factory_reset(ip, creds.username, creds.password,
                                     keep_ip=keep_ip, **self._conn(creds))
