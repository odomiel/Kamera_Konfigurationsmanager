"""Axis mDNS/Zeroconf discovery — extracted from the Discovery tool's CLI core.

This is the vendor-specific *find cameras on the LAN* logic. It is kept separate
from :mod:`kkm.plugins.axis.vapix` (which only changes settings on a known IP) so
the plugin can expose discovery and configuration independently.

``FIELD_NAMES`` is the single source of truth for the base device columns; the GUI
table and exports derive from it, and the manager adds its own columns (group,
online status) on top.
"""

import csv
import time

from zeroconf import ServiceBrowser, Zeroconf

# Base device fields as reported by mDNS. The manager augments each camera dict
# with extra keys (``_group``, ``_online``, ``_vendor``) — those are NOT in here.
FIELD_NAMES = [
    "Name",
    "IP Adresse: Zeroconfig",
    "IP Adresse: Konfiguriert",
    "Port",
    "Hostname",
    "MAC-Adresse/Seriennummer",
]


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


def get_first_ip(camera):
    """First reachable IP of a camera: prefer configured, else zeroconf."""
    for field in ("IP Adresse: Konfiguriert", "IP Adresse: Zeroconfig"):
        ip = str(camera.get(field, "")).split(",")[0].strip()
        if ip:
            return ip
    return ""


def export_results(cameras, output_file, fmt=None, columns=None):
    """Export the camera list as CSV or a plain text table."""
    if columns is None:
        columns = FIELD_NAMES
    if fmt is None:
        fmt = "csv" if output_file.lower().endswith(".csv") else "txt"

    if fmt == "csv":
        with open(output_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns)
            writer.writeheader()
            for cam in cameras:
                writer.writerow({c: cam.get(c, "") for c in columns})
    else:
        # Minimal aligned text table (no prettytable dependency).
        widths = {c: max(len(c), *(len(str(cam.get(c, ""))) for cam in cameras)) if cameras
                  else len(c) for c in columns}
        line = "  ".join(c.ljust(widths[c]) for c in columns)
        rows = [line, "  ".join("-" * widths[c] for c in columns)]
        for cam in cameras:
            rows.append("  ".join(str(cam.get(c, "")).ljust(widths[c]) for c in columns))
        with open(output_file, "w", encoding="utf-8") as fh:
            fh.write("\n".join(rows) + "\n")
