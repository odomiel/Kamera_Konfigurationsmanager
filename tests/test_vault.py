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

"""Password vault: PBKDF2 + AES-256-GCM round-trip, locking and master change.

Skipped cleanly if ``cryptography`` is not importable (the vault needs it; the bundled
AppImage interpreter has it)."""

import pathlib
import sys
import tempfile
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

try:
    from kkm.core.vault import PasswordVault, VaultError, VaultLocked
    _VERFUEGBAR = True
except Exception:  # noqa: BLE001 - z. B. cryptography fehlt im System-Python
    _VERFUEGBAR = False


@unittest.skipUnless(_VERFUEGBAR, "cryptography nicht verfügbar")
class TestTresor(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.pfad = str(pathlib.Path(self._dir.name) / "vault.enc")

    def test_anlegen_setzen_wiederlesen(self):
        v = PasswordVault(self.pfad)
        v.create("geheim")
        v.set_password("MAC-1", "root", "pass123")
        # Neue Instanz derselben Datei: erst nach Entsperren lesbar.
        w = PasswordVault(self.pfad)
        w.unlock("geheim")
        eintrag = w.get_password("MAC-1")
        self.assertEqual(eintrag, {"username": "root", "password": "pass123"})

    def test_falsches_master_passwort_wirft_vaulterror(self):
        PasswordVault(self.pfad).create("richtig")
        with self.assertRaises(VaultError):
            PasswordVault(self.pfad).unlock("falsch")

    def test_gesperrt_wirft_beim_zugriff(self):
        PasswordVault(self.pfad).create("geheim")
        gesperrt = PasswordVault(self.pfad)   # nicht entsperrt
        with self.assertRaises(VaultLocked):
            gesperrt.get_password("MAC-1")

    def test_master_wechsel(self):
        v = PasswordVault(self.pfad)
        v.create("alt")
        v.set_password("MAC-1", "u", "p")
        v.change_master("alt", "neu")
        # Altes Passwort gilt nicht mehr, neues schon — Daten erhalten.
        with self.assertRaises(VaultError):
            PasswordVault(self.pfad).unlock("alt")
        w = PasswordVault(self.pfad)
        w.unlock("neu")
        self.assertEqual(w.get_password("MAC-1"), {"username": "u", "password": "p"})

    def test_loeschen(self):
        v = PasswordVault(self.pfad)
        v.create("geheim")
        v.set_password("MAC-1", "u", "p")
        v.delete("MAC-1")
        self.assertIsNone(v.get_password("MAC-1"))

    def test_kaputte_datei_wirft_vaulterror(self):
        pathlib.Path(self.pfad).write_text("kein gueltiger tresor", encoding="utf-8")
        with self.assertRaises(VaultError):
            PasswordVault(self.pfad).unlock("egal")


if __name__ == "__main__":
    unittest.main()
