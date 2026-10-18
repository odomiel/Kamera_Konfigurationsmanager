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

"""Encrypted ``.kkmbackup`` round-trip (``core/backup.py``).

Skipped cleanly if ``cryptography`` is not importable."""

import pathlib
import sys
import tempfile
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

try:
    from kkm.core.backup import BackupError, create_backup, restore_backup
    _VERFUEGBAR = True
except Exception:  # noqa: BLE001
    _VERFUEGBAR = False


@unittest.skipUnless(_VERFUEGBAR, "cryptography nicht verfügbar")
class TestBackup(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.basis = pathlib.Path(self._tmp.name)
        self.quelle = self.basis / "quelle"
        self.quelle.mkdir()
        (self.quelle / "groups.json").write_text('{"groups": []}', encoding="utf-8")
        (self.quelle / "settings.json").write_text('{"language": "de"}', encoding="utf-8")
        self.archiv = str(self.basis / "sicherung.kkmbackup")

    def test_sichern_und_zurueckspielen_erhaelt_die_dateien(self):
        create_backup(self.archiv, "geheim", str(self.quelle))
        self.assertTrue(pathlib.Path(self.archiv).is_file())
        ziel = self.basis / "ziel"
        ziel.mkdir()
        restore_backup(self.archiv, "geheim", str(ziel))
        self.assertEqual((ziel / "groups.json").read_text(encoding="utf-8"),
                         '{"groups": []}')
        self.assertEqual((ziel / "settings.json").read_text(encoding="utf-8"),
                         '{"language": "de"}')

    def test_falsches_passwort_wirft_backuperror(self):
        create_backup(self.archiv, "richtig", str(self.quelle))
        ziel = self.basis / "ziel"
        ziel.mkdir()
        with self.assertRaises(BackupError):
            restore_backup(self.archiv, "falsch", str(ziel))


if __name__ == "__main__":
    unittest.main()
