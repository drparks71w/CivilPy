"""Terrain: a source-agnostic ground surface that answers ``elevation_at``.

The bridge/analysis pipeline places objects by station and offset along an
:class:`~civilpy.transportation.alignment.Alignment`; the vertical position of
anything that meets grade (abutment seats, wingwall foreslopes, footing cutoff,
approach grades) comes from the ground surface, which this object models as a
triangulated irregular network (TIN).

The **query core** (``elevation_at`` by barycentric interpolation over the TIN)
is pure ``numpy`` + ``scipy`` so it runs and tests anywhere.  The heavier
ingestion paths are lazy:

* :meth:`from_las` reads OGRIP LiDAR ``.las``/``.laz`` (imports ``laspy`` only
  when called) — the early-design / demo source.
* :meth:`from_landxml` reads a survey-shot TIN (LandXML ``Surface``) with its
  own faces/breaklines — the Stage-3 production source.
* :meth:`to_open3d_mesh` exports a mesh (imports ``open3d`` only when called).

Coordinates are ``(x=East, y=North, z=Elevation)`` in feet, matching
:mod:`civilpy.transportation.alignment`.

Examples
--------
>>> import numpy as np
>>> # a plane tilted 2% east, 1% north, sampled on a coarse grid
>>> gx, gy = np.meshgrid(np.linspace(0, 100, 6), np.linspace(0, 100, 6))
>>> z = 500.0 + 0.02 * gx + 0.01 * gy
>>> pts = np.column_stack([gx.ravel(), gy.ravel(), z.ravel()])
>>> t = Terrain.from_points(pts)
>>> round(t.elevation_at(50.0, 50.0), 6)      # 500 + 1.0 + 0.5
501.5
>>> t.elevation_at(-10.0, 50.0) is None        # outside the hull
True
"""

from __future__ import annotations

#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

import numpy as np
from scipy.spatial import Delaunay, cKDTree


class Terrain:
    """A triangulated ground surface.

    Parameters
    ----------
    points : array_like, shape (N, 3)
        ``(x, y, z)`` ground points, feet.
    faces : array_like, shape (M, 3), optional
        Triangle vertex indices (a supplied TIN, e.g. from a survey with
        breaklines).  When omitted the XY projection is Delaunay-triangulated.
    """

    def __init__(self, points, faces=None):
        pts = np.asarray(points, dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 3:
            raise ValueError("points must be an (N, 3) array of x, y, z")
        if len(pts) < 3:
            raise ValueError("a terrain needs at least three points")
        self.points = pts
        self._xy = pts[:, :2]
        self._z = pts[:, 2]
        if faces is None:
            self._delaunay = Delaunay(self._xy)
            self.faces = self._delaunay.simplices
            self._kdtree = None
        else:
            self._delaunay = None
            self.faces = np.asarray(faces, dtype=int)
            if self.faces.ndim != 2 or self.faces.shape[1] != 3:
                raise ValueError("faces must be an (M, 3) array of indices")
            self._centroids = self._xy[self.faces].mean(axis=1)
            self._kdtree = cKDTree(self._centroids)

    # -- constructors ------------------------------------------------------

    @classmethod
    def from_points(cls, points, faces=None) -> "Terrain":
        """Build from an ``(N, 3)`` array of ground points."""
        return cls(points, faces=faces)

    @classmethod
    def from_xyz_file(cls, path, *, skiprows: int = 0,
                      cols: tuple[int, int, int] = (0, 1, 2)) -> "Terrain":
        """Build from a whitespace/CSV ``.xyz``/``.txt`` file of point rows."""
        data = np.loadtxt(path, skiprows=skiprows)
        return cls(data[:, list(cols)])

    @classmethod
    def from_las(cls, path, *, ground_only: bool = True, bbox=None,
                 thin: int = 1, preprocess: bool = False,
                 voxel_size: float | None = None,
                 nb_neighbors: int = 20, std_ratio: float = 2.0) -> "Terrain":
        """Build from an OGRIP LiDAR ``.las``/``.laz`` file (lazy ``laspy``).

        ``ground_only`` keeps only ASPRS class 2 (ground) returns; ``bbox`` is
        an optional ``(xmin, ymin, xmax, ymax)`` clip; ``thin`` keeps every
        ``thin``-th point to cap density.

        If ``preprocess`` is True, use Open3D for statistical outlier removal
        and voxel downsampling (requires ``open3d``).
        """
        try:
            import laspy
        except ImportError as exc:                       # pragma: no cover
            raise ImportError(
                "reading LiDAR needs 'laspy' (pip install laspy[laszip]); "
                "the Terrain query core does not require it") from exc
        las = laspy.read(str(path))
        x = np.asarray(las.x, dtype=float)
        y = np.asarray(las.y, dtype=float)
        z = np.asarray(las.z, dtype=float)
        keep = np.ones(len(x), dtype=bool)
        if ground_only and hasattr(las, "classification"):
            keep &= np.asarray(las.classification) == 2
        if bbox is not None:
            xmin, ymin, xmax, ymax = bbox
            keep &= (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
        idx = np.nonzero(keep)[0]
        if thin > 1:
            idx = idx[::thin]

        pts = np.column_stack([x[idx], y[idx], z[idx]])

        if preprocess:
            try:
                import open3d as o3d
            except ImportError as exc:
                raise ImportError(
                    "preprocessing needs 'open3d' (pip install open3d)") from exc

            pcd = o3d.geometry.PointCloud()
            pcd.points = o3d.utility.Vector3dVector(pts)

            if voxel_size:
                pcd = pcd.voxel_down_sample(voxel_size=voxel_size)

            pcd, _ = pcd.remove_statistical_outlier(
                nb_neighbors=nb_neighbors, std_ratio=std_ratio)
            pts = np.asarray(pcd.points)

        return cls(pts)

    @classmethod
    def from_landxml(cls, path, *, surface: str | None = None) -> "Terrain":
        """Build from a LandXML ``Surface`` TIN (survey deliverable).

        Honors the supplied faces (breaklines preserved).  LandXML point
        coordinates are ``northing easting elevation``; they are stored as
        ``(easting, northing, elevation)``.  Faces are 1-indexed; faces with a
        negative index (LandXML's deleted/invisible marker) are dropped.
        """
        import xml.etree.ElementTree as ET

        root = ET.parse(str(path)).getroot()

        def _local(tag):                     # strip the LandXML namespace
            return tag.rsplit("}", 1)[-1]

        surf = None
        for el in root.iter():
            if _local(el.tag) == "Surface" and (
                    surface is None or el.get("name") == surface):
                surf = el
                break
        if surf is None:
            raise ValueError(f"no Surface {surface!r} found in {path}")

        pnts, id_map, faces = [], {}, []
        for el in surf.iter():
            lt = _local(el.tag)
            if lt == "P":
                vals = [float(v) for v in (el.text or "").split()]
                northing, easting, elev = vals[0], vals[1], vals[2]
                id_map[el.get("id")] = len(pnts)
                pnts.append((easting, northing, elev))
            elif lt == "F":
                ids = [int(v) for v in (el.text or "").split()]
                if any(i < 0 for i in ids):
                    continue
                faces.append([i - 1 for i in ids[:3]])     # 1- to 0-indexed
        if not pnts or not faces:
            raise ValueError(f"Surface in {path} has no points/faces")
        return cls(np.asarray(pnts, float), faces=np.asarray(faces, int))

    # -- query core --------------------------------------------------------

    def elevation_at(self, x: float, y: float) -> float | None:
        """Ground elevation at plan ``(x, y)`` by barycentric interpolation on
        the TIN; ``None`` when the point is outside the triangulated area."""
        p = np.array([float(x), float(y)])
        if self._delaunay is not None:
            s = int(self._delaunay.find_simplex(p))
            if s < 0:
                return None
            tr = self._delaunay.transform[s]
            b = tr[:2].dot(p - tr[2])
            bary = np.array([b[0], b[1], 1.0 - b[0] - b[1]])
            verts = self._delaunay.simplices[s]
            return float(bary.dot(self._z[verts]))
        # supplied faces: search nearest centroids, test containment
        k = min(16, len(self.faces))
        _, cand = self._kdtree.query(p, k=k)
        for f in np.atleast_1d(cand):
            bary = self._barycentric(p, self.faces[f])
            if bary is not None and (bary >= -1e-9).all():
                return float(bary.dot(self._z[self.faces[f]]))
        return None

    def _barycentric(self, p, face) -> np.ndarray | None:
        (x1, y1), (x2, y2), (x3, y3) = self._xy[face]
        det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(det) < 1e-12:
            return None
        l1 = ((y2 - y3) * (p[0] - x3) + (x3 - x2) * (p[1] - y3)) / det
        l2 = ((y3 - y1) * (p[0] - x3) + (x1 - x3) * (p[1] - y3)) / det
        return np.array([l1, l2, 1.0 - l1 - l2])

    # -- alignment-aware helpers ------------------------------------------

    def elevation_along(self, alignment, station_ft: float,
                        offset_ft: float = 0.0) -> float | None:
        """Ground elevation at ``(station, offset)`` on ``alignment``."""
        x, y, _ = alignment.point_at(station_ft, offset_ft)
        return self.elevation_at(x, y)

    def profile(self, alignment, stations, offset_ft: float = 0.0) -> list:
        """Ground elevations along ``alignment`` at each of ``stations``."""
        return [self.elevation_along(alignment, s, offset_ft) for s in stations]

    # -- utilities ---------------------------------------------------------

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(xmin, ymin, xmax, ymax)`` of the point set."""
        lo = self._xy.min(axis=0)
        hi = self._xy.max(axis=0)
        return float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1])

    @property
    def n_points(self) -> int:
        return len(self.points)

    @property
    def n_triangles(self) -> int:
        return len(self.faces)

    def clip_to_bbox(self, xmin: float, ymin: float, xmax: float,
                     ymax: float) -> "Terrain":
        """Return a new re-triangulated ``Terrain`` of the points inside the
        box (used to keep just the project corridor)."""
        m = ((self._xy[:, 0] >= xmin) & (self._xy[:, 0] <= xmax)
             & (self._xy[:, 1] >= ymin) & (self._xy[:, 1] <= ymax))
        return Terrain(self.points[m])

    def clip_to_corridor(self, alignment, half_width_ft: float, *,
                         step_ft: float = 25.0) -> "Terrain":
        """Return a new ``Terrain`` of points within ``half_width_ft`` of the
        alignment (a station-sampled corridor), for trimming LiDAR to a site."""
        stations = np.arange(alignment.start_station,
                             alignment.end_station + step_ft, step_ft)
        centers = np.array([alignment.point_at(s)[:2] for s in stations])
        tree = cKDTree(centers)
        d, _ = tree.query(self._xy, k=1)
        return Terrain(self.points[d <= half_width_ft])

    def to_open3d_mesh(self, poisson: bool = False, depth: int = 9):  # pragma: no cover
        """Build an ``open3d`` triangle mesh (lazy import) for display/Rhino.

        If ``poisson`` is True, use Poisson Surface Reconstruction instead of
        the internal TIN (good for noisy LiDAR; requires ``depth`` parameter).
        """
        try:
            import open3d as o3d
        except ImportError as exc:
            raise ImportError(
                "to_open3d_mesh needs 'open3d' (pip install open3d)") from exc

        if not poisson:
            mesh = o3d.geometry.TriangleMesh()
            mesh.vertices = o3d.utility.Vector3dVector(self.points)
            mesh.triangles = o3d.utility.Vector3iVector(self.faces)
            mesh.compute_vertex_normals()
            return mesh

        # Poisson reconstruction needs normals
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(self.points)
        pcd.estimate_normals()
        pcd.orient_normals_consistent_tangent_plane(100)

        mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
            pcd, depth=depth)

        # Crop to the original bbox to remove artifacts
        bbox = pcd.get_axis_aligned_bounding_box()
        mesh = mesh.crop(bbox)
        mesh.compute_vertex_normals()
        return mesh

    @classmethod
    def from_ogrip(cls, bbox_wgs84, out_dir="temp_las", **kwargs) -> "Terrain":
        """Fetch OGRIP/3DEP LiDAR tiles for a WGS84 bbox and build a Terrain.

        Requires ``requests``.  Tiles are ZIP archives (~50-120 MB each,
        holding one LAS) downloaded to ``out_dir`` and extracted there;
        both survive for reuse on the next call.  When flights overlap
        (OSIP and 3DEP cover the same ground) only the newest collection
        year is used.  Remaining ``kwargs`` are passed to :meth:`from_las`.
        """
        from civilpy.state.ohio.ogrip import find_las_tiles, download_las_tile
        import os
        import zipfile

        tiles = find_las_tiles(bbox_wgs84)
        if not tiles:
            raise ValueError(f"no OGRIP tiles found for bbox {bbox_wgs84}")

        # overlapping flights: keep only the newest collection year
        newest = max(str(t.get("Year", "")) for t in tiles)
        tiles = [t for t in tiles if str(t.get("Year", "")) == newest]

        las_paths = []
        os.makedirs(out_dir, exist_ok=True)

        for tile in tiles:
            url = tile.get("LAS_URL") or tile.get("LIDAR_URL")
            if not url:
                continue
            name = os.path.basename(url)
            dest = os.path.join(out_dir, name)
            if not os.path.exists(dest):
                download_las_tile(url, dest)
            if zipfile.is_zipfile(dest):
                with zipfile.ZipFile(dest) as zf:
                    members = [m for m in zf.namelist()
                               if m.lower().endswith((".las", ".laz"))]
                    for m in members:
                        extracted = os.path.join(out_dir, os.path.basename(m))
                        if not os.path.exists(extracted):
                            with zf.open(m) as src, open(extracted, "wb") as out:
                                while True:
                                    chunk = src.read(1 << 20)
                                    if not chunk:
                                        break
                                    out.write(chunk)
                        las_paths.append(extracted)
            else:
                las_paths.append(dest)

        if not las_paths:
            raise ValueError("found tiles but none had download URLs")

        all_pts = []
        for p in las_paths:
            t = cls.from_las(p, **kwargs)
            all_pts.append(t.points)

        return cls(np.vstack(all_pts))

    #: Ohio DNR statewide DEM (OSIP LiDAR-derived, 2.5 ft, F32), an ArcGIS
    #: ImageServer that returns real elevations by query -- no gigabyte tile
    #: downloads.  Native SR is EPSG:3754 (NAD83 Ohio South State Plane, ft).
    OH_DEM_IMAGESERVER = (
        "https://gis.ohiodnr.gov/image/rest/services/OH_DEM_test/ImageServer")
    OH_DEM_SR = 3754

    @classmethod
    def from_ohio_dem(cls, bbox, *, spacing_ft: float = 50.0,
                      wgs84: bool = True, service: str | None = None,
                      chunk: int = 400) -> "Terrain":
        """Build a Terrain from real Ohio LiDAR by sampling the ODNR OH_DEM
        ImageServer over ``bbox`` -- the practical alternative to downloading
        LAS tiles.

        Parameters
        ----------
        bbox : tuple
            ``(xmin, ymin, xmax, ymax)``.  When ``wgs84`` (default) these are
            longitude/latitude degrees, projected to Ohio South State Plane feet
            (EPSG:3754, ``pyproj`` required); otherwise they are already in
            EPSG:3754 feet.
        spacing_ft : float
            Grid spacing of the elevation samples, feet.
        service : str, optional
            Override the ImageServer URL (defaults to
            :data:`OH_DEM_IMAGESERVER`).
        chunk : int
            Points per ``getSamples`` request (batched multipoint POST).

        Returns
        -------
        Terrain
            Points ``(easting_ft, northing_ft, elevation_ft)`` in EPSG:3754 --
            a feet frame consistent with the rest of the bridge stack.  Cells
            the DEM marks NoData are dropped.

        Notes
        -----
        Requires ``requests`` (and ``pyproj`` when ``wgs84``).  Needs network
        access to the ODNR service; unlike ``from_ogrip`` there is no local
        file, so keep it out of import-time paths.
        """
        import json
        import requests

        svc = (service or cls.OH_DEM_IMAGESERVER).rstrip("/")
        xmin, ymin, xmax, ymax = bbox
        if wgs84:
            from pyproj import Transformer
            tf = Transformer.from_crs(4326, cls.OH_DEM_SR, always_xy=True)
            (xmin, ymin), (xmax, ymax) = tf.transform(xmin, ymin), tf.transform(xmax, ymax)
        xmin, xmax = sorted((xmin, xmax))
        ymin, ymax = sorted((ymin, ymax))

        nx = max(2, int((xmax - xmin) / spacing_ft) + 1)
        ny = max(2, int((ymax - ymin) / spacing_ft) + 1)
        grid = [(xmin + i * spacing_ft, ymin + j * spacing_ft)
                for i in range(nx) for j in range(ny)]

        pts = []
        for k in range(0, len(grid), chunk):
            batch = grid[k:k + chunk]
            mp = {"points": [[x, y] for x, y in batch],
                  "spatialReference": {"wkid": cls.OH_DEM_SR}}
            resp = requests.post(
                svc + "/getSamples",
                data={"geometry": json.dumps(mp),
                      "geometryType": "esriGeometryMultipoint",
                      "returnFirstValueOnly": "true", "f": "json"},
                timeout=60)
            resp.raise_for_status()
            samples = resp.json().get("samples", [])
            for s in samples:
                v = s.get("value")
                if v in (None, "", "NoData"):
                    continue
                loc = s["location"]
                pts.append((loc["x"], loc["y"], float(v)))

        if len(pts) < 3:
            raise ValueError(
                f"OH_DEM returned {len(pts)} valid samples for bbox {bbox}; "
                "check the bbox covers Ohio and the service is reachable")
        return cls(np.array(pts, dtype=float))

    def __repr__(self):
        x0, y0, x1, y1 = self.bounds
        return (f"Terrain({self.n_points} pts, {self.n_triangles} tris, "
                f"bounds=({x0:.1f}, {y0:.1f})-({x1:.1f}, {y1:.1f}))")


class BboxPicker:
    """Interactive notebook map for picking a WGS84 bounding box.

    Draw a rectangle on the map and ``.bbox`` holds ``(xmin, ymin, xmax,
    ymax)`` in decimal degrees (lon, lat) — the tuple
    :meth:`Terrain.from_ogrip` and :meth:`Terrain.from_ohio_dem` take.
    Drawing a new rectangle replaces the previous pick.  Displaying the
    picker (last expression in a cell) shows the map; a corner readout
    updates live so the chosen bbox is also visible on screen.

    Navigation: **hybrid imagery** by default — Esri satellite with
    Esri's transparent road and place-label reference tiles on top (both
    can be unticked, and a plain streets base map selected, from the
    layer toggle at top right) — plus scroll-wheel zoom, a fullscreen
    control, and a **search box** (top left, Nominatim) that flies to a
    typed address or place name — the quick way to land on a jobsite
    before drawing the rectangle.

    Requires ``ipyleaflet`` (``pip install ipyleaflet``), which gives the
    two-way widget link a static ``folium`` map cannot: the drawn
    geometry lands in the Python kernel with no copy/paste.
    """

    def __init__(self, center=(40.004, -83.005), zoom=14, height="480px"):
        try:
            import ipywidgets
            from ipyleaflet import (DrawControl, FullScreenControl,
                                    LayersControl, Map, Marker,
                                    SearchControl, TileLayer, WidgetControl,
                                    basemaps, basemap_to_tiles)
        except ImportError as exc:                       # pragma: no cover
            raise ImportError(
                "the bbox picker needs 'ipyleaflet' (pip install "
                "ipyleaflet); Terrain itself does not require it") from exc

        self.bbox = None
        # hybrid default: satellite imagery + Esri's transparent road and
        # place-label reference tiles (their standard hybrid recipe);
        # streets ride along as a base-layer toggle
        sat = basemap_to_tiles(basemaps.Esri.WorldImagery)
        sat.base, sat.name = True, "Esri satellite"
        streets = basemap_to_tiles(basemaps.OpenStreetMap.Mapnik)
        streets.base, streets.name = True, "Streets"
        ref = ("https://server.arcgisonline.com/ArcGIS/rest/services/"
               "Reference/{}/MapServer/tile/{{z}}/{{y}}/{{x}}")
        roads = TileLayer(url=ref.format("World_Transportation"),
                          name="Roads (hybrid)", attribution="Esri")
        labels = TileLayer(url=ref.format("World_Boundaries_and_Places"),
                           name="Labels (hybrid)", attribution="Esri")
        self.map = Map(layers=(streets, sat, roads, labels), center=center,
                       zoom=zoom, scroll_wheel_zoom=True)
        self.map.layout.height = height
        self.map.add(LayersControl(position="topright"))
        self.map.add(FullScreenControl())
        # fly-to-address search (Nominatim geocoder)
        self.map.add(SearchControl(
            position="topleft",
            url="https://nominatim.openstreetmap.org/search?format=json&q={s}",
            zoom=zoom, marker=Marker()))

        self._label = ipywidgets.HTML("draw a rectangle to set the bbox")
        self.map.add(WidgetControl(widget=self._label,
                                   position="bottomleft"))

        draw = DrawControl(rectangle={"shapeOptions": {"color": "#c00",
                                                       "weight": 2,
                                                       "fillOpacity": 0.08}},
                           polygon={}, polyline={}, circlemarker={},
                           marker={}, edit=False, remove=False)
        draw.on_draw(self._on_draw)
        self.map.add(draw)
        self._draw = draw

    def _on_draw(self, target, action, geo_json):
        lons, lats = zip(*geo_json["geometry"]["coordinates"][0])
        self.bbox = (min(lons), min(lats), max(lons), max(lats))
        self._label.value = ("bbox = (%.4f, %.4f, %.4f, %.4f)" % self.bbox)
        # keep only the newest rectangle on the map
        self._draw.data = self._draw.data[-1:]

    def _ipython_display_(self):
        from IPython.display import display
        display(self.map)


def bbox_picker(center=(40.004, -83.005), zoom=14) -> BboxPicker:
    """A :class:`BboxPicker` centered on ``center`` (lat, lon) — display
    it, draw a rectangle, then read ``picker.bbox``."""
    return BboxPicker(center=center, zoom=zoom)
