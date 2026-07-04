#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""G4 -- the ``gdr.*`` reader.  Authors a small tagged ``.3dm`` (two girder
lines with bearings and the document-level bridge parameters, exactly what the
C# GirderLines/GirderShape/GirderBearing commands stamp) and reads it back into
the canonical hub, mirroring the round-trip style of ``test_rhino_stm``."""

import warnings

import pytest

rhino3dm = pytest.importorskip("rhino3dm")

from civilpy.structural.rhino_gdr import GTAG, read_girder_model


def _tag(obj_attr, **kv):
    for k, v in kv.items():
        obj_attr.SetUserString(GTAG + k, str(v))


def _author_bridge(path):
    """A 2-girder, 2-span continuous frame in PLAN (feet): girders run along X
    at Y = 0 and 8 ft, supported at X = 0, 60, 120 ft (fixed at the pier)."""
    f = rhino3dm.File3dm()
    f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Feet

    stations = [0.0, 60.0, 120.0]
    for line_no, y in ((1, 0.0), (2, 8.0)):
        # one polyline girder line per girder, spanning both spans
        pl = rhino3dm.Polyline()
        for x in stations:
            pl.Add(x, y, 0.0)
        crv = pl.ToPolylineCurve()
        ga = rhino3dm.ObjectAttributes()
        shape = "w24x104" if line_no == 1 else "W24 X 104"  # normalizer test
        _tag(ga, kind="girder", shape=shape, grade="Grade 50", line=line_no)
        f.Objects.AddCurve(crv, ga)
        # bearings: expansion at the abutments, fixed at the interior pier
        for x, fixity in ((0.0, "expansion"), (60.0, "fixed"),
                          (120.0, "expansion")):
            ba = rhino3dm.ObjectAttributes()
            _tag(ba, kind="support", fixity=fixity, line=line_no)
            f.Objects.AddPoint(rhino3dm.Point3d(x, y, 0.0), ba)

    # bridge-wide parameters ride on a gdr.kind=bridge marker object's user
    # text (rhino3dm cannot read RhinoDoc.Strings).
    da = rhino3dm.ObjectAttributes()
    _tag(da, kind="bridge", deck_t="7.5", deck_weff="84", deck_fc="4.5",
         ship_max="100", bolt_dia="0.875", bolt_spec="A325",
         bolt_hole="oversize", bolt_class="C")
    f.Objects.AddPoint(rhino3dm.Point3d(0.0, -4.0, 0.0), da)

    assert f.Write(str(path), 7)


@pytest.fixture
def bridge(tmp_path):
    p = tmp_path / "gdr_bridge.3dm"
    _author_bridge(p)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # AISC-db lookups, etc.
        return read_girder_model(str(p))


class TestGdrReader:
    def test_two_girder_lines(self, bridge):
        assert set(bridge.girder_lines) == {"1", "2"}
        # each girder line spans 2 segments (3 stations -> 2 elements)
        assert all(len(ids) == 2 for ids in bridge.girder_lines.values())
        assert len(bridge.model.elements) == 4

    def test_section_and_grade_on_elements(self, bridge):
        for elem in bridge.model.elements.values():
            assert elem.section == "W24X104"      # normalized both spellings
            assert elem.material == "Grade 50"
            assert elem.role == "girder"
            assert elem.midas_type == "BEAM"

    def test_line_metadata_preserved(self, bridge):
        lines = {e.metadata.get("gdr.line") for e in bridge.model.elements.values()}
        assert lines == {"1", "2"}

    def test_bearings_become_restraints(self, bridge):
        # 3 bearings x 2 lines = 6, but the two lines' ends are distinct nodes
        assert len(bridge.model.restraints) == 6
        presets = sorted(r.preset for r in bridge.model.restraints.values())
        assert presets == ["expansion", "expansion", "expansion",
                            "expansion", "fixed", "fixed"]

    def test_fixed_vs_expansion_dof(self, bridge):
        fixed = [r for r in bridge.model.restraints.values()
                 if r.preset == "fixed"]
        expansion = [r for r in bridge.model.restraints.values()
                     if r.preset == "expansion"]
        for r in fixed:                       # holds longitudinal (X)
            assert (r.fix_x, r.fix_y, r.fix_z) == (True, True, True)
        for r in expansion:                   # frees longitudinal (X)
            assert (r.fix_x, r.fix_y, r.fix_z) == (False, True, True)

    def test_bridge_parameters(self, bridge):
        assert bridge.deck_t == pytest.approx(7.5)
        assert bridge.deck_weff == pytest.approx(84.0)
        assert bridge.deck_fc == pytest.approx(4.5)
        assert bridge.ship_max == pytest.approx(100.0)
        assert (bridge.bolt_spec, bridge.bolt_hole, bridge.bolt_class) == (
            "A325", "oversize", "C")

    def test_geometry_in_feet(self, bridge):
        xs = sorted({round(n.x, 3) for n in bridge.model.nodes.values()})
        assert xs == [0.0, 60.0, 120.0]
        ys = sorted({round(n.y, 3) for n in bridge.model.nodes.values()})
        assert ys == [0.0, 8.0]


class TestSpliceWriteBack:
    """G8 -- write a designed splice's status/summary/checks back to a .3dm and
    read them back (the round-trip the C# GirderSplice command consumes)."""

    def _design(self):
        from civilpy.structural.aashto.lrfd import (
            design_rolled_splice, SpliceLoads, BoltSpec, PlatePair, WebPlate,
        )
        loads = SpliceLoads(dc1_m=10.90, dc2_m=3.00, dw_m=4.70,
                            ll_pos_m=337.10, ll_neg_m=-212.80, ll_neg_v=-36.60)
        plates = PlatePair("Grade 50", 0.375, 5.5, 0.375, 12.75, 2)
        return design_rolled_splice(
            "W24X131", "W24X104", loads, deck_thickness=7.5,
            deck_eff_width=84.0, rebar_area=7.46,
            bolts=BoltSpec("A325", 0.875, flange_threads_excluded=False,
                           web_threads_excluded=False, surface_class="C",
                           hole_type="oversize"),
            top_plates=plates, bottom_plates=plates,
            web_plate=WebPlate("Grade 50", 0.4375, 2),
            top_flange_rows=2, bottom_flange_rows=2, web_rows=4,
            bolt_spacing=3.0, flange_edge=1.5, flange_end=1.5,
            web_edge=1.5, web_end=1.5, design_year=2016)

    def test_tags_and_roundtrip(self, tmp_path):
        from civilpy.structural.rhino_gdr import (
            splice_writeback_tags, write_splice_results, read_splice_results,
            SpliceMarker, GTAG,
        )
        design = self._design()
        tags = splice_writeback_tags(design)
        assert tags[GTAG + "status"] == "OK"           # Splice #1 passes
        assert "10 bolts/flange" in tags[GTAG + "summary"]
        # every checks row is a 5-field article|check|actual|allowable|verdict
        rows = tags[GTAG + "checks"].splitlines()
        assert rows and all(len(r.split("|")) == 5 for r in rows)

        p = tmp_path / "splice_results.3dm"
        n = write_splice_results(p, [
            SpliceMarker(point=(100.0, 0.0, 0.0), design=design, line="1")])
        assert n == 1
        got = read_splice_results(str(p))
        assert len(got) == 1
        m = got[0]
        assert m["status"] == "OK" and m["line"] == "1"
        assert m["point"][0] == pytest.approx(100.0)
        assert all(len(rec) == 5 for rec in m["checks"])
        assert all(rec[4] in ("OK", "NG") for rec in m["checks"])


def test_missing_deck_params_warn(tmp_path):
    """Absent gdr.deck_t / gdr.deck_weff must warn loudly (G4 contract)."""
    f = rhino3dm.File3dm()
    f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Feet
    pl = rhino3dm.Polyline()
    pl.Add(0.0, 0.0, 0.0)
    pl.Add(60.0, 0.0, 0.0)
    ga = rhino3dm.ObjectAttributes()
    _tag(ga, kind="girder", shape="W24X104", grade="Grade 50", line=1)
    f.Objects.AddCurve(pl.ToPolylineCurve(), ga)
    p = tmp_path / "no_deck.3dm"
    assert f.Write(str(p), 7)

    with pytest.warns(UserWarning, match="deck_t"):
        b = read_girder_model(str(p))
    assert b.deck_t is None and b.deck_weff is None
    assert b.deck_fc == pytest.approx(4.0)   # falls back to the BDM default
