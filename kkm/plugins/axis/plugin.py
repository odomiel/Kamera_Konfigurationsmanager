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

from kkm.core.plugins import (VendorPlugin, Credentials, Capability,
                              FirmwareInfo, FirmwareRelease)
from . import vapix
from . import discovery
from . import firmware_repo


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
        Capability.FIRMWARE_CHECK,
        Capability.CONFIG,
        Capability.FACTORY_RESET,
    }

    # Rollen (VAPIX-Benutzer) und ONVIF-Stufen, jeweils hoechstes Recht zuerst —
    # die Dialoge lesen sie von der Plugin-Instanz.
    USER_ROLES = ("administrator", "operator", "viewer")
    ONVIF_LEVELS = ("Administrator", "Operator", "User")

    #: Basis-URL des Firmware-Verzeichnisses (aus den Einstellungen ueberschreibbar,
    #: z. B. auf einen internen Spiegel).
    repo_url: str = firmware_repo.BASE_URL

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

    def parse_user_list(self, path, onvif=False):
        """Parse a CSV/text user list (Name,Password[,Role]) -> list of dicts.

        Raises on format errors (with line numbers) so nothing partial is applied.
        """
        return vapix.parse_user_list(path, onvif=onvif)

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

    # --- firmware lookup (Capability.FIRMWARE_CHECK) ------------------------
    def firmware_updates(self, model, current="", prefer_track=True) -> FirmwareInfo:
        model_dir = firmware_repo.resolve_model(model, self.repo_url)
        vers = firmware_repo.versions(model_dir, self.repo_url)
        latest = firmware_repo.latest_version(model_dir, self.repo_url)
        if latest:
            # Axis' latest/ver.txt ist massgeblich: numerisch hoehere Versionsordner
            # (z. B. ein noch nicht als "latest" freigegebener Patch) werden ignoriert
            # — weder vorgeschlagen noch in der Auswahlliste gezeigt.
            vers = [v for v in vers if not firmware_repo.is_newer(v, latest)]
            # latest/ enthaelt gelegentlich eine Version ohne eigenen Versionsordner.
            if latest not in vers:
                vers = firmware_repo.sort_versions(vers + [latest])
        else:
            latest = vers[0] if vers else ""
        return FirmwareInfo(
            model=model_dir, current=current, versions=vers, latest=latest,
            recommended=firmware_repo.pick_recommended(vers, current, prefer_track) or "",
        )

    def firmware_release(self, model, version="") -> FirmwareRelease:
        model_dir = firmware_repo.resolve_model(model, self.repo_url)
        rel = firmware_repo.release(model_dir, version or None, self.repo_url)
        return FirmwareRelease(model=rel.model, version=rel.version, url=rel.url,
                               filename=rel.filename, size=rel.size,
                               notes_url=rel.notes_url)

    def download_firmware(self, release: FirmwareRelease, progress=None,
                          cancelled=None) -> str:
        rel = firmware_repo.Release(
            model=release.model, version=release.version, url=release.url,
            filename=release.filename, size=release.size, notes_url=release.notes_url)
        return firmware_repo.download(rel, progress=progress, cancelled=cancelled)

    def firmware_cache_size(self) -> int:
        return firmware_repo.cache_size()

    def clear_firmware_cache(self) -> None:
        firmware_repo.clear_cache()

    def parse_config_file(self, path) -> dict:
        return vapix.parse_adm_config(path)

    def write_config_file(self, path, config, selected_params=None,
                          with_profiles=True, with_vmd4=True, selected_profiles=None):
        return vapix.write_adm_config(path, config, selected_params=selected_params,
                                      with_profiles=with_profiles, with_vmd4=with_vmd4,
                                      selected_profiles=selected_profiles)

    def import_config(self, camera, creds: Credentials, cfg_path,
                      selected_params=None, selected_profiles=None, with_vmd4=True):
        ip = self.ip_of(camera)
        config = vapix.parse_adm_config(cfg_path)
        return vapix.apply_adm_config(ip, creds.username, creds.password, config,
                                      selected_params=selected_params,
                                      selected_profiles=selected_profiles,
                                      with_vmd4=with_vmd4, **self._conn(creds))

    def read_config(self, camera, creds: Credentials) -> dict:
        ip = self.ip_of(camera)
        return vapix.read_device_config(ip, creds.username, creds.password,
                                        **self._conn(creds))

    def factory_reset(self, camera, creds: Credentials, keep_ip: bool = True):
        ip = self.ip_of(camera)
        return vapix.factory_default(ip, creds.username, creds.password,
                                     keep_ip=keep_ip, **self._conn(creds))

    def export_config(self, camera, creds: Credentials, out_path,
                      selected_params=None, with_profiles=True, with_vmd4=True):
        config = self.read_config(camera, creds)
        return self.write_config_file(out_path, config,
                                      selected_params=selected_params,
                                      with_profiles=with_profiles,
                                      with_vmd4=with_vmd4)
