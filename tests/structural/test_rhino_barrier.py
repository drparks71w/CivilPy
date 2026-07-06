#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""G7 -- traffic barriers, portable concrete barriers, steel railings, lane
markings, and reinforcement built from a girder-line model. Checks the shape
classification, the placement/geometry counts, the dead-load quantities, the
rebar cages, and the tag round-trip the DeckBarrier / DeckLaneLines
importers consume."""

import warnings

import pytest

rhino3dm = pytest.importorskip("rhino3dm")

from civilpy.structural.rhino_gdr import GTAG
from civilpy.structural.rhino_barrier import (
    build_barriers, build_lane_lines, read_barrier_model, barrier_dc2_klf,
    shape_family, bar_diameter_in, barrier_profile,
)
from civilpy.structural.odot.bridge_railing import BRIDGE_RAILINGS


def _tag(obj_attr, **kv):
    for k, v in kv.items():
        obj_attr.SetUserString(GTAG + k, str(v))


def _author_girders(path, *, ys=(0.0, 7.0, 14.0, 21.0, 28.0)):
    f = rhino3dm.File3dm()
    f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Feet
    for i, y in enumerate(ys, start=1):
        pl = rhino3dm.Polyline()
        for x in (0.0, 60.0, 120.0):
            pl.Add(x, y, 0.0)
        ga = rhino3dm.ObjectAttributes()
        _tag(ga, kind="girder", shape="W24X104", grade="Grade 50", line=i)
        f.Objects.AddCurve(pl.ToPolylineCurve(), ga)
        for x in (0.0, 120.0):
            ba = rhino3dm.ObjectAttributes()
            _tag(ba, kind="support", fixity="expansion", line=i)
            f.Objects.AddPoint(rhino3dm.Point3d(x, y, 0.0), ba)
    assert f.Write(str(path), 7)


@pytest.fixture
def girders(tmp_path):
    p = tmp_path / "girders.3dm"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _author_girders(p)
    return str(p)


def test_bar_diameter():
    assert bar_diameter_in(5) == pytest.approx(0.625)
    assert bar_diameter_in(8) == pytest.approx(1.0)


def test_shape_family_classification():
    assert shape_family(BRIDGE_RAILINGS["BR-1 (36 in)"]) == "new jersey"
    assert shape_family(BRIDGE_RAILINGS["SBR-3 (36 in)"]) == "single slope"
    assert shape_family(BRIDGE_RAILINGS["TST-2 (three steel tube)"]) == "steel tube"
    assert shape_family(BRIDGE_RAILINGS["PCB (portable, unanchored)"]) == "portable"
    # BR-2-15's shape string ("combination (barrier + steel tube)") contains
    # "tube" as a substring -- regression guard for it being misclassified
    # as a bare steel-tube railing (which would draw only a 10 in curb
    # instead of the full 42 in crashworthy concrete barrier).
    assert shape_family(
        BRIDGE_RAILINGS["BR-2 (sidewalk barrier + twin tube)"]) == "combination"


def test_combination_profile_is_full_height_not_a_curb():
    r = BRIDGE_RAILINGS["BR-2 (sidewalk barrier + twin tube)"]
    prof = barrier_profile(r, 42.0 / 12.0, side=+1)
    assert max(z for _, z in prof) == pytest.approx(3.5)   # full 42 in, not 10 in
    offs = [o for o, _ in prof]
    assert max(offs) - min(offs) == pytest.approx(1.0)     # 12 in rectangular section


def test_barrier_dc2_matches_catalog():
    # BR-1 (36 in): 423.25 in^2 gross section
    assert barrier_dc2_klf("BR-1 (36 in)") == pytest.approx(423.25 / 144 * 0.150)
    # TST-2 steel railing priced by weight_per_ft (80 lb/ft)
    assert barrier_dc2_klf("TST-2 (three steel tube)") == pytest.approx(0.080)


def test_nj_profile_shape():
    # NJ back face vertical on the line (offset 0 at base and top); body inward
    prof = barrier_profile(BRIDGE_RAILINGS["BR-1 (36 in)"], 3.0, side=+1)
    offs = [o for o, _ in prof]
    assert min(offs) == pytest.approx(0.0)       # back face on the line
    assert max(offs) == pytest.approx(1.5)       # 18 in base width
    assert max(z for _, z in prof) == pytest.approx(3.0)   # 36 in tall


class TestBuildBarriers:
    def test_edges_with_rebar(self, girders, tmp_path):
        out = tmp_path / "barriers.3dm"
        bm = build_barriers(girders, out_path=out, designation="BR-1 (36 in)")
        assert bm.n_placements == 2
        assert bm.n_barrier == 2
        assert bm.n_steel == 0
        assert bm.n_rebar > 0
        assert bm.dc2_klf_each == pytest.approx(423.25 / 144 * 0.150)
        assert bm.total_dc2_klf == pytest.approx(2 * bm.dc2_klf_each)

    def test_rebar_can_be_disabled(self, girders, tmp_path):
        bm = build_barriers(girders, out_path=tmp_path / "b.3dm",
                            designation="BR-1 (36 in)", rebar=False)
        assert bm.n_rebar == 0

    def test_vertical_bar_count_follows_spacing(self, girders, tmp_path):
        # 120 ft long, BR-1 vertical bars at 12 in (1 ft) o.c. -> 120 per run,
        # 2 runs = 240 vertical bars, plus longitudinal bars on top
        bm = build_barriers(girders, out_path=tmp_path / "b.3dm",
                            designation="BR-1 (36 in)", long_spacing_in=12.0)
        assert bm.n_rebar >= 240

    def test_portable_median_placement(self, girders, tmp_path):
        out = tmp_path / "pcb.3dm"
        bm = build_barriers(girders, out_path=out,
                            designation="PCB (portable, unanchored)",
                            placements="median")
        assert bm.shape_family == "portable"
        assert bm.n_placements == 1
        assert bm.n_barrier == 1
        # F-shape is symmetric about the centerline (Y = 14 ft here)
        prof = barrier_profile(BRIDGE_RAILINGS["PCB (portable, unanchored)"],
                               32.0 / 12.0, side=0)
        offs = [o for o, _ in prof]
        assert min(offs) == pytest.approx(-max(offs))

    def test_steel_tube_adds_posts_and_rails(self, girders, tmp_path):
        bm = build_barriers(girders, out_path=tmp_path / "tst.3dm",
                            designation="TST-2 (three steel tube)")
        assert bm.shape_family == "steel tube"
        assert bm.n_steel > 0        # posts + rail tubes
        assert bm.n_rebar == 0       # steel railing carries no concrete cage

    def test_combination_barrier_gets_both_concrete_cage_and_rail(
            self, girders, tmp_path):
        bm = build_barriers(girders, out_path=tmp_path / "br2.3dm",
                            designation="BR-2 (sidewalk barrier + twin tube)")
        assert bm.shape_family == "combination"
        assert bm.n_barrier == 2
        assert bm.n_steel > 0   # pedestrian rail posts/tubes on top
        assert bm.n_rebar > 0   # the 42 in barrier is itself reinforced

    def test_roundtrip_tags(self, girders, tmp_path):
        out = tmp_path / "barriers.3dm"
        build_barriers(girders, out_path=out, designation="BR-1 (36 in)")
        rows = read_barrier_model(str(out))
        bodies = [r for r in rows if r["kind"] == "barrier"
                  and r["attrs"].get("part") == "body"]
        assert len(bodies) == 2
        assert bodies[0]["attrs"]["designation"] == "BR-1 (36 in)"
        assert bodies[0]["attrs"]["shape"] == "new jersey"
        assert bodies[0]["attrs"]["dc2"] == pytest.approx(
            423.25 / 144 * 0.150, abs=1e-4)
        rebar = [r for r in rows if r["kind"] == "rebar"]
        assert rebar and rebar[0]["attrs"]["host"] == "barrier"

    def test_unknown_designation_rejected(self, girders, tmp_path):
        with pytest.raises(KeyError, match="unknown bridge-railing"):
            build_barriers(girders, out_path=tmp_path / "x.3dm",
                          designation="NOPE-99")


class TestLaneLines:
    def test_lane_count_and_lines(self, girders, tmp_path):
        out = tmp_path / "lanes.3dm"
        # usable width ~ 35 ft deck - 2 x 18 in barrier bases = 32 ft -> ~3 lanes
        lm = build_lane_lines(girders, out_path=out)
        assert lm.n_lanes == round(lm.usable_width_ft / 12.0)
        assert lm.n_edge_lines == 2
        assert lm.n_divider_lines == lm.n_lanes - 1
        assert lm.n_objects > lm.n_edge_lines   # dashed dividers add segments

    def test_explicit_lane_count(self, girders, tmp_path):
        lm = build_lane_lines(girders, out_path=tmp_path / "l.3dm", n_lanes=2)
        assert lm.n_lanes == 2
        assert lm.n_divider_lines == 1

    def test_roundtrip_tags(self, girders, tmp_path):
        out = tmp_path / "lanes.3dm"
        build_lane_lines(str(out) and girders, out_path=out, n_lanes=2)
        rows = read_barrier_model(str(out))
        assert rows and all(r["kind"] == "lane_line" for r in rows)
        types = {r["attrs"]["type"] for r in rows}
        assert types == {"edge", "divider"}
        styles = {r["attrs"]["style"] for r in rows}
        assert styles == {"solid", "dashed"}
