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


# ── LiDAR ingest (laspy / open3d now available) ───────────────────────────

def _write_las(path, pts, classification=None):
    """A minimal LAS file holding ``pts`` (Nx3) with optional classes."""
    laspy = pytest.importorskip("laspy")
    header = laspy.LasHeader(point_format=3, version="1.2")
    header.offsets = pts.min(axis=0)
    header.scales = [0.001, 0.001, 0.001]
    las = laspy.LasData(header)
    las.x, las.y, las.z = pts[:, 0], pts[:, 1], pts[:, 2]
    if classification is not None:
        las.classification = np.asarray(classification, dtype=np.uint8)
    las.write(str(path))
    return path


class TestFromLas:
    def test_reads_ground_returns_only(self, tmp_path):
        pts, (a, b, c) = _plane_grid(n=8)
        # half the points are class 1 (unclassified) noise well above ground
        noise = pts.copy()
        noise[:, 2] += 75.0
        allpts = np.vstack([pts, noise])
        cls = [2] * len(pts) + [1] * len(noise)
        f = _write_las(tmp_path / "g.las", allpts, cls)

        t = Terrain.from_las(f)
        assert t.n_points == len(pts)
        assert t.elevation_at(50.0, 50.0) == pytest.approx(
            c + a * 50.0 + b * 50.0, abs=0.05)

    def test_ground_only_false_keeps_everything(self, tmp_path):
        pts, _ = _plane_grid(n=5)
        cls = [1] * len(pts)
        f = _write_las(tmp_path / "all.las", pts, cls)
        assert Terrain.from_las(f, ground_only=False).n_points == len(pts)
        # filtering every point away is an error, not an empty terrain
        with pytest.raises(ValueError, match="at least three points"):
            Terrain.from_las(f, ground_only=True)

    def test_bbox_clips(self, tmp_path):
        pts, _ = _plane_grid(n=11, span=100.0)
        f = _write_las(tmp_path / "b.las", pts, [2] * len(pts))
        t = Terrain.from_las(f, bbox=(0.0, 0.0, 50.0, 50.0))
        xmin, ymin, xmax, ymax = t.bounds
        assert xmax <= 50.0 + 1e-6 and ymax <= 50.0 + 1e-6
        assert t.n_points < len(pts)

    def test_thin_decimates(self, tmp_path):
        pts, _ = _plane_grid(n=10)
        f = _write_las(tmp_path / "t.las", pts, [2] * len(pts))
        full = Terrain.from_las(f).n_points
        thinned = Terrain.from_las(f, thin=4).n_points
        assert thinned == len(range(0, full, 4))

    def test_file_without_classification_keeps_all_points(self, tmp_path):
        """A LAS lacking the classification dimension must not be filtered
        down to nothing when ground_only is set."""
        pts, _ = _plane_grid(n=5)
        f = _write_las(tmp_path / "noclass.las", pts)
        # point_format 3 always carries classification, so all-zero classes
        # mean "no ground flagged" -> ground_only yields nothing, but
        # ground_only=False still reads every point.
        assert Terrain.from_las(f, ground_only=False).n_points == len(pts)

    def test_preprocess_voxel_downsamples(self, tmp_path):
        pytest.importorskip("open3d")
        rng = np.random.default_rng(0)
        pts = rng.uniform(0, 100, size=(4000, 3))
        pts[:, 2] = 500.0 + 0.02 * pts[:, 0]
        f = _write_las(tmp_path / "dense.las", pts, [2] * len(pts))
        plain = Terrain.from_las(f)
        coarse = Terrain.from_las(f, preprocess=True, voxel_size=10.0)
        assert coarse.n_points < plain.n_points

    def test_preprocess_removes_statistical_outliers(self, tmp_path):
        pytest.importorskip("open3d")
        rng = np.random.default_rng(1)
        pts = rng.uniform(0, 100, size=(2000, 3))
        pts[:, 2] = 500.0
        spikes = np.array([[50.0, 50.0, 5000.0], [10.0, 10.0, -5000.0]])
        allpts = np.vstack([pts, spikes])
        f = _write_las(tmp_path / "spiky.las", allpts, [2] * len(allpts))
        cleaned = Terrain.from_las(f, preprocess=True, nb_neighbors=10,
                                  std_ratio=1.0)
        assert cleaned.n_points < len(allpts)
        assert cleaned.bounds is not None


# ── LandXML TIN ingest ────────────────────────────────────────────────────

def _landxml(points, faces, name="EG"):
    ps = "\n".join(f'<P id="{i + 1}">{n} {e} {z}</P>'
                   for i, (n, e, z) in enumerate(points))
    fs = "\n".join("<F>%d %d %d</F>" % tuple(f) for f in faces)
    return f"""<?xml version="1.0"?>
<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2">
  <Surfaces>
    <Surface name="{name}">
      <Definition surfType="TIN">
        <Pnts>{ps}</Pnts>
        <Faces>{fs}</Faces>
      </Definition>
    </Surface>
  </Surfaces>
</LandXML>"""


class TestFromLandXML:
    #: northing easting elevation, per the LandXML convention
    PTS = [(0.0, 0.0, 100.0), (0.0, 100.0, 102.0),
           (100.0, 100.0, 104.0), (100.0, 0.0, 102.0)]
    FACES = [(1, 2, 3), (1, 3, 4)]

    def test_reads_points_faces_and_swaps_to_easting_northing(self, tmp_path):
        f = tmp_path / "s.xml"
        f.write_text(_landxml(self.PTS, self.FACES))
        t = Terrain.from_landxml(f)
        assert t.n_points == 4 and t.n_triangles == 2
        # stored as (easting, northing, elev): the (0,100) LandXML point
        # becomes x=100, y=0
        xmin, ymin, xmax, ymax = t.bounds
        assert (xmin, ymin, xmax, ymax) == (0.0, 0.0, 100.0, 100.0)
        assert t.elevation_at(50.0, 50.0) is not None

    def test_named_surface_selection(self, tmp_path):
        f = tmp_path / "two.xml"
        f.write_text(_landxml(self.PTS, self.FACES, name="FG"))
        assert Terrain.from_landxml(f, surface="FG").n_points == 4
        with pytest.raises(ValueError, match="no Surface"):
            Terrain.from_landxml(f, surface="EG")

    def test_negative_face_indices_are_dropped(self, tmp_path):
        f = tmp_path / "del.xml"
        f.write_text(_landxml(self.PTS, [(1, 2, 3), (-1, 3, 4)]))
        assert Terrain.from_landxml(f).n_triangles == 1

    def test_surface_without_geometry_is_rejected(self, tmp_path):
        f = tmp_path / "empty.xml"
        f.write_text(_landxml([], []))
        with pytest.raises(ValueError, match="no points/faces"):
            Terrain.from_landxml(f)


class TestSuppliedFaceQueries:
    """With explicit faces the query core uses the centroid KD-tree path
    rather than Delaunay."""

    def test_interpolates_inside_a_supplied_face(self, tmp_path):
        f = tmp_path / "s.xml"
        f.write_text(_landxml(TestFromLandXML.PTS, TestFromLandXML.FACES))
        t = Terrain.from_landxml(f)
        assert t.elevation_at(1.0, 1.0) == pytest.approx(100.0, abs=0.5)

    def test_outside_supplied_faces_returns_none(self, tmp_path):
        f = tmp_path / "s.xml"
        f.write_text(_landxml(TestFromLandXML.PTS, TestFromLandXML.FACES))
        t = Terrain.from_landxml(f)
        assert t.elevation_at(500.0, 500.0) is None

    def test_degenerate_face_is_skipped(self):
        """A zero-area triangle has no barycentric solution."""
        pts = np.array([[0.0, 0.0, 10.0], [1.0, 0.0, 10.0],
                        [2.0, 0.0, 10.0], [0.0, 1.0, 11.0]])
        t = Terrain(pts, faces=np.array([[0, 1, 2], [0, 1, 3]]))
        assert t._barycentric(np.array([0.5, 0.0]), np.array([0, 1, 2])) is None
        assert t.elevation_at(0.25, 0.25) is not None


def test_repr_reports_size():
    pts, _ = _plane_grid(n=4)
    r = repr(Terrain.from_points(pts))
    assert "Terrain" in r
    assert "16" in r


# ── remote sources, with the network faked out ────────────────────────────

class TestFromOgrip:
    """The tile fetch is mocked; the tile-selection, unzip and merge logic
    is the real thing."""

    @staticmethod
    def _zip_of(tmp_path, las_name, pts):
        import zipfile
        las = _write_las(tmp_path / las_name, pts, [2] * len(pts))
        z = tmp_path / (las_name + ".zip")
        with zipfile.ZipFile(z, "w") as zf:
            zf.write(las, arcname=las_name)
        las.unlink()
        return z

    def _patch(self, monkeypatch, tiles, zips):
        from civilpy.state.ohio import ogrip as ogrip_mod
        monkeypatch.setattr(ogrip_mod, "find_las_tiles", lambda bbox: tiles)

        def _download(url, dest):
            import shutil
            shutil.copyfile(zips[url], dest)

        monkeypatch.setattr(ogrip_mod, "download_las_tile", _download)

    def test_merges_tiles_and_extracts_zips(self, tmp_path, monkeypatch):
        pts_a, _ = _plane_grid(n=5, span=50.0)
        pts_b, _ = _plane_grid(n=5, span=50.0)
        pts_b[:, 0] += 100.0
        za = self._zip_of(tmp_path, "a.las", pts_a)
        zb = self._zip_of(tmp_path, "b.las", pts_b)
        tiles = [{"LAS_URL": "http://x/a.las.zip", "Year": "2019"},
                 {"LAS_URL": "http://x/b.las.zip", "Year": "2019"}]
        self._patch(monkeypatch, tiles,
                    {"http://x/a.las.zip": za, "http://x/b.las.zip": zb})
        out = tmp_path / "dl"
        t = Terrain.from_ogrip((0, 0, 1, 1), out_dir=str(out))
        assert t.n_points == len(pts_a) + len(pts_b)
        assert t.bounds[2] > 100.0

    def test_keeps_only_the_newest_collection_year(self, tmp_path,
                                                   monkeypatch):
        pts_old, _ = _plane_grid(n=4, span=40.0)
        pts_new, _ = _plane_grid(n=6, span=40.0)
        zo = self._zip_of(tmp_path, "old.las", pts_old)
        zn = self._zip_of(tmp_path, "new.las", pts_new)
        tiles = [{"LAS_URL": "http://x/old.las.zip", "Year": "2012"},
                 {"LAS_URL": "http://x/new.las.zip", "Year": "2021"}]
        self._patch(monkeypatch, tiles,
                    {"http://x/old.las.zip": zo, "http://x/new.las.zip": zn})
        t = Terrain.from_ogrip((0, 0, 1, 1), out_dir=str(tmp_path / "d2"))
        assert t.n_points == len(pts_new)

    def test_bare_las_download_is_used_directly(self, tmp_path, monkeypatch):
        pts, _ = _plane_grid(n=5, span=50.0)
        las = _write_las(tmp_path / "plain.las", pts, [2] * len(pts))
        tiles = [{"LIDAR_URL": "http://x/plain.las", "Year": "2020"}]
        self._patch(monkeypatch, tiles, {"http://x/plain.las": las})
        t = Terrain.from_ogrip((0, 0, 1, 1), out_dir=str(tmp_path / "d3"))
        assert t.n_points == len(pts)

    def test_cached_files_are_not_redownloaded(self, tmp_path, monkeypatch):
        pts, _ = _plane_grid(n=5, span=50.0)
        z = self._zip_of(tmp_path, "c.las", pts)
        calls = []
        from civilpy.state.ohio import ogrip as ogrip_mod
        monkeypatch.setattr(ogrip_mod, "find_las_tiles",
                            lambda bbox: [{"LAS_URL": "http://x/c.las.zip",
                                           "Year": "2020"}])

        def _download(url, dest):
            import shutil
            calls.append(url)
            shutil.copyfile(z, dest)

        monkeypatch.setattr(ogrip_mod, "download_las_tile", _download)
        out = str(tmp_path / "cache")
        Terrain.from_ogrip((0, 0, 1, 1), out_dir=out)
        Terrain.from_ogrip((0, 0, 1, 1), out_dir=out)
        assert len(calls) == 1, "second call should reuse the cached zip"

    def test_no_tiles_is_an_error(self, monkeypatch):
        from civilpy.state.ohio import ogrip as ogrip_mod
        monkeypatch.setattr(ogrip_mod, "find_las_tiles", lambda bbox: [])
        with pytest.raises(ValueError, match="no OGRIP tiles"):
            Terrain.from_ogrip((0, 0, 1, 1))

    def test_tiles_without_urls_are_an_error(self, monkeypatch):
        from civilpy.state.ohio import ogrip as ogrip_mod
        monkeypatch.setattr(ogrip_mod, "find_las_tiles",
                            lambda bbox: [{"Year": "2020"}])
        with pytest.raises(ValueError, match="none had download URLs"):
            Terrain.from_ogrip((0, 0, 1, 1))


class TestFromOhioDem:
    """The ImageServer is faked; grid construction, batching, NoData handling
    and projection are real."""

    @staticmethod
    def _fake_post(captured, value=lambda x, y: 500.0 + 0.01 * x):
        class _Resp:
            def __init__(self, payload):
                self._p = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._p

        def post(url, data=None, timeout=None):
            import json as _json
            captured.append((url, data))
            geom = _json.loads(data["geometry"])
            samples = []
            for x, y in geom["points"]:
                v = value(x, y)
                samples.append({"value": None if v is None else str(v),
                                "location": {"x": x, "y": y}})
            return _Resp({"samples": samples})

        return post

    def test_samples_a_grid_in_state_plane_feet(self, monkeypatch):
        import requests  # noqa: F401
        cap = []
        monkeypatch.setattr(requests, "post", self._fake_post(cap))
        t = Terrain.from_ohio_dem((1000.0, 2000.0, 1400.0, 2400.0),
                                  spacing_ft=100.0, wgs84=False)
        assert t.n_points == 5 * 5
        assert cap and cap[0][0].endswith("/getSamples")
        assert cap[0][1]["geometryType"] == "esriGeometryMultipoint"
        assert t.elevation_at(1200.0, 2200.0) == pytest.approx(
            500.0 + 0.01 * 1200.0, abs=1e-6)

    def test_wgs84_bbox_is_projected(self, monkeypatch):
        pytest.importorskip("pyproj")
        import requests
        cap = []
        monkeypatch.setattr(requests, "post", self._fake_post(cap))
        t = Terrain.from_ohio_dem((-83.01, 39.99, -83.00, 40.00),
                                  spacing_ft=200.0)
        # projected into EPSG:3754 feet, so coordinates are large, not degrees
        xmin, ymin, xmax, ymax = t.bounds
        assert abs(xmin) > 1000.0 and abs(ymin) > 1000.0

    def test_requests_are_batched_by_chunk(self, monkeypatch):
        import requests
        cap = []
        monkeypatch.setattr(requests, "post", self._fake_post(cap))
        Terrain.from_ohio_dem((0.0, 0.0, 900.0, 900.0), spacing_ft=100.0,
                              wgs84=False, chunk=25)
        assert len(cap) == 4          # 10x10 grid / 25 per request
        for _, data in cap:
            import json as _json
            assert len(_json.loads(data["geometry"])["points"]) <= 25

    def test_nodata_samples_are_dropped(self, monkeypatch):
        import requests
        cap = []
        monkeypatch.setattr(
            requests, "post",
            self._fake_post(cap, value=lambda x, y: None if x > 200 else 500.0))
        t = Terrain.from_ohio_dem((0.0, 0.0, 400.0, 400.0), spacing_ft=100.0,
                                  wgs84=False)
        assert t.bounds[2] <= 200.0

    def test_too_few_valid_samples_is_a_clear_error(self, monkeypatch):
        import requests
        monkeypatch.setattr(requests, "post",
                            self._fake_post([], value=lambda x, y: None))
        with pytest.raises(ValueError, match="valid samples"):
            Terrain.from_ohio_dem((0.0, 0.0, 400.0, 400.0), spacing_ft=100.0,
                                  wgs84=False)

    def test_service_override_is_honoured(self, monkeypatch):
        import requests
        cap = []
        monkeypatch.setattr(requests, "post", self._fake_post(cap))
        Terrain.from_ohio_dem((0.0, 0.0, 200.0, 200.0), spacing_ft=100.0,
                              wgs84=False, service="http://example.test/img/")
        assert cap[0][0] == "http://example.test/img/getSamples"

    def test_degenerate_bbox_still_yields_a_minimum_grid(self, monkeypatch):
        import requests
        cap = []
        monkeypatch.setattr(requests, "post", self._fake_post(cap))
        t = Terrain.from_ohio_dem((0.0, 0.0, 1.0, 1.0), spacing_ft=100.0,
                                  wgs84=False)
        assert t.n_points == 4        # nx, ny floored to 2 each


class TestTerrainConstructionGuards:
    def test_faces_must_be_triangles(self):
        pts, _ = _plane_grid(n=4)
        with pytest.raises(ValueError, match=r"\(M, 3\) array"):
            Terrain(pts, faces=np.array([[0, 1, 2, 3]]))
        with pytest.raises(ValueError, match=r"\(M, 3\) array"):
            Terrain(pts, faces=np.array([0, 1, 2]))


class TestBboxPickerHandlers:
    """The draw handlers are plain callbacks; drive them directly rather
    than through a live widget."""

    @pytest.fixture()
    def picker(self):
        pytest.importorskip("ipyleaflet")
        from civilpy.transportation.terrain import bbox_picker
        return bbox_picker()

    SQUARE = {"type": "Polygon",
              "coordinates": [[[-83.02, 39.98], [-83.00, 39.98],
                               [-83.00, 40.00], [-83.02, 40.00],
                               [-83.02, 39.98]]]}

    def test_draw_sets_the_bbox_and_label(self, picker):
        picker._on_draw(None, "created", {"geometry": self.SQUARE})
        assert picker.bbox == pytest.approx((-83.02, 39.98, -83.00, 40.00))
        assert "bbox = (-83.0200, 39.9800, -83.0000, 40.0000)" \
            == picker._label.value

    def test_edit_replaces_the_previous_pick(self, picker):
        picker._on_draw(None, "created", {"geometry": self.SQUARE})
        moved = {"type": "Polygon",
                 "coordinates": [[[-81.0, 41.0], [-80.5, 41.0],
                                  [-80.5, 41.5], [-81.0, 41.5],
                                  [-81.0, 41.0]]]}
        picker._on_draw(None, "edited", {"geometry": moved})
        assert picker.bbox == pytest.approx((-81.0, 41.0, -80.5, 41.5))

    def test_other_actions_are_ignored(self, picker):
        picker._on_draw(None, "created", {"geometry": self.SQUARE})
        before = picker.bbox
        picker._on_draw(None, "deleted", {"geometry": self.SQUARE})
        picker._on_draw(None, "created", {})
        assert picker.bbox == before

    def test_data_change_uses_the_last_polygon(self, picker):
        picker._on_data({"new": [
            {"geometry": {"type": "Point", "coordinates": [0, 0]}},
            {"geometry": self.SQUARE},
        ]})
        assert picker.bbox == pytest.approx((-83.02, 39.98, -83.00, 40.00))

    def test_data_change_without_polygons_leaves_bbox_alone(self, picker):
        picker._on_data({"new": None})
        picker._on_data({"new": [
            {"geometry": {"type": "Point", "coordinates": [0, 0]}}]})
        assert picker.bbox is None

    def test_ipython_display_shows_the_map(self, picker, monkeypatch):
        shown = []
        import IPython.display as disp
        monkeypatch.setattr(disp, "display", lambda obj: shown.append(obj))
        picker._ipython_display_()
        assert shown == [picker.map]
