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

import unittest
from src.civilpy.structural.wood import (
    LumberSection,
    GlulamSection,
    AdjustmentFactors,
    WoodMemberCheck,
    TimberBridgeDeck,
    TimberStringer,
    BoltConnection,
    euler_critical_buckling_stress,
    column_stability_factor,
    beam_stability_factor,
    effective_beam_length,
    list_available_species,
    list_available_grades,
    list_available_glulam,
    LOAD_DURATION_FACTORS,
)

# Use the same Pint registry instance as the wood module so that quantities
# created in tests can be combined with quantities created inside the module
# (mixing registries raises "Cannot operate with Quantity ... of different
# registries").
from src.civilpy.structural.wood import units


class TestLumberSection(unittest.TestCase):
    def test_dressed_dimensions(self):
        beam = LumberSection(6, 12, "Douglas Fir-Larch", "No. 1")
        self.assertEqual(beam.b, 5.5 * units("in"))
        self.assertEqual(beam.d, 11.25 * units("in"))

    def test_label_form_matches_positional(self):
        b1 = LumberSection("6x12", "Douglas Fir-Larch", "No. 1")
        b2 = LumberSection(6, 12, "Douglas Fir-Larch", "No. 1")
        self.assertEqual(b1.Fb, b2.Fb)
        self.assertEqual(b1.A, b2.A)
        self.assertEqual(b1.Sx, b2.Sx)

    def test_label_form_tolerates_case_and_spaces(self):
        b1 = LumberSection("6 X 12", "Douglas Fir-Larch", "No. 1")
        b2 = LumberSection(6, 12, "Douglas Fir-Larch", "No. 1")
        self.assertEqual(b1.A, b2.A)

    def test_all_dimension_lumber_size_classes_resolve(self):
        # 2x6 / 2x10 / 4x6 previously failed grouped size-class lookup
        for nw, nd in [(2, 4), (2, 6), (2, 8), (2, 10), (2, 12), (4, 6)]:
            beam = LumberSection(nw, nd, "Douglas Fir-Larch", "No. 2")
            self.assertGreater(beam.Fb.magnitude, 0)

    def test_beams_and_stringers_vs_posts_and_timbers(self):
        bs = LumberSection(6, 12, "Douglas Fir-Larch", "Select Structural")
        pt = LumberSection(6, 6, "Douglas Fir-Larch", "Select Structural")
        self.assertEqual(bs.size_class, "5x5_and_larger_B&S")
        self.assertEqual(pt.size_class, "5x5_and_larger_P&T")

    def test_reference_values_dfl_no1_bs(self):
        # NDS Supplement Table 4D, DF-L No. 1, Beams & Stringers
        beam = LumberSection(8, 16, "Douglas Fir-Larch", "No. 1")
        self.assertEqual(beam.Fb, 1350 * units("lbf/in^2"))
        self.assertEqual(beam.Fv, 170 * units("lbf/in^2"))
        self.assertEqual(beam.E, 1600000 * units("lbf/in^2"))

    def test_unknown_size_raises(self):
        with self.assertRaises(ValueError):
            LumberSection(7, 13, "Douglas Fir-Larch", "No. 1")

    def test_unknown_grade_raises(self):
        with self.assertRaises(ValueError):
            LumberSection(6, 12, "Douglas Fir-Larch", "Ultra Premium")


class TestGlulamSection(unittest.TestCase):
    def test_reference_values(self):
        beam = GlulamSection(6.75, 30, "24F-V4", "Douglas Fir")
        self.assertEqual(beam.Fb_pos, 2400 * units("lbf/in^2"))
        self.assertEqual(beam.Fb, beam.Fb_pos)

    def test_section_properties(self):
        beam = GlulamSection(6.75, 30, "24F-V4", "Douglas Fir")
        self.assertEqual(beam.A, 6.75 * 30 * units("in^2"))
        self.assertEqual(beam.Sx, 6.75 * 30**2 / 6 * units("in^3"))
        self.assertEqual(beam.Ix, 6.75 * 30**3 / 12 * units("in^4"))

    def test_label_form_matches_positional(self):
        g1 = GlulamSection("6.75x30", "24F-V4", "Douglas Fir")
        g2 = GlulamSection(6.75, 30, "24F-V4", "Douglas Fir")
        self.assertEqual(g1.Fb_pos, g2.Fb_pos)
        self.assertEqual(g1.Sx, g2.Sx)

    def test_unknown_combination_raises(self):
        with self.assertRaises(ValueError):
            GlulamSection(6.75, 30, "99F-V9", "Douglas Fir")


class TestAdjustmentFactors(unittest.TestCase):
    def setUp(self):
        self.beam = LumberSection(6, 12, "Douglas Fir-Larch", "No. 1")
        self.af = AdjustmentFactors(self.beam)

    def test_load_duration_factors(self):
        self.assertEqual(self.af.CD("normal"), 1.0)
        self.assertEqual(self.af.CD("permanent"), 0.9)
        self.assertEqual(self.af.CD("10_min"), 1.6)
        with self.assertRaises(ValueError):
            self.af.CD("bogus")

    def test_wet_service_factor(self):
        # Dry service always 1.0
        self.assertEqual(self.af.CM("Fb", wet_service=False), 1.0)
        # B&S timbers: CM(Fc_perp) = 0.67 per NDS Table 4D
        self.assertEqual(self.af.CM("Fc_perp", wet_service=True), 0.67)

    def test_temperature_factor(self):
        self.assertEqual(self.af.Ct(100, "Fb"), 1.0)
        self.assertEqual(self.af.Ct(120, "Fb"), 0.80)
        self.assertEqual(self.af.Ct(120, "E"), 0.90)

    def test_incising_factor(self):
        self.assertEqual(self.af.Ci("Fb", incised=False), 1.0)
        self.assertEqual(self.af.Ci("Fb", incised=True), 0.80)
        self.assertEqual(self.af.Ci("Fc_perp", incised=True), 1.00)
        self.assertEqual(self.af.Ci("E", incised=True), 0.95)

    def test_size_factor_dimension_lumber(self):
        joist = LumberSection(2, 10, "Douglas Fir-Larch", "No. 2")
        af = AdjustmentFactors(joist)
        self.assertEqual(af.CF("Fb"), 1.1)
        # Timbers don't use the CF table
        self.assertEqual(self.af.CF("Fb"), 1.0)

    def test_repetitive_member_factor(self):
        self.assertEqual(self.af.Cr(repetitive=True), 1.15)
        self.assertEqual(self.af.Cr(repetitive=False), 1.0)

    def test_bearing_area_factor(self):
        self.assertEqual(self.af.Cb(6 * units("in")), 1.0)
        # lb < 6 in.: Cb = (lb + 0.375) / lb
        self.assertAlmostEqual(self.af.Cb(3 * units("in")), 3.375 / 3.0)

    def test_volume_factor_glulam_only(self):
        self.assertEqual(self.af.CV(L=40 * units("ft")), 1.0)
        gl = GlulamSection(6.75, 30, "24F-V4", "Douglas Fir")
        af_gl = AdjustmentFactors(gl)
        cv = af_gl.CV(L=40 * units("ft"))
        self.assertLess(cv, 1.0)
        self.assertGreater(cv, 0.7)

    def test_adjusted_value_applies_factors(self):
        result = self.af.adjusted_value(
            "Fb", load_duration="normal", wet_service=False, incised=True
        )
        # Only Ci = 0.8 should bite: 1350 * 0.8 = 1080 psi
        self.assertAlmostEqual(
            result["value"].to("lbf/in^2").magnitude, 1080.0, places=1
        )
        self.assertEqual(result["factors"]["Ci"], 0.8)

    def test_lrfd_factors(self):
        af_lrfd = AdjustmentFactors(self.beam, method="LRFD")
        result = af_lrfd.adjusted_value("Fb")
        self.assertIn("KF", result["factors"])
        self.assertIn("phi", result["factors"])
        self.assertIn("lambda", result["factors"])


class TestStabilityFunctions(unittest.TestCase):
    def test_euler_critical_buckling_stress(self):
        FcE = euler_critical_buckling_stress(
            580000 * units("lbf/in^2"), 120 * units("in"), 5.5 * units("in")
        )
        expected = 0.822 * 580000 / (120 / 5.5) ** 2
        self.assertAlmostEqual(FcE.magnitude, expected, places=1)

    def test_column_stability_factor_bounds(self):
        # Cp approaches 1.0 for stocky columns, decreases when slender
        cp_stocky = column_stability_factor(100000, 1000, c=0.8)
        cp_slender = column_stability_factor(500, 1000, c=0.8)
        self.assertGreater(cp_stocky, 0.98)
        self.assertLess(cp_slender, 0.5)

    def test_effective_beam_length(self):
        lu = 10 * units("ft")
        self.assertEqual(effective_beam_length(lu, "uniform"), 1.63 * lu)
        self.assertEqual(
            effective_beam_length(lu, "concentrated_center"), 1.37 * lu
        )

    def test_beam_stability_factor(self):
        CL = beam_stability_factor(
            580000 * units("lbf/in^2"),
            1350 * units("lbf/in^2"),
            16.3 * units("ft"),
            11.25 * units("in"),
            5.5 * units("in"),
        )
        self.assertGreater(CL, 0.0)
        self.assertLessEqual(CL, 1.0)


class TestWoodMemberCheck(unittest.TestCase):
    def setUp(self):
        self.beam = LumberSection(6, 12, "Douglas Fir-Larch", "No. 1")
        self.check = WoodMemberCheck(self.beam)

    def test_bending_check(self):
        result = self.check.check_bending(9600 * units("lbf*ft"))
        # fb = M/Sx = 115200 / 116.0 ~ 993 psi < Fb' = 1350 psi
        self.assertAlmostEqual(result["fb"].magnitude, 993.1, places=0)
        self.assertEqual(result["status"], "OK")

    def test_shear_check(self):
        result = self.check.check_shear(2400 * units("lbf"))
        # fv = 1.5*2400/61.875 = 58.2 psi < 170 psi
        self.assertAlmostEqual(result["fv"].magnitude, 58.18, places=1)
        self.assertEqual(result["status"], "OK")

    def test_compression_check(self):
        col = LumberSection(6, 6, "Douglas Fir-Larch", "No. 1")
        check = WoodMemberCheck(col)
        result = check.check_compression(15000 * units("lbf"), 10 * units("ft"))
        self.assertEqual(result["status"], "OK")
        self.assertLess(result["Cp"], 1.0)

    def test_compression_slenderness_limit(self):
        col = LumberSection(2, 4, "Douglas Fir-Larch", "No. 1")
        check = WoodMemberCheck(col)
        with self.assertRaises(ValueError):
            check.check_compression(1000 * units("lbf"), 20 * units("ft"))

    def test_tension_check(self):
        result = self.check.check_tension(10000 * units("lbf"))
        self.assertEqual(result["status"], "OK")

    def test_bearing_check(self):
        result = self.check.check_bearing(2400 * units("lbf"), 6 * units("in"))
        self.assertEqual(result["status"], "OK")

    def test_deflection_check(self):
        result = self.check.check_deflection(
            200 * units("lbf/ft"), 16 * units("ft"), limit="L/360"
        )
        self.assertEqual(result["status"], "OK")
        self.assertEqual(
            result["delta_limit"], (16 * 12 / 360) * units("in")
        )

    def test_combined_bending_compression(self):
        member = LumberSection(6, 8, "Douglas Fir-Larch", "No. 1")
        check = WoodMemberCheck(member)
        result = check.check_combined_bending_compression(
            P=5000 * units("lbf"),
            M=8000 * units("lbf*ft"),
            le_strong=8 * units("ft"),
            lu=8 * units("ft"),
        )
        self.assertIn("interaction_ratio", result)
        self.assertIn("FcE", result)  # Key used by the Wood Design notebook

    def test_summary_dataframe(self):
        self.check.check_bending(9600 * units("lbf*ft"))
        self.check.check_shear(2400 * units("lbf"))
        df = self.check.summary()
        self.assertEqual(len(df), 2)
        self.assertIn("Status", df.columns)


class TestTimberBridge(unittest.TestCase):
    def test_deck_check_runs(self):
        deck = TimberBridgeDeck(
            deck_type="nail_laminated",
            span=4 * units("ft"),
            thickness=12 * units("in"),
            species="Douglas Fir-Larch",
            grade="No. 2",
            wearing_surface="asphalt_3in",
        )
        result = deck.check_deck()
        for key in ("bending", "shear", "deflection", "distribution_width"):
            self.assertIn(key, result)

    def test_stringer_distribution_factor(self):
        stringer = LumberSection(8, 16, "Douglas Fir-Larch", "Select Structural")
        ts = TimberStringer(
            stringer, 20 * units("ft"), 4 * units("ft"),
            num_lanes=1, deck_type="nail_laminated",
        )
        # AASHTO Table 4.6.2.2.2a-1, one lane: g = S/6.0
        self.assertAlmostEqual(ts.live_load_distribution_factor(), 4.0 / 6.0, places=3)
        self.assertEqual(ts.dynamic_load_allowance(), 0.33)

    def test_rating_factor(self):
        stringer = LumberSection(8, 16, "Douglas Fir-Larch", "Select Structural")
        ts = TimberStringer(stringer, 20 * units("ft"), 4 * units("ft"))
        rf = ts.rating_factor(
            DC_moment=10000 * units("lbf*ft"),
            DW_moment=5000 * units("lbf*ft"),
            LL_moment=20000 * units("lbf*ft"),
            capacity_moment=100000 * units("lbf*ft"),
        )
        # RF = (100000 - 1.25*10000 - 1.5*5000) / (1.75*20000*1.33)
        self.assertAlmostEqual(rf["RF"], 80000 / 46550, places=3)
        self.assertEqual(rf["status"], "ADEQUATE")


class TestBoltConnection(unittest.TestCase):
    def setUp(self):
        self.conn = BoltConnection(
            bolt_diameter=0.75 * units("in"),
            main_thickness=7.5 * units("in"),
            side_thickness=0.375 * units("in"),
            main_species_gravity=0.50,
            side_material="steel",
            loading="single_shear",
            angle_to_grain=0,
        )

    def test_dowel_bearing_strengths(self):
        # Fe parallel = 11200 * G
        self.assertEqual(self.conn.Fem, 11200 * 0.50)
        self.assertEqual(self.conn.Fes, 87000.0)

    def test_z_reference_governing_mode(self):
        z = self.conn.Z_reference()
        self.assertGreater(z["Z"], 0)
        self.assertEqual(z["governing_mode"], "IV")
        self.assertEqual(len(z["all_modes"]), 6)
        # Governing value is the minimum of all modes
        self.assertEqual(z["Z"], min(z["all_modes"].values()))

    def test_z_prime_applies_factors(self):
        result = self.conn.Z_prime(
            num_bolts=4, num_bolts_in_row=4,
            load_duration="normal", wet_service=True,
        )
        self.assertEqual(result["factors"]["CM"], 0.70)
        self.assertEqual(result["factors"]["Cg"], 0.96)
        z_single = self.conn.Z_reference()["Z"]
        expected = z_single * 4 * 0.70 * 0.96
        self.assertAlmostEqual(result["Z_prime"].magnitude, expected, places=0)


class TestUtilityFunctions(unittest.TestCase):
    def test_list_available_species(self):
        species = list_available_species()
        self.assertIn("Douglas Fir-Larch", species)
        self.assertIn("Southern Pine", species)

    def test_list_available_grades(self):
        grades = list_available_grades("Douglas Fir-Larch")
        self.assertIn("Select Structural", grades)
        self.assertIn("No. 1", grades)

    def test_list_available_glulam(self):
        self.assertIn("24F-V4", list_available_glulam())

    def test_load_duration_constants(self):
        self.assertEqual(LOAD_DURATION_FACTORS["normal"], 1.0)
        self.assertEqual(LOAD_DURATION_FACTORS["permanent"], 0.9)


if __name__ == "__main__":
    unittest.main()
