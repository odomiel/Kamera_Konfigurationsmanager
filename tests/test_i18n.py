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

"""Keep the English catalog complete.

The important check reads every ``t("…")`` call out of the source tree (via AST) and
makes sure its German message id is present in ``i18n_catalog.EN`` — a wrapped string
missing from the catalog would silently stay German in the English UI, and nobody would
notice. Ported from verteilerly's ``test_sprachen.py``.
"""

import ast
import pathlib
import re
import sys
import unittest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from kkm.core.i18n_catalog import EN


def _msgids_aus_quelltext() -> set[str]:
    """Jeder String aus einem ``t("…")``-Aufruf im Paket ``kkm`` (per AST)."""
    gefunden: set[str] = set()
    for datei in sorted((WURZEL / "kkm").rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
                    and knoten.func.id == "t" and knoten.args):
                erste = knoten.args[0]
                if isinstance(erste, ast.Constant) and isinstance(erste.value, str):
                    gefunden.add(erste.value)
    return gefunden


_PLATZHALTER = re.compile(r"\{(\w+)\}")


class TestKatalog(unittest.TestCase):
    def test_jeder_eingewickelte_satz_steht_im_katalog(self):
        """Sonst bliebe er im englischen Programm deutsch stehen."""
        fehlend = sorted(m for m in _msgids_aus_quelltext() if m not in EN)
        self.assertEqual(fehlend, [], f"{len(fehlend)} Satz/Sätze ohne Übersetzung")

    def test_platzhalter_bleiben_erhalten(self):
        """Ein benannter Platzhalter {ip} muss in beiden Sprachen vorkommen —
        sonst wirft ``.format(**kw)`` oder der Wert fehlt im Satz."""
        falsch = [f"{d!r} -> {e!r}" for d, e in EN.items()
                  if sorted(_PLATZHALTER.findall(d)) != sorted(_PLATZHALTER.findall(e))]
        self.assertEqual(falsch, [])

    def test_der_katalog_ist_nicht_leer(self):
        self.assertGreater(len(EN), 100)


if __name__ == "__main__":
    unittest.main()
