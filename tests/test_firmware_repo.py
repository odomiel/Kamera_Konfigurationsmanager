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

"""Network-free model resolution of the Axis firmware repository.

``_normalize`` maps a camera model name onto the comparison form of a repo folder,
``_is_variant_of`` recognises a variant folder (``Q3505-V Mk II``) of a bare family
name (``Q3505 Mk II``), and ``resolve_model`` combines both. The folder matching is
pure string work and tested here without touching ftp.axis.com — the live directory
is injected as a fake ``model_index``."""

import pathlib
import sys
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from kkm.plugins.axis import firmware_repo as fr


class TestNormalize(unittest.TestCase):
    def test_axis_praefix_und_variante(self):
        self.assertEqual(fr._normalize("AXIS M3085-V"), "m3085-v")
        self.assertEqual(fr._normalize("AXIS Q3505-V Mk II"), "q3505-v_mk_ii")

    def test_familienname_ohne_variante(self):
        self.assertEqual(fr._normalize("AXIS Q3505 Mk II"), "q3505_mk_ii")

    def test_zusatz_network_camera_entfaellt(self):
        self.assertEqual(fr._normalize("AXIS P3245-LVE Network Camera"), "p3245-lve")


class TestIstVarianteVon(unittest.TestCase):
    def test_zusatz_am_modellcode_ist_variante(self):
        self.assertTrue(fr._is_variant_of("q3505_mk_ii", "q3505-v_mk_ii"))
        self.assertTrue(fr._is_variant_of("q3505_mk_ii", "q3505-sve_mk_ii"))
        self.assertTrue(fr._is_variant_of("q1615", "q1615-e"))

    def test_andere_variante_ist_keine_variante_der_variante(self):
        # Eine bereits variantengenaue Angabe darf nicht an eine ANDERE Variante koppeln.
        self.assertFalse(fr._is_variant_of("q3505-v_mk_ii", "q3505-ve_mk_ii"))
        self.assertFalse(fr._is_variant_of("m3085-v", "m3085-ve"))

    def test_anderes_produkt_ist_keine_variante(self):
        self.assertFalse(fr._is_variant_of("q3505_mk_ii", "q3505"))      # anderes Modell
        self.assertFalse(fr._is_variant_of("q3505_mk_ii", "q3505_mk_ii"))  # identisch
        self.assertFalse(fr._is_variant_of("p3245", "p3367"))


class TestResolveModel(unittest.TestCase):
    """``resolve_model`` mit einem eingespeisten Modellindex (kein Netzwerk)."""

    # So lag die Q3505-Familie am 2026-11-02 im echten Repo: veralteter Sammelordner
    # plus drei aktuelle Varianten.
    INDEX = ["M3085-V", "P3245-LVE", "Q3505", "Q3505_Mk_II",
             "Q3505-V_Mk_II", "Q3505-VE_Mk_II", "Q3505-SVE_Mk_II"]

    def setUp(self):
        self._orig = fr.model_index
        fr.model_index = lambda base_url=None, refresh=False: list(self.INDEX)
        self.addCleanup(lambda: setattr(fr, "model_index", self._orig))

    def test_produktnummer_mit_variante_trifft_exakt(self):
        # Brand.ProdNbr liefert die Variante -> exakter Ordner, aktuelle Firmware.
        self.assertEqual(fr.resolve_model("Q3505-V Mk II"), "Q3505-V_Mk_II")
        self.assertEqual(fr.resolve_model("AXIS Q3505-VE Mk II"), "Q3505-VE_Mk_II")

    def test_familienname_mit_mehreren_varianten_ist_mehrdeutig(self):
        # Ohne Variante (und mit veraltetem Sammelordner) darf NICHT still der alte
        # Ordner genommen werden — klare Meldung, die alle Varianten nennt.
        with self.assertRaises(fr.RepoError) as ctx:
            fr.resolve_model("AXIS Q3505 Mk II")
        msg = str(ctx.exception)
        self.assertIn("Q3505-V_Mk_II", msg)
        self.assertIn("Q3505-VE_Mk_II", msg)

    def test_einzelne_variante_wird_genommen(self):
        # Familienname, aber nur eine Variante im Repo -> die ist eindeutig gemeint.
        fr.model_index = lambda base_url=None, refresh=False: ["Q1615-E_Mk_III"]
        self.assertEqual(fr.resolve_model("AXIS Q1615 Mk III"), "Q1615-E_Mk_III")

    def test_gewoehnliches_modell_unveraendert(self):
        self.assertEqual(fr.resolve_model("AXIS M3085-V"), "M3085-V")
        self.assertEqual(fr.resolve_model("AXIS P3245-LVE"), "P3245-LVE")

    def test_unbekanntes_modell_wirft(self):
        with self.assertRaises(fr.RepoError):
            fr.resolve_model("AXIS ZZZ9999")

    def test_mehrdeutig_traegt_kandidaten(self):
        with self.assertRaises(fr.AmbiguousModelError) as ctx:
            fr.resolve_model("AXIS Q3505 Mk II")
        self.assertIn("Q3505-V_Mk_II", ctx.exception.candidates)
        self.assertIn("Q3505-VE_Mk_II", ctx.exception.candidates)


class TestPluginAmbiguous(unittest.TestCase):
    """Das Axis-Plugin reicht die Mehrdeutigkeit vendor-neutral als ``FirmwareAmbiguous``
    mit lesbaren Variantennamen weiter (ohne Netzwerk — Modellindex eingespeist)."""

    INDEX = TestResolveModel.INDEX

    def setUp(self):
        self._orig = fr.model_index
        fr.model_index = lambda base_url=None, refresh=False: list(self.INDEX)
        self.addCleanup(lambda: setattr(fr, "model_index", self._orig))

    def test_firmware_updates_wirft_firmware_ambiguous(self):
        from kkm.plugins.axis.plugin import AxisPlugin
        from kkm.core.plugins import FirmwareAmbiguous
        with self.assertRaises(FirmwareAmbiguous) as ctx:
            AxisPlugin().firmware_updates("AXIS Q3505 Mk II", "8.40.0", True)
        # Ordnernamen werden zu lesbaren Varianten (Unterstrich -> Leerzeichen).
        self.assertIn("Q3505-V Mk II", ctx.exception.variants)
        self.assertIn("Q3505-VE Mk II", ctx.exception.variants)
        self.assertTrue(all("_" not in v for v in ctx.exception.variants))


if __name__ == "__main__":
    unittest.main()
