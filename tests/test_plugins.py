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

"""The plugin registry: which plugins exist, their default on/off state, declared
capabilities and the ``uses_credentials`` flag (``core/plugins.py`` + registry)."""

import pathlib
import sys
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from kkm.core.plugins import Capability as C
from kkm.plugins import DEFAULT_OFF, build_registry

ERWARTET = {"axis", "onvif", "hikvision", "dahua", "hanwha", "senstar", "scutum"}


class TestRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = build_registry()

    def test_alle_erwarteten_plugins_sind_da(self):
        vorhanden = {p.id for p in self.reg.all()}
        self.assertEqual(vorhanden, ERWARTET)

    def test_nur_axis_ist_ab_werk_an(self):
        self.assertTrue(self.reg.is_enabled("axis"))
        for pid in ERWARTET - {"axis"}:
            with self.subTest(plugin=pid):
                self.assertFalse(self.reg.is_enabled(pid))
                self.assertIn(pid, DEFAULT_OFF)

    def test_gespeicherte_auswahl_ueberschreibt_die_vorgabe(self):
        reg = build_registry(enabled_ids=["scutum"])
        self.assertTrue(reg.is_enabled("scutum"))
        self.assertFalse(reg.is_enabled("axis"))


class TestFaehigkeiten(unittest.TestCase):
    def setUp(self):
        self.reg = build_registry()

    def test_scutum_kann_nur_anzeigen(self):
        p = self.reg.get("scutum")
        for cap in (C.DISCOVER, C.ONLINE_CHECK, C.DEVICE_INFO):
            self.assertTrue(p.supports(cap))
        for cap in (C.SET_IP, C.USERS, C.FIRMWARE, C.FACTORY_RESET, C.CONFIG):
            self.assertFalse(p.supports(cap))

    def test_senstar_kann_konfigurieren(self):
        p = self.reg.get("senstar")
        for cap in (C.SET_IP, C.USERS, C.FIRMWARE, C.FACTORY_RESET, C.VIDEO_SOURCES):
            with self.subTest(cap=cap):
                self.assertTrue(p.supports(cap))

    def test_uses_credentials_nur_bei_reiner_anzeige_false(self):
        self.assertFalse(self.reg.get("scutum").uses_credentials)
        for pid in ("axis", "senstar", "hikvision", "hanwha", "dahua", "onvif"):
            with self.subTest(plugin=pid):
                self.assertTrue(self.reg.get(pid).uses_credentials)

    def test_default_username_wird_gefuehrt(self):
        """Senstar braucht „admin" als Vorgabe-Benutzer — mit dem generischen
        „root" scheitert die Anmeldung trotz richtigem Passwort (die
        Passwortabfrage muss diesen Default übernehmen)."""
        self.assertEqual(self.reg.get("senstar").default_username, "admin")

    def test_experimentelle_und_generische_kennzeichnung(self):
        self.assertFalse(self.reg.get("axis").experimental)
        self.assertTrue(self.reg.get("scutum").experimental)
        self.assertTrue(self.reg.get("onvif").generic)
        self.assertFalse(self.reg.get("axis").generic)


if __name__ == "__main__":
    unittest.main()
