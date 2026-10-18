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

"""Tests for the version scheme JJ.MM.TT[bN] (``bump_version.next_version``)."""

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import bump_version


class TestVersionsschema(unittest.TestCase):
    TAG = "26.09.05"

    def test_erster_build_eines_tages_ist_nur_das_datum(self):
        self.assertEqual(bump_version.next_version("", self.TAG), self.TAG)
        self.assertEqual(bump_version.next_version("26.08.01", self.TAG), self.TAG)

    def test_weitere_builds_am_selben_tag_zaehlen_b_hoch(self):
        self.assertEqual(bump_version.next_version("26.09.05", self.TAG), "26.09.05b1")
        self.assertEqual(bump_version.next_version("26.09.05b1", self.TAG), "26.09.05b2")
        self.assertEqual(bump_version.next_version("26.09.05b11", self.TAG), "26.09.05b12")

    def test_neuer_tag_beginnt_wieder_ohne_suffix(self):
        self.assertEqual(bump_version.next_version("26.09.05b3", "26.09.06"), "26.09.06")

    def test_folge_an_einem_tag(self):
        version = ""
        for erwartet in ["26.09.05", "26.09.05b1", "26.09.05b2", "26.09.05b3"]:
            version = bump_version.next_version(version, self.TAG)
            self.assertEqual(version, erwartet)

    def test_read_version_findet_die_fassung(self):
        """Die ausgelieferte kkm/version.py muss eine Version im Schema tragen."""
        import re
        wurzel = pathlib.Path(__file__).resolve().parent.parent
        text = (wurzel / "kkm" / "version.py").read_text(encoding="utf-8")
        fassung = bump_version.read_version(text)
        self.assertRegex(fassung, r"^\d{2}\.\d{2}\.\d{2}(b\d+)?$")


if __name__ == "__main__":
    unittest.main()
