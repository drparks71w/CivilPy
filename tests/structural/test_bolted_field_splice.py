#  CivilPy
#  Copyright (C) 2026 Dane Parks
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

"""Validation of the AASHTO 6.13.6.1 bolted-field-splice designer against two
independently worked plate-girder splices.  The expected values are plain
numeric results (bolt counts, plate sizes, design forces, member resistances)
hand-checked against the two reference designs; no copyrighted content is
reproduced here.

Design forces carry a small (<1%) offset from the reference numbers because
this module uses the exact AASHTO 6.13.6.1.3b resistance-factor ratio
phi_u/phi_y = 0.80/0.95 where the reference rounds it to 0.84; the tolerance
below absorbs that."""

import pytest

from civilpy.structural.aashto.lrfd import (
    design_splice, SpliceInput, Flange, GirderSide, SpliceLoads, BoltSpec,
    PlatePair, WebPlate,
)


# ---------------------------------------------------------------------------
# Worked design 1 — composite plate girder, flanges resist the splice moment.
# ---------------------------------------------------------------------------

def _design_one():
    left = GirderSide(
        top_flange=Flange("Grade 50W", 1.0, 16.0),
        bottom_flange=Flange("Grade 50W", 1.375, 18.0),
        web_material="Grade 50W", web_thickness=0.5, web_depth=69.0,
        haunch=1.0, stiffener_spacing_ft=17.25, stiffened=True,
    )
    right = GirderSide(
        top_flange=Flange("HPS Grade 70W", 1.0, 18.0),
        bottom_flange=Flange("HPS Grade 70W", 1.0, 20.0),
        web_material="Grade 50W", web_thickness=0.5625, web_depth=69.0,
        haunch=1.0, stiffener_spacing_ft=12.0, stiffened=True,
    )
    loads = SpliceLoads(
        dc1_m=248, dc1_v=-82, dc2_m=50, dc2_v=-12, dw_m=52, dw_v=-11,
        ll_pos_m=2469, ll_pos_v=19, ll_neg_m=-1754, ll_neg_v=-112,
        deck_cast_m=1300, deck_cast_v=-82,
    )
    bolts = BoltSpec(bolt_type="A325", diameter=0.875,
                     flange_threads_excluded=True, web_threads_excluded=False,
                     surface_class="B", hole_type="standard")
    inp = SpliceInput(
        left=left, right=right, loads=loads, bolts=bolts,
        top_plates=PlatePair("Grade 50W", 0.6875, 7.0, 0.625, 16.0, 2),
        bottom_plates=PlatePair("Grade 50W", 0.875, 8.0, 0.75, 18.0, 2),
        web_plate=WebPlate("Grade 50W", 0.3125, 2),
        deck_composite=True, deck_thickness=9.0, deck_eff_width=144.0, fc=4.0,
        top_flange_rows=4, bottom_flange_rows=4, web_rows=2,
        bolt_spacing=3.0, flange_edge=2.0, flange_end=1.5,
        web_edge=2.0, web_end=1.5, web_weld_size=0.3125,
        web_weld_clearance=0.375, girder_gap=0.75, entering_tightening=3.0,
        design_year=2020,
    )
    return design_splice(inp)


class TestDesignOne:
    def setup_method(self):
        self.d = _design_one()

    def test_factored_load_combinations(self):
        m = self.d.factored_moments
        assert m["deck_cast"] == pytest.approx(1820.0)
        assert m["strength_pos"] == pytest.approx(4771.25)
        assert m["strength_neg"] == pytest.approx(-2767.5)
        assert m["service_pos"] == pytest.approx(3559.7, rel=1e-4)
        assert m["service_neg"] == pytest.approx(-1930.2, rel=1e-4)
        assert self.d.factored_shears["service_neg"] == pytest.approx(-250.6)

    def test_bolt_counts_and_rows(self):
        assert (self.d.top_flange.bolt_rows,
                self.d.top_flange.total_bolts) == (4, 12)
        assert (self.d.web.bolt_rows, self.d.web.total_bolts) == (2, 26)
        assert (self.d.bottom_flange.bolt_rows,
                self.d.bottom_flange.total_bolts) == (4, 24)

    def test_flange_design_forces(self):
        # Reference Pfy: top 720.3, bottom 1152.1 (kip); 0.84-vs-exact offset.
        assert self.d.top_flange.design_force == pytest.approx(720.3, rel=0.01)
        assert self.d.bottom_flange.design_force == pytest.approx(
            1152.1, rel=0.01)

    def test_filler_reduction_factor(self):
        # No filler on the top flange, R = 1; bottom flange R = 0.7985.
        assert self.d.top_flange.extra["filler_R"] == pytest.approx(1.0)
        assert self.d.bottom_flange.extra["filler_R"] == pytest.approx(
            0.79851, rel=1e-4)

    def test_flange_layout(self):
        t = self.d.top_flange
        assert (t.gage_bolts, t.gage_groups, t.pitch, t.end) == (3, 6, 3, 1.5)
        assert t.pitch_groups == pytest.approx(3.75)
        b = self.d.bottom_flange
        assert (b.gage_bolts, b.gage_groups) == (4, 6)

    def test_splice_plate_lengths(self):
        assert self.d.top_flange.plate_length == pytest.approx(18.75)
        assert self.d.bottom_flange.plate_length == pytest.approx(36.75)

    def test_web_layout_and_plate(self):
        w = self.d.web
        assert w.pitch == pytest.approx(5.0)
        assert w.plate_length == pytest.approx(63.0)   # splice-plate height
        assert w.plate_width == pytest.approx(14.75)
        assert w.gage_groups == pytest.approx(4.75)
        assert w.design_force == pytest.approx(467.91, rel=1e-3)  # phi*Vn

    def test_all_checks_pass(self):
        assert self.d.ok
        top = {c.name: c for c in self.d.top_flange.checks}
        # Block shear on the top flange: Mode 1 = 900.9 kip, Mode 2 governs at
        # 737.45 kip (both factored, reference values).
        assert top["girder flange block shear (Mode 2)"].factored_capacity \
            == pytest.approx(737.45, rel=1e-3)
        assert top["girder flange block shear (Mode 1)"].factored_capacity \
            == pytest.approx(900.9, rel=1e-3)
        # Composite slab crushing resistance 0.85 f'c b ts = 4406.4 kip.
        bottom = {c.name: c for c in self.d.bottom_flange.checks}
        assert bottom["composite slab crushing"].capacity == pytest.approx(
            4406.4)


# ---------------------------------------------------------------------------
# Worked design 2 — deeper girder, unstiffened left web, moment-critical.
# The flanges are over-stressed at Service II: the negative-moment slip check
# is expected to fail (mirrors the reference NOTICE), so the overall design is
# not "ok".  Bolt sizing and layout still match the reference.
# ---------------------------------------------------------------------------

def _design_two():
    left = GirderSide(
        top_flange=Flange("Grade 50", 1.0, 19.0),
        bottom_flange=Flange("Grade 50", 1.4375, 20.0),
        web_material="Grade 50W", web_thickness=0.75, web_depth=109.0,
        haunch=2.0, stiffener_spacing_ft=0.0, stiffened=False,
    )
    right = GirderSide(
        top_flange=Flange("Grade 50", 2.0, 22.0),
        bottom_flange=Flange("Grade 50", 2.25, 24.0),
        web_material="Grade 50W", web_thickness=0.75, web_depth=109.0,
        haunch=2.0, stiffener_spacing_ft=27.25, stiffened=True,
    )
    loads = SpliceLoads(
        dc1_m=-1564, dc1_v=-147, dc2_m=-242, dc2_v=-28, dw_m=-315, dw_v=-37,
        ll_pos_m=5627, ll_pos_v=19, ll_neg_m=-7117, ll_neg_v=-126,
        deck_cast_m=3006, deck_cast_v=-79,
    )
    bolts = BoltSpec(bolt_type="A325", diameter=0.875,
                     flange_threads_excluded=True, web_threads_excluded=False,
                     surface_class="B", hole_type="standard")
    inp = SpliceInput(
        left=left, right=right, loads=loads, bolts=bolts,
        top_plates=PlatePair("Grade 50", 0.625, 8.5, 0.5625, 19.0, 2),
        bottom_plates=PlatePair("Grade 50", 0.875, 9.0, 0.8125, 20.0, 2),
        web_plate=WebPlate("Grade 50", 0.4375, 2),
        deck_composite=True, deck_thickness=8.0, deck_eff_width=114.0, fc=4.0,
        top_flange_rows=4, bottom_flange_rows=4, web_rows=2,
        bolt_spacing=3.0, flange_edge=2.0, flange_end=1.125,
        web_edge=2.0, web_end=1.75, web_weld_size=0.3125,
        web_weld_clearance=0.25, girder_gap=0.75, entering_tightening=3.0,
        design_year=2020,
    )
    return design_splice(inp)


class TestDesignTwo:
    def setup_method(self):
        self.d = _design_two()

    def test_flange_bolt_counts(self):
        # Strength (not slip) governs the count: top 20, bottom 28.
        assert self.d.top_flange.total_bolts == 20
        assert self.d.top_flange.strength_bolts == 20
        assert self.d.bottom_flange.total_bolts == 28

    def test_flange_layout_and_plates(self):
        t = self.d.top_flange
        assert (t.gage_bolts, t.end) == (4.5, 1.125)
        assert t.plate_length == pytest.approx(29.25)
        b = self.d.bottom_flange
        assert b.gage_bolts == 5
        assert b.plate_length == pytest.approx(41.25)

    def test_filler_on_thinner_flange(self):
        # Top flange has a 1-in filler (t_left=1, t_right=2): R = 2/3.
        assert self.d.top_flange.extra["filler_R"] == pytest.approx(
            2.0 / 3.0, rel=1e-4)

    def test_service_slip_governs_notice(self):
        # Over-stressed flanges: the negative Service II slip check fails,
        # matching the reference NOTICE; the overall design is not ok.
        slip = {c.name: c for c in self.d.top_flange.checks}[
            "top flange Service II slip"]
        assert slip.ok is False
        assert not self.d.ok
