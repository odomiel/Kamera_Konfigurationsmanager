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

"""Axis plugin — adapts the copied VAPIX/discovery modules to ``VendorPlugin``.

This is intentionally a thin wrapper: all the heavy vendor logic lives in
:mod:`kkm.plugins.axis.vapix` (copied verbatim from the Discovery tool and
maintained here independently). The wrapper only:

- maps the generic ``VendorPlugin`` calls onto VAPIX functions,
- resolves a camera dict to its IP via :func:`discovery.get_first_ip`,
- translates ``Credentials`` into VAPIX keyword arguments.

Adding a second manufacturer later means writing a sibling module like this one;
nothing in :mod:`kkm.core` or :mod:`kkm.gui` changes.
"""

from __future__ import annotations

from kkm.core.plugins import VendorPlugin, Credentials, Capability
from . import vapix
from . import discovery


class AxisPlugin(VendorPlugin):
    id = "axis"
    name = "Axis"
    capabilities = {
        Capability.DISCOVER,
        Capability.ONLINE_CHECK,
        Capability.DEVICE_INFO,
        Capability.SET_IP,
        Capability.USERS,
        Capability.ONVIF_USERS,
        Capability.FIRMWARE,
        Capability.CONFIG,
        Capability.FACTORY_RESET,
    }

    # --- helpers ------------------------------------------------------------
    @staticmethod
    def _conn(creds: Credentials) -> dict:
        return {"scheme": creds.scheme, "port": creds.port, "timeout": creds.timeout}

    @staticmethod
    def ip_of(camera: dict) -> str:
        return discovery.get_first_ip(camera)

    # --- discovery & status -------------------------------------------------
    def discover(self, timeout: int = 10) -> list[dict]:
        cams = discovery.discover_axis_cameras(timeout=timeout)
        for cam in cams:
            cam["_vendor"] = self.id
        return cams

    def check_online(self, camera: dict, creds: Credentials | None = None) -> bool:
        ip = self.ip_of(camera)
        if not ip:
            return False
        creds = creds or Credentials()
        try:
            # Echte Erreichbarkeit: jede HTTP(S)-Antwort (auch 401) = online,
            # nur Verbindungs-/Timeout-Fehler = offline.
            return vapix.is_online(ip, scheme=creds.scheme, port=creds.port,
                                   timeout=min(creds.timeout, 5))
        except Exception:
            return False

    def device_info(self, camera: dict, creds: Credentials) -> dict:
        ip = self.ip_of(camera)
        return vapix.get_device_info(ip, creds.username, creds.password,
                                     **self._conn(creds))

    def is_unconfigured(self, camera: dict, creds: Credentials | None = None) -> bool:
        ip = self.ip_of(camera)
        if not ip:
            return False
        creds = creds or Credentials()
        try:
            # Werksneu: unauthentifizierter pwdgrp.cgi-Aufruf liefert 200 (kein
            # Passwort gesetzt); konfiguriert -> 401. Kurzes Timeout genügt.
            return vapix.is_unconfigured(ip, scheme=creds.scheme, port=creds.port,
                                         timeout=min(creds.timeout, 5))
        except Exception:
            return False

    # --- actions (called by the front-view buttons via plugin dialogs) ------
    def set_static_ip(self, camera, creds: Credentials, new_ip, mask, gateway):
        ip = self.ip_of(camera)
        return vapix.set_static_ip(ip, creds.username, creds.password,
                                   new_ip, mask, gateway, **self._conn(creds))

    def set_dhcp(self, camera, creds: Credentials):
        ip = self.ip_of(camera)
        return vapix.set_dhcp(ip, creds.username, creds.password, **self._conn(creds))

    @staticmethod
    def next_ip(ip_str, step=1):
        """IPv4 helper for the sequential-assignment mode. Raises on invalid input."""
        return vapix.next_ip(ip_str, step)

    # Roles offered in the user dialog (highest to lowest privilege).
    USER_ROLES = ("administrator", "operator", "viewer")

    def add_user(self, camera, creds: Credentials, new_user, new_password,
                 role="viewer", factory=False):
        ip = self.ip_of(camera)
        return vapix.add_or_set_user(ip, creds.username, creds.password,
                                     new_user, new_password, role=role,
                                     factory=factory, **self._conn(creds))

    def set_user_password(self, camera, creds: Credentials, target_user, new_password):
        ip = self.ip_of(camera)
        return vapix.set_user_password(ip, creds.username, creds.password,
                                       target_user, new_password, **self._conn(creds))

    @staticmethod
    def parse_user_list(path, onvif=False):
        """Parse a CSV/text user list (Name,Password[,Role]) -> list of dicts.

        Raises on format errors (with line numbers) so nothing partial is applied.
        """
        return vapix.parse_user_list(path, onvif=onvif)

    # ONVIF user levels (highest to lowest privilege).
    ONVIF_LEVELS = ("Administrator", "Operator", "User")

    def add_onvif_user(self, camera, creds: Credentials, new_user, new_password,
                       level="Administrator"):
        ip = self.ip_of(camera)
        return vapix.add_onvif_user(ip, creds.username, creds.password,
                                    new_user, new_password, level=level,
                                    **self._conn(creds))

    def set_onvif_user_password(self, camera, creds: Credentials, target_user,
                                new_password, level="Administrator"):
        ip = self.ip_of(camera)
        return vapix.set_onvif_user_password(ip, creds.username, creds.password,
                                             target_user, new_password, level=level,
                                             **self._conn(creds))

    def upgrade_firmware(self, camera, creds: Credentials, firmware_path,
                         factory_default=False):
        ip = self.ip_of(camera)
        return vapix.upgrade_firmware(ip, creds.username, creds.password,
                                      firmware_path, factory_default=factory_default,
                                      **self._conn(creds))

    def import_config(self, camera, creds: Credentials, cfg_path):
        ip = self.ip_of(camera)
        config = vapix.parse_adm_config(cfg_path)
        return vapix.apply_adm_config(ip, creds.username, creds.password,
                                      config, **self._conn(creds))

    def read_config(self, camera, creds: Credentials) -> dict:
        ip = self.ip_of(camera)
        return vapix.read_device_config(ip, creds.username, creds.password,
                                        **self._conn(creds))

    def factory_reset(self, camera, creds: Credentials, keep_ip: bool = True):
        ip = self.ip_of(camera)
        return vapix.factory_default(ip, creds.username, creds.password,
                                     keep_ip=keep_ip, **self._conn(creds))

    def export_config(self, camera, creds: Credentials, out_path,
                      selected_params=None, with_profiles=True):
        config = self.read_config(camera, creds)
        return vapix.write_adm_config(out_path, config,
                                      selected_params=selected_params,
                                      with_profiles=with_profiles)
