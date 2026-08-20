#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""B4 -- composite steel-girder transformed-section properties, validated
against the reference workbook's MDX/Descus section-property and service-
stress tables (smaller stringer W24x104, section without bolt holes, pp. 1 & 3).
This is the "verify the composite section math independent of MIDAS" leg of B1.
Only plain numeric results are checked; no copyrighted content is reproduced."""

import pytest

from civilpy.structural.aashto.lrfd import girder_side_from_w
from civilpy.structural.aashto.lrfd.composite import (
    CompositeGirder, modular_ratio,
)


def _girder():
    # haunch 2.0 in places the composite NA to match the workbook's tables.
    gs = girder_side_from_w("W24X104", "Grade 50", haunch=2.0)
    return CompositeGirder(gs, deck_t=7.5, deck_weff=84.0, n=8.0,
                           rebar_area=7.46, rebar_cover=2.5)


def test_modular_ratio_is_about_eight():
    assert modular_ratio(4.0) == pytest.approx(8.0, abs=0.1)


class TestSectionProperties:
    def setup_method(self):
        self.cg = _girder()

    def test_noncomposite_matches_aisc(self):
        # bare steel I = AISC Ix for W24x104 = 3100 in^4; NA at mid-depth.
        p = self.cg.props("steel")
        assert p.inertia == pytest.approx(3100.0, rel=0.01)
        assert p.y_na == pytest.approx(12.05, abs=0.1)

    def test_short_term_composite_n(self):
        p = self.cg.props("n")           # deck / n, positive moment
        assert p.inertia == pytest.approx(10375.0, rel=0.015)
        assert p.y_na == pytest.approx(24.95, abs=0.15)

    def test_long_term_composite_3n(self):
        p = self.cg.props("3n")          # deck / 3n, sustained load
        assert p.inertia == pytest.approx(7768.0, rel=0.015)


class TestServiceStresses:
    """Unfactored bottom-flange stresses per load case (workbook p. 3), each on
    its own section: DC1 on bare steel, DC2/DW on 3n, LL+I on n."""

    def setup_method(self):
        self.cg = _girder()
        self.yb = self.cg.y_bottom_flange
        self.steel = self.cg.props("steel")
        self.n = self.cg.props("n")
        self.tn = self.cg.props("3n")

    def test_dc1_on_bare_steel(self):
        assert self.steel.stress(10.90, self.yb) == pytest.approx(
            0.4926, rel=0.02)

    def test_superimposed_dead_on_3n(self):
        assert self.tn.stress(3.00, self.yb) == pytest.approx(0.0936, rel=0.03)
        assert self.tn.stress(4.70, self.yb) == pytest.approx(0.1466, rel=0.03)

    def test_live_load_on_n(self):
        assert self.n.stress(337.10, self.yb) == pytest.approx(9.582, rel=0.02)

    def test_factored_fcf_is_low_stress(self):
        # Strength I bottom flange (Case A): gamma_p max on DC/DW, 1.75 on LL+.
        fcf = self.cg.flange_stress("bottom", {
            "dc1": 1.25 * 10.90, "dc2": 1.25 * 3.00, "dw": 1.50 * 4.70,
            "ll_pos": 1.75 * 337.10})
        # ~17.5 ksi (no-holes); the workbook's with-holes value is 18.65 ksi.
        # Well below Fyf, which is why the splice design stress floors at 37.5.
        assert fcf == pytest.approx(17.5, rel=0.05)

    def test_flange_fcf_from_loads(self):
        from civilpy.structural.aashto.lrfd import SpliceLoads
        loads = SpliceLoads(dc1_m=10.90, dc2_m=3.00, dw_m=4.70,
                            ll_pos_m=337.10, ll_neg_m=-212.80)
        # bottom flange governed by the positive case (~17.5 ksi no-holes)
        assert self.cg.flange_fcf("bottom", loads) == pytest.approx(
            17.5, rel=0.05)


class TestDesignRolledSplice:
    """The end-to-end wrapper computes fcf from the composite deck section, so
    it reproduces reference Splice #1 with NO MDX-supplied stress."""

    def test_reproduces_splice_1_without_supplied_fcf(self):
        from civilpy.structural.aashto.lrfd import (
            design_rolled_splice, SpliceLoads, BoltSpec, PlatePair, WebPlate,
        )
        loads = SpliceLoads(
            dc1_m=10.90, dc1_v=-10.00, dc2_m=3.00, dc2_v=-2.60,
            dw_m=4.70, dw_v=-4.00, ll_pos_m=337.10, ll_neg_m=-212.80,
            ll_neg_v=-36.60)
        plates = PlatePair("Grade 50", 0.375, 5.5, 0.375, 12.75, 2)
        d = design_rolled_splice(
            "W24X131", "W24X104", loads, grade="Grade 50",
            deck_thickness=7.5, deck_eff_width=84.0, deck_fc=4.0,
            rebar_area=7.46,
            bolts=BoltSpec("A325", 0.875, flange_threads_excluded=False,
                           web_threads_excluded=False, surface_class="C",
                           hole_type="oversize"),
            top_plates=plates, bottom_plates=plates,
            web_plate=WebPlate("Grade 50", 0.4375, 2),
            top_flange_rows=2, bottom_flange_rows=2, web_rows=4,
            bolt_spacing=3.0, flange_edge=1.5, flange_end=1.5,
            web_edge=1.5, web_end=1.5, design_year=2016)
        # fcf floors at Fcf=37.5 -> same 332.53 k / 10 bolts / all OK design
        assert d.top_flange.design_force == pytest.approx(332.53, rel=2e-3)
        assert d.top_flange.total_bolts == 10
        assert d.bottom_flange.total_bolts == 10
        assert d.ok
