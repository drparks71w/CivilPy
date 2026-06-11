"""
CivilPy
Copyright (C) 2019 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from unittest import TestCase
from civilpy.structural.arema.rail_tpg_design import TPG, ThroughPlateGirderFloorbeam


class TestTPG(TestCase):
    t = TPG()

    def test_run_calcs(self):
        self.assertLessEqual(self.t.fb_deflection, self.t.max_deflection)


class TestThroughPlateGirderFloorbeam(TestCase):
    def test_not_rolled_shape(self):
        # Covers lines 144-151: if not rolled_shape: branch
        fb = ThroughPlateGirderFloorbeam(rolled_shape=False)
        self.assertIsInstance(fb.shape, tuple)
        self.assertIsInstance(fb.depth, tuple)
