#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import unittest
import pandas as pd
from pathlib import Path
from unittest.mock import patch, MagicMock

from civilpy.general import units
from civilpy.structural.midas import analysis_results_request
from civilpy.structural.arema import CooperE80, LoadRatingMember


class TestCooperE80(unittest.TestCase):

    def test_initialization(self):
        cooper = CooperE80()
        self.assertEqual(cooper.series, 80)
        self.assertEqual(len(cooper.distances), 18)
        self.assertEqual(len(cooper.magnitudes), 18)
        self.assertEqual(cooper.distributed["distance"], 109 * units.feet)
        self.assertEqual(cooper.distributed["magnitude"], 8 * units("kip/ft"))

    def test_conversion_to_other_series(self):
        cooper = CooperE80(series=60)
        self.assertEqual(cooper.series, 60)
        expected_magnitudes = [
            30.0 * units("kip"),
            60.0 * units("kip"),
            60.0 * units("kip"),
            60.0 * units("kip"),
            60.0 * units("kip"),
            39.0 * units("kip"),
            39.0 * units("kip"),
            39.0 * units("kip"),
            39.0 * units("kip"),
            30.0 * units("kip"),
            60.0 * units("kip"),
            60.0 * units("kip"),
            60.0 * units("kip"),
            60.0 * units("kip"),
            39.0 * units("kip"),
            39.0 * units("kip"),
            39.0 * units("kip"),
            39.0 * units("kip"),
        ]
        for expected, actual in zip(expected_magnitudes, cooper.magnitudes):
            self.assertAlmostEqual(expected.magnitude, actual.magnitude)

    def test_str_representation(self):
        cooper = CooperE80()
        repr_string = repr(cooper)
        self.assertIn("0 foot: 40 kip", repr_string)
        self.assertIn("109 foot: 8.0 kip / foot", repr_string)


class TestCooperE80EqStrip(unittest.TestCase):
    def test_initialization(self):
        from civilpy.structural.arema import CooperE80EqStrip
        strip = CooperE80EqStrip()
        self.assertIsNotNone(strip.linear_loads)
        self.assertIn("LS1", strip.linear_loads)

    def test_repr(self):
        from civilpy.structural.arema import CooperE80EqStrip
        strip = CooperE80EqStrip()
        result = repr(strip)
        self.assertIn("CooperE80EqStrip", result)
        self.assertIn("LS1", result)
