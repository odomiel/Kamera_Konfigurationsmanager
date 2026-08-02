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

from zeroconf import IPVersion, ServiceBrowser, Zeroconf

# Die hier erzeugten Kamera-Dicts folgen der Form von ``kkm.core.camera.FIELD_NAMES``.
# get_first_ip wird bewusst re-exportiert: axis/plugin.py löst die Kamera-IP über
# ``discovery.get_first_ip(camera)`` auf (nicht in diesem Modul selbst benutzt).
from kkm.core.camera import get_first_ip  # noqa: F401  (Re-Export für axis/plugin.py)


class AxisDiscovery:
    """Browses ``_axis-video._tcp.local.`` and collects camera service info."""

    SERVICE_TYPE = "_axis-video._tcp.local."

    def __init__(self):
        try:
            # IPv4 UND IPv6 abfragen (A- + AAAA-Records) — ohne ip_version fragt
            # zeroconf nur IPv4 ab und die Kameras meldeten keine IPv6-Adresse.
            self.zeroconf = Zeroconf(ip_version=IPVersion.All)
        except OSError:
            # Host ohne (nutzbaren) IPv6-Stack -> wie bisher nur IPv4.
            self.zeroconf = Zeroconf()
        self.services = []

    def add_service(self, zeroconf, service_type, name):
        info = zeroconf.get_service_info(service_type, name)
        if info:
            addresses = info.parsed_addresses(IPVersion.V4Only)
            # IPv6: globale Adressen zuerst, Link-Local (fe80::) dahinter.
            ipv6 = sorted(info.parsed_addresses(IPVersion.V6Only),
                          key=lambda a: a.lower().startswith("fe80"))

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
                "IP Adresse: IPv6": ", ".join(ipv6),
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


