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

"""Axis mDNS/Zeroconf discovery — extracted from the Discovery tool's CLI core.

This is the vendor-specific *find cameras on the LAN* logic. It is kept separate
from :mod:`kkm.plugins.axis.vapix` (which only changes settings on a known IP) so
the plugin can expose discovery and configuration independently.

The camera dict itself is *not* Axis-specific: its shape (``FIELD_NAMES``) and the
helpers on it live in :mod:`kkm.core.camera` and are re-exported here, because that
is where a plugin's discovery reaches for them.
"""

import time

from zeroconf import ServiceBrowser, Zeroconf

from kkm.core.camera import FIELD_NAMES, get_first_ip, export_results  # noqa: F401


def convert_bytearray_to_ipv4(bytearray_address):
    return ".".join(str(byte) for byte in bytearray_address)


class AxisDiscovery:
    """Browses ``_axis-video._tcp.local.`` and collects camera service info."""

    SERVICE_TYPE = "_axis-video._tcp.local."

    def __init__(self):
        self.zeroconf = Zeroconf()
        self.services = []

    def on_service_state_change(self, zeroconf, service_type, name, state_change):
        if state_change is Zeroconf.StateChange.Added:
            self.add_service(zeroconf, service_type, name)

    def add_service(self, zeroconf, service_type, name):
        info = zeroconf.get_service_info(service_type, name)
        if info:
            addresses = [convert_bytearray_to_ipv4(a) for a in info.addresses]

            name = name.replace("._axis-video._tcp.local.", "")
            # Serial/MAC suffix stripped -> model name only
            # (mDNS name is e.g. "AXIS M7001 - ACCC8E07ADC9").
            name = name.rsplit(" - ", 1)[0].strip()

            mac_address = info.properties.get(b"macaddress", b"").decode("utf-8")

            zeroconf_ips = [a for a in addresses if a.startswith("169.254.")]
            configured_ips = [a for a in addresses if not a.startswith("169.254.")]

            self.services.append({
                "Name": name,
                "IP Adresse: Zeroconfig": ", ".join(zeroconf_ips),
                "IP Adresse: Konfiguriert": ", ".join(configured_ips),
                "Port": info.port,
                "Hostname": info.server,
                "MAC-Adresse/Seriennummer": mac_address,
            })

    def remove_service(self, zeroconf, service_type, name):
        pass

    def update_service(self, zeroconf, service_type, name):
        pass

    def start(self):
        ServiceBrowser(self.zeroconf, self.SERVICE_TYPE, listener=self)

    def search(self, timeout=10):
        time.sleep(timeout)

    def stop(self):
        self.zeroconf.close()


def discover_axis_cameras(timeout=10):
    """Blocking LAN scan. Returns a list of camera dicts (keys = FIELD_NAMES)."""
    discovery = AxisDiscovery()
    discovery.start()
    discovery.search(timeout)
    discovery.stop()
    return discovery.services


