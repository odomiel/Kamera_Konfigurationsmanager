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

"""The network-free parsing building blocks of the display-only plugins.

Scutum derives model/serial from the reverse-DNS hostname and reads a MAC out of ARP
output; Senstar parses model + version from the device's 404 page and turns its
``DeviceSerial`` into a MAC. These are the bits most likely to break on a new firmware,
and they parse pure strings — so they are tested without touching the network."""

import pathlib
import sys
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from kkm.plugins.scutum import session as scutum
from kkm.plugins.senstar import session as senstar
from kkm.plugins.senstar.plugin import SenstarPlugin


class TestScutumHostname(unittest.TestCase):
    """``_NETCON`` zieht Modellnummer + Geräte-ID aus dem Reverse-DNS-Namen."""

    def test_netcon3_mit_id(self):
        m = scutum._NETCON.match("netcon3-1436520562")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "3")
        self.assertEqual(m.group(2), "1436520562")

    def test_netcon4_ohne_id(self):
        m = scutum._NETCON.match("netcon4")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "4")
        self.assertIn(m.group(2), (None, ""))

    def test_fremder_host_passt_nicht(self):
        self.assertIsNone(scutum._NETCON.match("axis-b8a44f"))


class TestScutumErkennung(unittest.TestCase):
    """``_erkennen`` — Netcon über Hostname-Marker ODER Hersteller-OUI (netzfrei)."""

    def test_hostname_marker_gewinnt(self):
        self.assertEqual(scutum._erkennen("netcon3-1436520562", ""),
                         {"modell": "Netcon 3", "serial": "1436520562"})
        self.assertEqual(scutum._erkennen("netcon4", "")["modell"], "Netcon 4")

    def test_oui_erkennt_auch_ohne_passenden_hostnamen(self):
        """.22/.23 heißen 'enet' bzw. haben keinen PTR — der VS-Vision-OUI greift."""
        self.assertEqual(scutum._erkennen("enet", "74:6A:8F:00:05:78"),
                         {"modell": "Netcon 3", "serial": ""})
        self.assertEqual(scutum._erkennen("", "74:6A:8F:00:05:F4"),
                         {"modell": "Netcon 3", "serial": ""})

    def test_fremder_ssh_host_ist_keine_netcon(self):
        # Ein Raspberry-Pi-OUI ohne netcon-Hostname darf NICHT als Netcon gelten.
        self.assertIsNone(scutum._erkennen("raspberrypi", "B8:27:EB:B4:7F:78"))
        self.assertIsNone(scutum._erkennen("fileserver", "00:11:22:33:44:55"))
        self.assertIsNone(scutum._erkennen("", ""))


class TestScutumMac(unittest.TestCase):
    """``_MAC_RE`` erkennt MAC-Adressen in ARP-Ausgaben (Doppelpunkt oder Strich)."""

    def test_doppelpunkt_und_strich(self):
        self.assertTrue(scutum._MAC_RE.search("… lladdr b8:27:eb:b4:7f:78 DELAY"))
        self.assertTrue(scutum._MAC_RE.search("192.168.0.164  b8-27-eb-b4-7f-78  ether"))

    def test_keine_mac(self):
        self.assertIsNone(scutum._MAC_RE.search("192.168.0.164 kein-eintrag"))


class TestSenstarFingerprint(unittest.TestCase):
    """``_MODELL``/``_FASSUNG`` lesen Modell und Softwarefassung aus der 404-Seite —
    die Version erst NACH der Modellzeile (sonst triggert jquery-ui 1.12.1)."""

    # Reale Anordnung: die jquery-ui-Fassung (1.12.1) steht im <head> VOR der
    # Modellzeile; die Softwarefassung folgt danach. Der ``m.end()``-Offset sorgt
    # dafür, dass nur ab dem Modell gesucht wird — sonst gewönne 1.12.1.
    SEITE = ("<head><script src='jquery-ui.min-1.12.1.js'></script>"
             "<title>Senstar A10D Thin Client</title></head>"
             "<body><div>Version 3.10.0.2726</div></body>")

    def test_modell(self):
        m = senstar._MODELL.search(self.SEITE)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "A10D")

    def test_fassung_erst_nach_dem_modell(self):
        m = senstar._MODELL.search(self.SEITE)
        mf = senstar._FASSUNG.search(self.SEITE, m.end())
        self.assertIsNotNone(mf)
        self.assertEqual(mf.group(1), "3.10.0.2726")


class TestSenstarSerialZuMac(unittest.TestCase):
    """``DeviceSerial`` des Thin Client IST die MAC (Lanner-OUI)."""

    def test_zwoelf_hex_wird_mac(self):
        self.assertEqual(SenstarPlugin._mac_aus_serial("00900B587DA2"),
                         "00:90:0B:58:7D:A2")

    def test_schon_formatiert_bleibt(self):
        self.assertEqual(SenstarPlugin._mac_aus_serial("00:90:0b:58:7d:a2"),
                         "00:90:0B:58:7D:A2")

    def test_kein_mac_muster_unveraendert(self):
        self.assertEqual(SenstarPlugin._mac_aus_serial("ABC123"), "ABC123")
        self.assertEqual(SenstarPlugin._mac_aus_serial(""), "")


if __name__ == "__main__":
    unittest.main()
