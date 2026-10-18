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

"""Roster identity and the de-duplication of re-discovered devices.

Covers the camera-key rules, ``GroupStore`` rekey/merge, and the post-search merge of
MAC-less rediscoveries — including the regression where a hit was wrongly merged into a
*different* vendor's entry that happened to share the (DHCP-reassigned) IP.
"""

import os
import pathlib
import sys
import tempfile
import unittest
from types import SimpleNamespace

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))


class _DedupBasis(unittest.TestCase):
    """Gemeinsames Gerüst: isolierte Konfig + echter GroupStore + Registry."""

    def setUp(self):
        self._cfg = tempfile.TemporaryDirectory()
        self.addCleanup(self._cfg.cleanup)
        os.environ["XDG_CONFIG_HOME"] = self._cfg.name

        from kkm.core.groups import GroupStore
        from kkm.plugins import build_registry
        self.store = GroupStore()
        self.store.load()
        self.registry = build_registry()

    def _fenster(self):
        """Ein Fake-MainWindow: nur die Felder, die die Merge-Methoden anfassen."""
        from kkm.gui.app import MainWindow
        fake = SimpleNamespace(store=self.store, _cam_creds={}, vault=None,
                               registry=self.registry)
        fake._transfer_creds = lambda o, n: MainWindow._transfer_creds(fake, o, n)
        fake._merge_rediscovered_duplicates = \
            lambda disc: MainWindow._merge_rediscovered_duplicates(fake, disc)
        return fake


class TestCameraKey(_DedupBasis):
    def test_mac_ist_die_identitaet(self):
        from kkm.core.groups import camera_key
        cam = {"Name": "X", "IP Adresse: Konfiguriert": "192.168.0.5",
               "MAC-Adresse/Seriennummer": "AA:BB:CC:DD:EE:FF"}
        self.assertEqual(camera_key(cam), "AA:BB:CC:DD:EE:FF")

    def test_ohne_mac_name_und_ip(self):
        from kkm.core.groups import camera_key
        cam = {"Name": "Netcon 4", "IP Adresse: Konfiguriert": "192.168.0.164",
               "MAC-Adresse/Seriennummer": ""}
        self.assertEqual(camera_key(cam), "Netcon 4@192.168.0.164")


class TestGroupStoreMerge(_DedupBasis):
    def test_rekey_zieht_roster_und_gruppen_mit(self):
        from kkm.core.groups import Group
        self.store.roster["alt"] = {"Name": "A"}
        self.store.groups["g"] = Group(id="g", name="G", members=["alt"])
        self.store.rekey_camera("alt", "neu")
        self.assertIn("neu", self.store.roster)
        self.assertNotIn("alt", self.store.roster)
        self.assertEqual(self.store.groups["g"].members, ["neu"])

    def test_merge_fuehrt_duplikat_ins_ziel(self):
        from kkm.core.groups import Group
        self.store.roster["dup"] = {"Name": "D"}
        self.store.roster["ziel"] = {"Name": "Z"}
        self.store.groups["g"] = Group(id="g", name="G", members=["dup"])
        self.store.merge_camera("dup", "ziel")
        self.assertNotIn("dup", self.store.roster)
        self.assertIn("ziel", self.store.roster)
        self.assertEqual(self.store.groups["g"].members, ["ziel"])


class TestRediscoveredMerge(_DedupBasis):
    """Der Kern — MAC-lose Wiederfunde (Senstar/Scutum/ONVIF)."""

    def _netcon_treffer(self, ip="192.168.0.164"):
        from kkm.core.camera import FIELD_NAMES
        cam = {n: "" for n in FIELD_NAMES}
        cam.update({"Name": "netcon4", "IP Adresse: Konfiguriert": ip,
                    "_vendor": "scutum", "_model": "Netcon 4", "_online": True})
        return cam

    def test_wiederfund_geht_in_bestehende_mac_identitaet(self):
        from kkm.core.groups import camera_key
        mac_cam = {"Name": "netcon4", "IP Adresse: Konfiguriert": "192.168.0.164",
                   "_vendor": "scutum", "MAC-Adresse/Seriennummer": "B8:27:EB:B4:7F:78",
                   "_online": False}
        mac_key = camera_key(mac_cam)
        self.store.roster[mac_key] = mac_cam
        hit = self._netcon_treffer()
        self.store.roster[camera_key(hit)] = hit  # wie remember_all
        n, ziele = self._fenster()._merge_rediscovered_duplicates([hit])
        self.assertEqual(n, 1)
        self.assertNotIn(camera_key(hit), self.store.roster)   # Name@IP-Dup weg
        self.assertIn(mac_key, self.store.roster)              # MAC-Identität bleibt
        self.assertTrue(self.store.roster[mac_key]["_online"]) # Online wandert mit

    def test_kein_merge_in_fremden_hersteller_auf_gleicher_ip(self):
        """b6/b7-Regression: eine Hikvision mit (veralteter) gleicher IP darf den
        Scutum-Treffer NICHT verschlucken."""
        from kkm.core.groups import camera_key
        fremd = {"Name": "ICL004", "IP Adresse: Konfiguriert": "192.168.0.164",
                 "_vendor": "hikvision", "MAC-Adresse/Seriennummer": "28:57:BE:57:9C:AB",
                 "_online": True}
        self.store.roster[camera_key(fremd)] = fremd
        hit = self._netcon_treffer()
        self.store.roster[camera_key(hit)] = hit
        n, _ziele = self._fenster()._merge_rediscovered_duplicates([hit])
        self.assertEqual(n, 0)                                  # kein Fehl-Merge
        self.assertIn(camera_key(hit), self.store.roster)       # Treffer bleibt sichtbar
        self.assertIn(camera_key(fremd), self.store.roster)     # Fremdgerät unberührt

    def test_treffer_mit_eigener_mac_wird_nicht_rediscovery_gemerged(self):
        from kkm.core.groups import camera_key
        hit = self._netcon_treffer()
        hit["MAC-Adresse/Seriennummer"] = "B8:27:EB:B4:7F:78"
        self.store.roster[camera_key(hit)] = hit
        n, _ = self._fenster()._merge_rediscovered_duplicates([hit])
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
