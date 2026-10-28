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

"""Settings load/save, defaults and corruption resilience (``core/settings.py``)."""

import pathlib
import sys
import tempfile
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from kkm.core.settings import DEFAULTS, AppSettings


class TestEinstellungen(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.pfad = str(pathlib.Path(self._dir.name) / "settings.json")

    def test_ohne_datei_gelten_die_vorgaben(self):
        s = AppSettings(self.pfad)
        for schluessel, wert in DEFAULTS.items():
            self.assertEqual(s.get(schluessel), wert)

    def test_setzen_speichert_und_ist_wiederlesbar(self):
        AppSettings(self.pfad).set("language", "en")
        self.assertEqual(AppSettings(self.pfad).get("language"), "en")

    def test_unbekannter_schluessel_hat_default(self):
        self.assertIsNone(AppSettings(self.pfad).get("gibtsnicht"))
        self.assertEqual(AppSettings(self.pfad).get("gibtsnicht", 7), 7)

    def test_kaputte_datei_faellt_auf_vorgaben_zurueck(self):
        """Eine beschädigte settings.json darf den Start nicht sprengen."""
        pathlib.Path(self.pfad).write_text("{kein gueltiges json", encoding="utf-8")
        s = AppSettings(self.pfad)   # load() im Init darf nicht werfen
        self.assertEqual(s.get("language"), DEFAULTS["language"])

    def test_backup_erinnerung_defaults(self):
        """Die Sicherungs-Erinnerung ist ab Werk an, noch nie gesichert, 30-Tage-Grenze."""
        from kkm.core.settings import BACKUP_WARN_DAYS
        self.assertTrue(DEFAULTS["warn_backup_age"])
        self.assertEqual(DEFAULTS["last_backup_ts"], 0.0)
        self.assertEqual(BACKUP_WARN_DAYS, 30)

    def test_unbekannte_felder_bleiben_erhalten(self):
        """Vorwärtskompatibel: ein Feld einer neueren Fassung geht nicht verloren."""
        s = AppSettings(self.pfad)
        s.set("zukunftsoption", 42)
        self.assertEqual(AppSettings(self.pfad).get("zukunftsoption"), 42)


if __name__ == "__main__":
    unittest.main()
