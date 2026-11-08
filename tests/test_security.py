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

"""Net-free regression tests for the security-audit fixes (2026-11-08).

Covers the parts that are plain logic and need no camera:
- CSV formula-injection masking in ``camera.export_results``
- ONVIF ``device_url``: the chosen scheme wins over a (spoofable) discovery XAddr,
  which only contributes path and port
- the certificate-pinning downgrade guard: a password-setting ("sensitive") operation
  refuses the HTTP fallback even without a pinned certificate, and ``pinned_in_context``
  reports a pinned device."""

import csv
import os
import pathlib
import sys
import tempfile
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from kkm.core import camera, certpin, vault
from kkm.plugins.onvif import soap

try:
    import cryptography  # noqa: F401
    _HAT_CRYPTO = True
except ImportError:
    _HAT_CRYPTO = False


class TestCsvInjektion(unittest.TestCase):
    """Zellen, die wie eine Excel-Formel beginnen, werden mit ' maskiert."""

    def _export(self, name):
        cams = [{"Name": name, "IP Adresse: Konfiguriert": "10.0.0.9"}]
        fd, pfad = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        self.addCleanup(os.unlink, pfad)
        camera.export_results(cams, pfad, columns=["Name", "IP Adresse: Konfiguriert"])
        with open(pfad, newline="", encoding="utf-8") as fh:
            return list(csv.reader(fh))[1][0]   # erste Datenzeile, Spalte Name

    def test_formelzeichen_werden_maskiert(self):
        for roh in ('=HYPERLINK("http://x","k")', "+1+1", "-2", "@cmd", "\tTab", "\rCR"):
            with self.subTest(roh=roh):
                self.assertEqual(self._export(roh), "'" + roh)

    def test_harmloser_name_unveraendert(self):
        self.assertEqual(self._export("Eingang Nord"), "Eingang Nord")

    def test_maskieren_direkt(self):
        self.assertEqual(camera._csv_maskieren("=1"), "'=1")
        self.assertEqual(camera._csv_maskieren("ok"), "ok")
        self.assertEqual(camera._csv_maskieren(None), "")
        self.assertEqual(camera._csv_maskieren(42), "42")


class TestOnvifDeviceUrl(unittest.TestCase):
    """Das gewaehlte Schema gewinnt gegen ein (faelschbares) Discovery-XAddr; aus dem
    XAddr kommen nur Pfad und Port."""

    def test_schema_gewinnt_gegen_xaddr(self):
        url = soap.device_url("10.0.0.5", "https", None,
                              xaddr="http://1.2.3.4:8080/onvif/dev")
        # http -> https herabgezogen wird NICHT; IP bleibt die aufgeloeste, Port/Pfad
        # kommen aus dem XAddr.
        self.assertEqual(url, "https://10.0.0.5:8080/onvif/dev")

    def test_ohne_xaddr_standardpfad(self):
        self.assertEqual(soap.device_url("10.0.0.5", "https"),
                         "https://10.0.0.5:443/onvif/device_service")
        self.assertEqual(soap.device_url("10.0.0.5", "http"),
                         "http://10.0.0.5:80/onvif/device_service")

    def test_expliziter_port_schlaegt_xaddr_port(self):
        url = soap.device_url("10.0.0.5", "https", 8443,
                              xaddr="http://1.2.3.4:8080/p")
        self.assertEqual(url, "https://10.0.0.5:8443/p")

    def test_ungueltiges_schema_wird_http(self):
        self.assertTrue(soap.device_url("10.0.0.5", "auto").startswith("http://"))


class TestPinningDowngrade(unittest.TestCase):
    """certpin: sensible Vorgaenge weigern sich, bei auto auf HTTP auszuweichen; der
    Pinned-Zustand steuert den Legacy-Rueckfall."""

    def setUp(self):
        fd, pfad = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.unlink(pfad)
        self.addCleanup(lambda: os.path.exists(pfad) and os.unlink(pfad))
        self._orig_store = certpin.STORE
        certpin.STORE = certpin.CertStore(path=pfad)
        certpin.set_enabled(True)
        self.addCleanup(lambda: setattr(certpin, "STORE", self._orig_store))

    def _https_fehlschlag(self):
        # simuliert einen gescheiterten HTTPS-Verbindungsaufbau (der=None).
        certpin.check_connection("https", "h", 443, None)

    def test_sensitiv_verweigert_http_ohne_zertifikat(self):
        with certpin.bound("kA", "auto", sensitive=True):
            self._https_fehlschlag()
            with self.assertRaises(certpin.HttpFallbackRefused):
                certpin.check_connection("http", "h", 80, None)

    def test_nicht_sensitiv_erlaubt_http_ohne_zertifikat(self):
        with certpin.bound("kB", "auto", sensitive=False):
            self._https_fehlschlag()
            certpin.check_connection("http", "h", 80, None)   # kein Fehler

    def test_bekanntes_zertifikat_verweigert_http_auch_ohne_sensitiv(self):
        certpin.STORE.remember("kC", "ab" * 32)
        with certpin.bound("kC", "auto", sensitive=False):
            self._https_fehlschlag()
            with self.assertRaises(certpin.HttpFallbackRefused):
                certpin.check_connection("http", "h", 80, None)

    def test_expliziter_http_modus_bleibt_erlaubt(self):
        # Ausdruecklich "http" gewaehlt -> bewusste Entscheidung, kein Downgrade-Schutz.
        with certpin.bound("kD", "http", sensitive=True):
            certpin.check_connection("http", "h", 80, None)   # kein Fehler

    def test_pinned_in_context(self):
        self.assertFalse(certpin.pinned_in_context())          # ohne Kontext
        with certpin.bound("kE", "auto"):
            self.assertFalse(certpin.pinned_in_context())      # noch nichts gepinnt
            certpin.STORE.remember("kE", "cd" * 32)
            self.assertTrue(certpin.pinned_in_context())

    def test_pinned_in_context_aus_wenn_pinning_deaktiviert(self):
        certpin.STORE.remember("kF", "ef" * 32)
        certpin.set_enabled(False)
        self.addCleanup(lambda: certpin.set_enabled(True))
        with certpin.bound("kF", "auto"):
            self.assertFalse(certpin.pinned_in_context())


class TestAutounlockSecret(unittest.TestCase):
    """Audit-Befund 5: Per-Install-Geheimnis in der Schlüsselableitung; ohne die
    Zusatzdatei scheitert die Auto-Entsperrung (kopierte Dateien allein genügen nicht)."""

    def test_machine_key_abwaertskompatibel_ohne_secret(self):
        salt = b"0123456789abcdef"
        self.assertEqual(vault._machine_key(salt),
                         vault._machine_key(salt, secret=b""))

    def test_machine_key_mit_secret_weicht_ab(self):
        salt = b"0123456789abcdef"
        self.assertNotEqual(vault._machine_key(salt),
                            vault._machine_key(salt, secret=b"geheim"))

    def test_secret_wird_erzeugt_und_wiedergelesen(self):
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        self.assertEqual(vault._autounlock_secret(d, create=False), b"")   # noch keins
        s1 = vault._autounlock_secret(d, create=True)
        self.assertEqual(len(s1), 32)
        self.assertTrue(os.path.exists(os.path.join(d, vault.AUTO_SECRET_FILENAME)))
        self.assertEqual(vault._autounlock_secret(d, create=False), s1)     # stabil

    @unittest.skipUnless(_HAT_CRYPTO, "cryptography nicht verfügbar")
    def test_autounlock_braucht_die_seed_datei(self):
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        pfad = os.path.join(d, "vault.enc")
        v = vault.PasswordVault(path=pfad)
        v.create("Master-PW")
        v.enable_autounlock("Master-PW")
        # Gleiches Verzeichnis (seed vorhanden) -> entsperrt automatisch.
        self.assertTrue(vault.PasswordVault(path=pfad).try_autounlock())
        # vault.seed fehlt (z. B. nur vault.enc+vault.auto kopiert) -> bleibt gesperrt.
        os.remove(os.path.join(d, vault.AUTO_SECRET_FILENAME))
        v3 = vault.PasswordVault(path=pfad)
        self.assertFalse(v3.try_autounlock())
        self.assertTrue(v3.is_locked)

    @unittest.skipUnless(_HAT_CRYPTO, "cryptography nicht verfügbar")
    def test_disable_entfernt_seed(self):
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        pfad = os.path.join(d, "vault.enc")
        v = vault.PasswordVault(path=pfad)
        v.create("pw")
        v.enable_autounlock("pw")
        self.assertTrue(os.path.exists(os.path.join(d, vault.AUTO_SECRET_FILENAME)))
        v.disable_autounlock()
        self.assertFalse(os.path.exists(os.path.join(d, vault.AUTO_SECRET_FILENAME)))
        self.assertFalse(os.path.exists(os.path.join(d, vault.AUTO_FILENAME)))


if __name__ == "__main__":
    unittest.main()
