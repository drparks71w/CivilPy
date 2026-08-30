"""Tests for civilpy.structural.gusset_geometry (pure geometry, inches)."""
import math

import pytest

from civilpy.structural import gusset_geometry as gg


def square_plate(size=60.0, t=0.625):
    return gg.GussetPlate(gg.polygon_from_bbox(0, 0, size, size), t, label="test")


def vertical_member(n_rows=5, n_cols=4, pitch=3.0, wp=(30.0, 30.0)):
    # member goes straight down from the work point; first row (farthest from
    # the joint) is at the bottom
    fs = gg.rectangular_grid((wp[0], wp[1] - 12.0), (0, -1), n_rows, n_cols, pitch, pitch)
    return gg.MemberEnd("U0L0", wp, (0, -1), fs, member_type="vertical")


def test_polygon_and_point_helpers():
    poly = gg.polygon_from_bbox(0, 0, 10, 5)
    assert gg.polygon_area(poly) == pytest.approx(50.0)
    assert gg.point_in_polygon((5, 2.5), poly)
    assert not gg.point_in_polygon((11, 2.5), poly)
    segs = gg.clip_segment((-5, 2.5), (15, 2.5), poly)
    assert len(segs) == 1 and math.isclose(gg._length(*segs[0]), 10.0)


def test_rows_and_whitmore_width():
    m = vertical_member()
    rows = m.rows()
    assert len(rows) == 5 and all(len(r) == 4 for r in rows)
    # connection length = 4 pitches, first-row width = 3 pitches
    assert m.connection_length == pytest.approx(12.0)
    assert m.first_row_width() == pytest.approx(9.0)
    assert m.whitmore_width() == pytest.approx(9.0 + 2 * 12.0 * math.tan(math.radians(30)))
    assert m.n_fasteners == 20


def test_whitmore_areas_gross_and_net():
    plate = square_plate()
    m = vertical_member()
    j = gg.GussetJoint("J", (30, 30), plate, members=[m])
    w = j.whitmore(m)
    b = m.whitmore_width()
    assert w["length_in_plate"] == pytest.approx(b)          # fits inside the 60" plate
    assert w["A_gross"] == pytest.approx(b * 0.625, rel=1e-3)
    # the last row (nearest the joint) has 4 holes of 1 1/8"
    assert w["A_net"] == pytest.approx(b * 0.625 - 4 * 1.125 * 0.625, rel=1e-3)


def test_whitmore_clipped_by_plate_edge():
    plate = gg.GussetPlate(gg.polygon_from_bbox(25, 0, 35, 60), 0.5)   # narrow 10" plate
    m = vertical_member()
    j = gg.GussetJoint("J", (30, 30), plate, members=[m])
    w = j.whitmore(m)
    assert w["length_in_plate"] == pytest.approx(10.0)
    assert w["A_gross"] == pytest.approx(5.0, rel=1e-3)


def test_unbraced_lengths_to_adjacent_member_and_edge():
    plate = square_plate()
    m = vertical_member()                       # last row at y = 18
    # a horizontal chord with a fastener row at y = 27 directly above the vertical
    chord_fs = gg.rectangular_grid((10, 27), (1, 0), 10, 1, 3.0, 3.0)
    chord = gg.MemberEnd("U0U1", (30, 30), (1, 0), chord_fs, member_type="chord", is_chord=True)
    j = gg.GussetJoint("J", (30, 30), plate, members=[m, chord])
    lc = j.unbraced_lengths(m)
    # from the Whitmore line (y=18) up to the chord fasteners at y=27 -> 9" at
    # the middle and the left end; the right end of the Whitmore line lies
    # beyond the chord's last fastener, so that ray runs to the plate edge (42")
    assert lc["Lmid"] == pytest.approx(9.0, abs=0.01)
    assert lc["L1"] == pytest.approx(9.0, abs=0.01)
    assert lc["L2"] == pytest.approx(42.0, abs=0.01)
    assert lc["Lc_avg"] == pytest.approx(20.0, abs=0.01)
    assert lc["Lc_min"] == pytest.approx(9.0, abs=0.01)
    # without the chord the ray reaches the plate edge (y = 60): 42"
    j2 = gg.GussetJoint("J", (30, 30), plate, members=[m])
    assert j2.unbraced_lengths(m)["Lmid"] == pytest.approx(42.0, abs=0.01)


def test_block_shear_areas():
    plate = square_plate(t=0.5)
    m = vertical_member()
    j = gg.GussetJoint("J", (30, 30), plate, members=[m])
    bs = j.block_shear(m)
    assert bs["shear_length"] == pytest.approx(12.0)
    assert bs["tension_width"] == pytest.approx(9.0)
    assert bs["A_vg"] == pytest.approx(2 * 12.0 * 0.5)
    # 5 holes per shear plane, the last-row hole counted half: 4.5 holes x 1.125 x 0.5 each plane
    assert bs["A_vn"] == pytest.approx(2 * (12.0 - 4.5 * 1.125) * 0.5, rel=1e-3)
    # tension plane 9" with 4 holes, corner holes half each -> 3 holes
    assert bs["A_tn"] == pytest.approx((9.0 - 3 * 1.125) * 0.5, rel=1e-3)


def test_thickness_field_patch_reduces_areas():
    field = gg.ThicknessField(0.625, [gg.ThicknessPatch(gg.polygon_from_bbox(20, 15, 40, 21), 0.325, "pit")])
    plate = gg.GussetPlate(gg.polygon_from_bbox(0, 0, 60, 60), field)
    m = vertical_member()
    j = gg.GussetJoint("J", (30, 30), plate, members=[m])
    w = j.whitmore(m)                      # Whitmore line at y = 18 crosses the patch x 20..40
    b = m.whitmore_width()
    expected = (b - 20.0) * 0.625 + 20.0 * 0.325
    assert w["A_gross"] == pytest.approx(expected, rel=0.02)
    assert field.t_at((30, 18)) == pytest.approx(0.325)
    assert field.t_at((5, 5)) == pytest.approx(0.625)


def test_section_cuts_and_edges():
    plate = square_plate(t=0.5)
    m = vertical_member()
    j = gg.GussetJoint("J", (30, 30), plate, members=[m])
    h = j.horizontal_section(18.0)         # through the last fastener row
    assert h["length"] == pytest.approx(60.0)
    assert h["A_net"] == pytest.approx(60 * 0.5 - 4 * 1.125 * 0.5, rel=1e-3)
    assert j.max_unsupported_edge() == pytest.approx(60.0)


def test_scan_to_thickness_field():
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(0)
    xs, ys = np.meshgrid(np.arange(0, 20, 0.25), np.arange(0, 12, 0.25))
    z = rng.normal(0, 0.002, xs.shape)                    # scanner noise
    pit = (xs > 8) & (xs < 12) & (ys > 4) & (ys < 7)
    z[pit] -= 0.15                                        # 0.15" deep pit
    pts = np.column_stack([xs.ravel(), ys.ravel(), z.ravel()])
    fld, info = gg.thickness_field_from_points(pts, 0.5, cell=1.0, min_depth=0.05)
    assert fld.patches, "pit not detected"
    depths = [0.5 - p.t_remaining for p in fld.patches]
    assert max(depths) == pytest.approx(0.15, abs=0.02)
    # patches cover roughly the 4" x 3" pit
    assert 8 <= len(fld.patches) <= 24
    assert fld.t_at((10, 5.5)) < 0.4 and fld.t_at((2, 2)) == pytest.approx(0.5)
