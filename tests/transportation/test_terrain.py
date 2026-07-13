"""Tests for the Terrain ground-surface object."""

import numpy as np
import pytest

from civilpy.transportation.alignment import Alignment, Tangent
from civilpy.transportation.terrain import Terrain


def _plane_grid(a=0.02, b=0.01, c=500.0, n=6, span=100.0):
    """A grid sampling the plane z = c + a*x + b*y over [0, span]^2."""
    gx, gy = np.meshgrid(np.linspace(0, span, n), np.linspace(0, span, n))
    z = c + a * gx + b * gy
    return np.column_stack([gx.ravel(), gy.ravel(), z.ravel()]), (a, b, c)


def test_from_points_interpolates_plane_exactly():
    pts, (a, b, c) = _plane_grid()
    t = Terrain.from_points(pts)
    for x, y in [(50.0, 50.0), (12.3, 88.1), (5.0, 95.0)]:
        assert t.elevation_at(x, y) == pytest.approx(c + a * x + b * y, abs=1e-6)


def test_outside_hull_returns_none():
    pts, _ = _plane_grid()
    t = Terrain.from_points(pts)
    assert t.elevation_at(-10.0, 50.0) is None
    assert t.elevation_at(50.0, 250.0) is None


def test_bounds_and_counts():
    pts, _ = _plane_grid(n=6, span=100.0)
    t = Terrain.from_points(pts)
    assert t.bounds == pytest.approx((0.0, 0.0, 100.0, 100.0))
    assert t.n_points == 36
    assert t.n_triangles > 0


def test_elevation_along_alignment():
    pts, (a, b, c) = _plane_grid()
    t = Terrain.from_points(pts)
    al = Alignment(start_point=(50.0, 0.0), start_bearing_deg=0.0,
                   elements=[Tangent(100.0)])
    # 30 ft up the (north) tangent, 10 ft right (east) -> x=60, y=30
    z = t.elevation_along(al, 30.0, 10.0)
    assert z == pytest.approx(c + a * 60.0 + b * 30.0, abs=1e-6)
    prof = t.profile(al, [0.0, 50.0, 100.0])
    assert all(v is not None for v in prof)


def test_clip_to_bbox():
    pts, _ = _plane_grid(n=11, span=100.0)
    t = Terrain.from_points(pts)
    clipped = t.clip_to_bbox(20.0, 20.0, 80.0, 80.0)
    assert clipped.n_points < t.n_points
    x0, y0, x1, y1 = clipped.bounds
    assert x0 >= 20.0 and y0 >= 20.0 and x1 <= 80.0 and y1 <= 80.0
    assert clipped.elevation_at(50.0, 50.0) is not None


def test_clip_to_corridor():
    gx, gy = np.meshgrid(np.linspace(-50, 50, 21), np.linspace(0, 100, 21))
    z = 500.0 + 0.0 * gx
    pts = np.column_stack([gx.ravel(), gy.ravel(), z.ravel()])
    t = Terrain.from_points(pts)
    al = Alignment(start_point=(0.0, 0.0), start_bearing_deg=0.0,
                   elements=[Tangent(100.0)])
    corr = t.clip_to_corridor(al, 20.0, step_ft=10.0)
    x0, _, x1, _ = corr.bounds
    assert x0 >= -20.0 - 1e-9 and x1 <= 20.0 + 1e-9
    assert corr.n_points < t.n_points


_LANDXML = """<?xml version="1.0"?>
<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
  <Surfaces>
    <Surface name="EG">
      <Definition surfType="TIN">
        <Pnts>
          <P id="1">0 0 100</P>
          <P id="2">0 100 110</P>
          <P id="3">100 100 110</P>
          <P id="4">100 0 100</P>
        </Pnts>
        <Faces>
          <F>1 2 3</F>
          <F>1 3 4</F>
        </Faces>
      </Definition>
    </Surface>
  </Surfaces>
</LandXML>
"""


def test_from_landxml_honors_faces(tmp_path):
    p = tmp_path / "eg.xml"
    p.write_text(_LANDXML)
    t = Terrain.from_landxml(p)
    assert t.n_points == 4
    assert t.n_triangles == 2
    # plane is z = 100 + 0.1 * easting (independent of northing)
    assert t.elevation_at(50.0, 50.0) == pytest.approx(105.0, abs=1e-6)
    assert t.elevation_at(10.0, 90.0) == pytest.approx(101.0, abs=1e-6)
    assert t.elevation_at(-5.0, 50.0) is None


def test_from_xyz_file(tmp_path):
    pts, (a, b, c) = _plane_grid()
    p = tmp_path / "cloud.xyz"
    np.savetxt(p, pts)
    t = Terrain.from_xyz_file(p)
    assert t.n_points == len(pts)
    assert t.elevation_at(50.0, 50.0) == pytest.approx(c + a * 50 + b * 50,
                                                       abs=1e-6)


def test_bad_input_shapes():
    with pytest.raises(ValueError):
        Terrain(np.zeros((2, 3)))          # too few points
    with pytest.raises(ValueError):
        Terrain(np.zeros((5, 2)))          # not x, y, z


def test_from_las_lazy_import():
    # laspy isn't installed in this env; the query core must not need it,
    # and from_las should raise a clear ImportError rather than crash.
    laspy = pytest.importorskip("laspy") if False else None
    try:
        import laspy  # noqa: F401
        pytest.skip("laspy installed; lazy-import path not exercised")
    except ImportError:
        with pytest.raises(ImportError):
            Terrain.from_las("nonexistent.las")


def test_bbox_picker_draw_round_trip():
    ipyleaflet = pytest.importorskip("ipyleaflet")  # noqa: F841
    from civilpy.transportation.terrain import bbox_picker

    rect = {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[
        [-83.010, 40.000], [-83.010, 40.008], [-83.000, 40.008],
        [-83.000, 40.000], [-83.010, 40.000]]]}}

    # the reliable path: the frontend syncing the DrawControl data trait
    p = bbox_picker()
    assert p.bbox is None
    p._draw.data = [rect]
    # (xmin, ymin, xmax, ymax) in lon/lat -- the from_ogrip tuple
    assert p.bbox == (-83.010, 40.000, -83.000, 40.008)
    assert "bbox = (" in p._label.value

    # the legacy path: the on_draw custom message, when the frontend sends it
    p2 = bbox_picker()
    p2._on_draw(None, "created", rect)
    assert p2.bbox == (-83.010, 40.000, -83.000, 40.008)
