#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import unittest
from civilpy.structural.aashto.vehicles import (
    EMERGENCY_VEHICLES,
    HL93Load,
    HS20Load,
    LEGAL_TRUCKS,
    OHIO_LEGAL_TRUCKS,
    PedestrianLoad,
    RATING_VEHICLES,
    RatingVehicle,
    SHV_TRUCKS,
)

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


class TestRatingVehicleCatalog(unittest.TestCase):
    # (GVW kip, wheelbase ft) per MBE Fig. D6A-1/-2, FHWA EV memo, ODOT BDM 908
    EXPECTED = {
        "HS20": (72.0, 28.0),
        "HL-93": (72.0, 28.0),
        "Type 3": (50.0, 19.0),
        "Type 3S2": (72.0, 41.0),
        "Type 3-3": (80.0, 54.0),
        "SU4": (54.0, 18.0),
        "SU5": (62.0, 22.0),
        "SU6": (69.5, 26.0),
        "SU7": (77.5, 30.0),
        "EV2": (57.5, 15.0),
        "EV3": (86.0, 19.0),
        "2F1": (30.0, 10.0),
        "3F1": (46.0, 14.0),
        "4F1": (54.0, 18.0),
        "5C1": (80.0, 51.0),
    }

    def test_catalog_complete(self):
        self.assertEqual(set(RATING_VEHICLES), set(self.EXPECTED))

    def test_gvw_and_wheelbase(self):
        for name, (gvw, wheelbase) in self.EXPECTED.items():
            v = RATING_VEHICLES[name]
            self.assertAlmostEqual(v.gvw_kip, gvw, msg=name)
            self.assertAlmostEqual(v.gvw_tons, gvw / 2.0, msg=name)
            self.assertAlmostEqual(v.wheelbase_ft, wheelbase, msg=name)

    def test_groups_partition_catalog(self):
        merged = {**LEGAL_TRUCKS, **SHV_TRUCKS, **EMERGENCY_VEHICLES,
                  **OHIO_LEGAL_TRUCKS}
        self.assertEqual(len(merged), len(LEGAL_TRUCKS) + len(SHV_TRUCKS)
                         + len(EMERGENCY_VEHICLES) + len(OHIO_LEGAL_TRUCKS))
        for name in merged:
            self.assertIn(name, RATING_VEHICLES)

    def test_type_3s2_axles(self):
        v = LEGAL_TRUCKS["Type 3S2"]
        self.assertEqual(v.axle_loads_kip, (10.0, 15.5, 15.5, 15.5, 15.5))
        self.assertEqual(v.axle_spacings_ft, (11.0, 4.0, 22.0, 4.0))

    def test_only_hl93_has_lane_load(self):
        for name, v in RATING_VEHICLES.items():
            if name == "HL-93":
                self.assertEqual(v.lane_load_klf, 0.64)
            else:
                self.assertEqual(v.lane_load_klf, 0.0, msg=name)

    def test_train_feeds_steppers(self):
        loads, positions = RATING_VEHICLES["Type 3"].train()
        self.assertEqual(loads, [16.0, 17.0, 17.0])
        self.assertEqual(positions, [0.0, 15.0, 19.0])

    def test_validation(self):
        with self.assertRaises(ValueError):
            RatingVehicle("bad", (10.0, 10.0), (0.0,))
        with self.assertRaises(ValueError):
            RatingVehicle("bad", (10.0, 10.0), (5.0, 0.0))
