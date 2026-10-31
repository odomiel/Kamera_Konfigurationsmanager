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

    def test_netcon2_nur_serie_ohne_trenner(self):
        """Die Netcon 2 heißt ``netcon<lange-serie>`` ohne Trenner — keine Modellnummer."""
        m = scutum._NETCON.match("netcon1793132771")
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "1793132771")
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

    def test_netcon2_hostname_serie_plus_oui(self):
        """Die Netcon 2 (.173): ``netcon<serie>`` ohne Trenner — Modell kommt vom OUI,
        die lange Zahl bleibt Serien-ID (nicht 'Netcon 1793132771')."""
        self.assertEqual(scutum._erkennen("netcon1793132771", "00:04:D9:80:D4:C1"),
                         {"modell": "Netcon 2", "serial": "1793132771"})
        # Auch ohne MAC darf die reine Serien-ID nicht zur Modellnummer werden.
        self.assertEqual(scutum._erkennen("netcon1793132771", ""),
                         {"modell": "Netcon", "serial": "1793132771"})
        # Der Titan-OUI allein (ohne netcon-Hostname) genügt.
        self.assertEqual(scutum._erkennen("", "00:04:D9:12:34:56"),
                         {"modell": "Netcon 2", "serial": ""})

    def test_fremder_ssh_host_ist_keine_netcon(self):
        # Ein Raspberry-Pi-OUI ohne netcon-Hostname UND ohne Netcon-4-Banner darf NICHT
        # als Netcon gelten (Default-Banner ist leer).
        self.assertIsNone(scutum._erkennen("raspberrypi", "B8:27:EB:B4:7F:78"))
        self.assertIsNone(scutum._erkennen("fileserver", "00:11:22:33:44:55"))
        self.assertIsNone(scutum._erkennen("", ""))


class TestScutumNetcon4Pi(unittest.TestCase):
    """Hostnamenlose Netcon 4: Raspberry-Pi-OUI **plus** exaktes Buster-SSH-Banner."""

    BUSTER = scutum._NETCON4_SSH  # "SSH-2.0-OpenSSH_7.9p1 Raspbian-10+deb10u2+rpt1"

    def test_enet_pi_mit_buster_banner_ist_netcon4(self):
        """.22: Reverse-DNS 'enet', RPi-OUI B8:27:EB, exaktes Buster-Banner -> Netcon 4."""
        self.assertEqual(scutum._erkennen("enet", "B8:27:EB:83:4C:AE", self.BUSTER),
                         {"modell": "Netcon 4", "serial": ""})

    def test_neuerer_pi_oui_zaehlt_auch(self):
        self.assertEqual(scutum._erkennen("", "DC:A6:32:11:22:33", self.BUSTER)["modell"],
                         "Netcon 4")

    def test_pi_ohne_exaktes_banner_ist_keine_netcon(self):
        # Falsches/neueres Banner oder kein Banner -> kein Treffer (kein normaler Pi).
        self.assertIsNone(scutum._erkennen("enet", "B8:27:EB:83:4C:AE",
                                           "SSH-2.0-OpenSSH_9.2p1 Debian-2"))
        self.assertIsNone(scutum._erkennen("enet", "B8:27:EB:83:4C:AE", ""))
        self.assertFalse(scutum._ist_netcon4_pi("B8:27:EB:83:4C:AE", "SSH-2.0-OpenSSH_8.4p1"))

    def test_buster_banner_ohne_pi_oui_ist_keine_netcon(self):
        # Exaktes Banner, aber fremder OUI (kein Raspberry Pi) -> kein Treffer.
        self.assertIsNone(scutum._erkennen("enet", "00:11:22:33:44:55", self.BUSTER))

    def test_netcon4_hostname_braucht_kein_banner(self):
        # Trägt der Hostname die Modellnummer, zählt er unabhängig vom Banner.
        self.assertEqual(scutum._erkennen("netcon4", "B8:27:EB:00:00:00", "")["modell"],
                         "Netcon 4")


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

    def test_marke_und_modell(self):
        m = senstar._MODELL.search(self.SEITE)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "Senstar")   # Marke
        self.assertEqual(m.group(2), "A10D")       # Modell

    def test_fassung_erst_nach_dem_modell(self):
        m = senstar._MODELL.search(self.SEITE)
        mf = senstar._FASSUNG.search(self.SEITE, m.end())
        self.assertIsNotNone(mf)
        self.assertEqual(mf.group(1), "3.10.0.2726")

    def test_aeltere_firmware_heisst_noch_aimetis(self):
        """Firmware vor der Senstar-Übernahme trägt den Markennamen Aimetis."""
        seite = ("<head><script src='jquery-ui.min-1.12.1.js'></script>"
                 "<title>Aimetis Thin Client</title></head>"
                 "<body>Aimetis A10D Thin Client<br />Version 1.2.1.515</body>")
        m = senstar._MODELL.search(seite)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), "Aimetis")
        self.assertEqual(m.group(2), "A10D")
        mf = senstar._FASSUNG.search(seite, m.end())
        self.assertEqual(mf.group(1), "1.2.1.515")


class TestSenstarLegacyTLS(unittest.TestCase):
    """Der nachgiebige TLS-Context macht ältere Firmware (nur veraltetes TLS)
    erreichbar — ohne auf Klartext-HTTP auszuweichen."""

    def test_legacy_context_erlaubt_altes_tls(self):
        import ssl
        c = senstar._SSL_LEGACY
        self.assertEqual(c.verify_mode, ssl.CERT_NONE)
        self.assertLessEqual(c.minimum_version, ssl.TLSVersion.TLSv1)
        if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
            self.assertTrue(c.options & ssl.OP_LEGACY_SERVER_CONNECT)

    def test_strikter_context_bleibt_streng(self):
        import ssl
        # Der normale Context wird NICHT auf Alt-TLS herabgesetzt (nur der Legacy-
        # Context tut das); er behält das strenge Minimum des create_default_context.
        self.assertNotEqual(senstar._SSL.minimum_version, ssl.TLSVersion.TLSv1)


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
