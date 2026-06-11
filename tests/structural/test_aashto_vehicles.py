#  CivilPy
#  Copyright (C) $originalComment.match("Copyright \(C\) (\d+)", 1)-2026 Dane Parks
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

import unittest
from civilpy.structural.aashto.vehicles import HL93Load, HS20Load, PedestrianLoad

class TestHL93Load(unittest.TestCase):
    def test_init(self):
        load = HL93Load()
        self.assertEqual(load.axels['spacing'], 6)
        self.assertEqual(load.axels[1]['load'], 8)
        self.assertEqual(load.lane_load_klf, 0.64)
        self.assertEqual(load.dynamic_load_allowance, 0.33)

class TestHS20Load(unittest.TestCase):
    def test_init(self):
        load = HS20Load()
        self.assertEqual(load.axles['axle_width_ft'], 6)
        self.assertEqual(load.axles[1]['load_kip'], 8)
        self.assertEqual(load.lane_load_klf, 0.64)

    def test_impact_factor(self):
        # 50 / (50 + 125) = 50 / 175 = 0.2857...
        self.assertAlmostEqual(HS20Load.impact_factor(50), 0.285714, places=5)
        # 50 / (25 + 125) = 50 / 150 = 0.333... -> capped at 0.30
        self.assertEqual(HS20Load.impact_factor(25), 0.30)
        # 50 / (200 + 125) = 50 / 325 = 0.1538...
        self.assertAlmostEqual(HS20Load.impact_factor(200), 0.153846, places=5)

    def test_total_axle_load(self):
        load = HS20Load()
        # 8 + 32 + 32 = 72
        self.assertEqual(load.total_axle_load_kip(), 72.0)

class TestPedestrianLoad(unittest.TestCase):
    def test_init_defaults(self):
        load = PedestrianLoad()
        self.assertEqual(load.span_length_ft, 25.0)
        self.assertEqual(load.tributary_width_ft, 6.0)
        self.assertEqual(load.dynamic_load_allowance, 0.0)

    def test_uniform_load_psf(self):
        # L <= 25 -> 90 psf
        self.assertEqual(PedestrianLoad(span_length_ft=25.0).uniform_load_psf, 90.0)
        self.assertEqual(PedestrianLoad(span_length_ft=10.0).uniform_load_psf, 90.0)

        # L = 100 -> 240/100 + 20 = 2.4 + 20 = 22.4 psf
        self.assertEqual(PedestrianLoad(span_length_ft=100.0).uniform_load_psf, 22.4)

        # L = 1000 -> 240/1000 + 20 = 0.24 + 20 = 20.24 -> min 20 psf
        self.assertEqual(PedestrianLoad(span_length_ft=1000.0).uniform_load_psf, 20.24)

        # very large L
        self.assertEqual(PedestrianLoad(span_length_ft=10000.0).uniform_load_psf, 20.024)

    def test_uniform_load_klf(self):
        # L=25, W=6 -> 90 psf * 6 ft / 1000 = 0.54 klf
        load = PedestrianLoad(span_length_ft=25.0, tributary_width_ft=6.0)
        self.assertEqual(load.uniform_load_klf, 0.54)

    def test_repr(self):
        load = PedestrianLoad(span_length_ft=25.0, tributary_width_ft=6.0)
        rep = repr(load)
        self.assertIn("PedestrianLoad", rep)
        self.assertIn("25.0 ft", rep)
        self.assertIn("6.0 ft", rep)
        self.assertIn("90.0 psf", rep)
        self.assertIn("0.5400 klf", rep)
