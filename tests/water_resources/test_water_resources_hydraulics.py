#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import unittest
from civilpy.water_resources.hydraulics import OhioCulvertDesign


class TestCulvertDesign(unittest.TestCase):
    # Establish a test culvert object
    def setUp(self):
        self.tc = OhioCulvertDesign()

    def test_load_culvert_design_object(self):
        self.assertEqual(
            self.tc.Headwall_Dimensions["A"]["10.5"]["L"], 12.75
        )  # add assertion here

    def test_wall_thickness_8(self):
        tc = OhioCulvertDesign(span=8)
        self.assertEqual(tc.wall_thickness, 8)

    def test_wall_thickness_10(self):
        tc = OhioCulvertDesign(span=10)
        self.assertEqual(tc.wall_thickness, 10)

    def test_wall_thickness_12(self):
        tc = OhioCulvertDesign(span=12)
        self.assertEqual(tc.wall_thickness, 12)
