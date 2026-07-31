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

"""Generic ONVIF plugin — one plugin for every manufacturer that speaks the standard.

Unlike the Axis plugin this one is not tied to a vendor, so it only offers what the
ONVIF *Device Management* service actually standardises:

- ``DISCOVER``      WS-Discovery probe
- ``ONLINE_CHECK``  GetSystemDateAndTime (works without credentials)
- ``DEVICE_INFO``   GetDeviceInformation
- ``SET_IP``        SetNetworkInterfaces (+ SetNetworkDefaultGateway)
- ``ONVIF_USERS``   CreateUsers / SetUser
- ``FACTORY_RESET`` SetSystemFactoryDefault

Deliberately absent:

- **CONFIG** — ONVIF has no parameter template. ``GetSystemBackup``/``RestoreSystem``
  return an opaque vendor blob for *that one device*, not something to roll out across
  a fleet, which is the whole point of the Axis config dialog.
- **FIRMWARE** — ``UpgradeSystemFirmware`` / ``StartFirmwareUpgrade`` are optional in
  the spec and unevenly implemented; pushing firmware through a shaky path is the most
  destructive thing one can do to a camera, so it is left out until asked for.
- **USERS** — the standard knows exactly *one* user list, and that is the ONVIF one.
  A separate "device user" (as Axis has via VAPIX) does not exist here.
- **FIRMWARE_CHECK** — no standardised firmware repository exists.

The GUI greys the missing actions out on its own; nothing else is needed for that.
"""

from __future__ import annotations

from kkm.core.camera import get_first_ip
from kkm.core.plugins import VendorPlugin, Credentials, Capability
from kkm.core.i18n import t
from . import discovery
from . import soap


class OnvifPlugin(VendorPlugin):
    id = "onvif"
    name = "ONVIF (generisch)"
    default_username = "admin"   # die meisten ONVIF-Kameras; Axis (root) hat ein eigenes Plugin
    #: Herstellerneutral — findet auch Geraete, fuer die es ein eigenes Plugin gibt.
    #: Die Suche im Hauptfenster bevorzugt darum das Hersteller-Plugin (s. app.py).
    generic = True
    capabilities = {
        Capability.DISCOVER,
        Capability.ONLINE_CHECK,
        Capability.DEVICE_INFO,
        Capability.SET_IP,
        Capability.ONVIF_USERS,
        Capability.FACTORY_RESET,
    }

    # ONVIF-Stufen, hoechstes Recht zuerst (der Dialog liest sie hier).
    ONVIF_LEVELS = ("Administrator", "Operator", "User")

    # --- helpers ------------------------------------------------------------
    @staticmethod
    def _url(camera: dict, creds: Credentials | None = None) -> str:
        """Endpunkt des Device-Service. Das per WS-Discovery gemeldete XAddr gewinnt,
        weil manche Geraete einen abweichenden Port oder Pfad nutzen."""
        creds = creds or Credentials()
        ip = get_first_ip(camera)
        if not ip:
            raise soap.OnvifError(t("Kamera hat keine IP-Adresse."))
        scheme = creds.scheme if creds.scheme in ("http", "https") else "http"
        return soap.device_url(ip, scheme, creds.port,
                               xaddr=camera.get("_onvif_xaddr", ""))

    def _auth(self, camera: dict, creds: Credentials):
        """URL + Zeitversatz — jeder authentifizierte Aufruf braucht beides."""
        url = self._url(camera, creds)
        offset = soap.time_offset(url, timeout=min(creds.timeout, 5))
        return url, offset

    def _interface_token(self, url, creds: Credentials, offset) -> str:
        ifaces = soap.network_interfaces(url, creds.username, creds.password, offset,
                                         creds.timeout)
        if not ifaces:
            raise soap.OnvifError(t("Keine Netzwerkschnittstelle gemeldet."))
        return ifaces[0]["token"]

    # --- discovery & status -------------------------------------------------
    def discover(self, timeout: int = 10) -> list[dict]:
        cams = discovery.discover(timeout=timeout)
        for cam in cams:
            cam["_vendor"] = self.id
        return cams

    def check_online(self, camera: dict, creds: Credentials | None = None) -> bool:
        creds = creds or Credentials()
        try:
            # GetSystemDateAndTime ist laut Spec ohne Anmeldung erreichbar -> ideal
            # als Lebenszeichen, auch wenn die Zugangsdaten fehlen.
            return soap.system_time(self._url(camera, creds),
                                    timeout=min(creds.timeout, 5)) is not None
        except Exception:  # noqa: BLE001 - offline ist kein Fehlerfall
            return False

    def device_info(self, camera: dict, creds: Credentials) -> dict:
        url, offset = self._auth(camera, creds)
        return soap.device_information(url, creds.username, creds.password, offset,
                                       creds.timeout)

    # --- actions ------------------------------------------------------------
    def set_static_ip(self, camera, creds: Credentials, new_ip, mask, gateway):
        url, offset = self._auth(camera, creds)
        token = self._interface_token(url, creds, offset)
        return soap.set_static_ip(url, creds.username, creds.password, offset, token,
                                  new_ip, mask, gateway, creds.timeout)

    def set_dhcp(self, camera, creds: Credentials):
        url, offset = self._auth(camera, creds)
        token = self._interface_token(url, creds, offset)
        return soap.set_dhcp(url, creds.username, creds.password, offset, token,
                             creds.timeout)

    def add_onvif_user(self, camera, creds: Credentials, new_user, new_password,
                       level="Administrator"):
        url, offset = self._auth(camera, creds)
        return soap.create_user(url, creds.username, creds.password, offset,
                                new_user, new_password, level, creds.timeout)

    def set_onvif_user_password(self, camera, creds: Credentials, target_user,
                                new_password, level="Administrator"):
        url, offset = self._auth(camera, creds)
        return soap.set_user(url, creds.username, creds.password, offset,
                             target_user, new_password, level, creds.timeout)

    def factory_reset(self, camera, creds: Credentials, keep_ip: bool = True):
        # ONVIF: Soft behaelt die Netzwerkeinstellungen, Hard setzt alles zurueck.
        url, offset = self._auth(camera, creds)
        return soap.factory_default(url, creds.username, creds.password, offset,
                                    hard=not keep_ip, timeout=creds.timeout)
