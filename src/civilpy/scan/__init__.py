#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Scan-to-CAD: point-cloud segmentation, meshing, and feature extraction.

Terrestrial / mobile LiDAR scans of a bridge site arrive as a few hundred
million unclassified points in state-plane feet.  This package turns them
into the engineering objects the rest of civilpy already understands —
planes (deck, soffit, abutment faces, wingwalls), cylinders (columns,
piles), boundary polylines, ground surfaces, vertical-clearance maps —
and writes those out as DXF / Rhino ``.3dm`` / mesh files.

The pipeline, module by module:

1. :mod:`~civilpy.scan.cloud` — the :class:`~civilpy.scan.cloud.PointCloud`
   container and **streaming** readers (``.las``/``.laz`` via ``laspy``,
   whitespace ``.xyz``, ``.ply``).  Readers decimate / voxelize chunk by
   chunk so a 9 GB scan never has to fit in memory.
2. :mod:`~civilpy.scan.preprocess` — voxel down-sampling, outlier removal,
   PCA normals, crops, local-origin shifts.  Pure ``numpy``/``scipy``.
3. :mod:`~civilpy.scan.segment` — RANSAC planes and cylinders, a
   progressive-morphological ground filter, Euclidean clustering,
   smoothness-constrained region growing, elevation slicing.
4. :mod:`~civilpy.scan.features` — typed geometric features
   (:class:`~civilpy.scan.features.PlaneFeature`,
   :class:`~civilpy.scan.features.CylinderFeature`, ...), alpha-shape
   boundaries, under-clearance grids, cross sections, bridge-role labels.
5. :mod:`~civilpy.scan.mesh` — :class:`~civilpy.scan.mesh.Mesh` with
   Delaunay / grid meshing (pure ``scipy``) and optional Poisson /
   ball-pivot reconstruction through ``open3d``; PLY/OBJ/STL writers.
6. :mod:`~civilpy.scan.cad` — DXF (``ezdxf``, a core dependency) and Rhino
   ``.3dm`` (``rhino3dm``, lazy) export on the shared
   :mod:`~civilpy.structural.rhino_layers` taxonomy; a bridge to
   :class:`~civilpy.transportation.terrain.Terrain`.
7. :mod:`~civilpy.scan.pipeline` — :func:`~civilpy.scan.pipeline.extract_features`
   runs the whole chain and returns a
   :class:`~civilpy.scan.pipeline.ScanFeatures` report.

Only ``numpy``, ``scipy``, ``pandas`` and ``ezdxf`` are required; ``laspy``
(``pip install civilpy[lidar]``), ``open3d`` and ``rhino3dm`` are imported
inside the functions that need them.  Coordinates follow the civilpy hub
convention — ``(x=East, y=North, z=Elevation)`` in **feet**.

Bentley Pointools ``.pod`` files are a closed format; export them to LAS
from MicroStation / Pointools before reading.

Quick start::

    from civilpy.scan import read_las, extract_features

    cloud = read_las("site.las", voxel=0.25, bbox=(x0, y0, x1, y1))
    result = extract_features(cloud)
    print(result.summary())
    result.export_dxf("site_features.dxf")
"""

from __future__ import annotations

from civilpy.scan.cloud import (PointCloud, las_info, read_las, read_ply,
                                read_xyz, write_las, write_ply, write_xyz)
from civilpy.scan.features import (CylinderFeature, LineFeature,
                                   PlaneFeature, PolylineFeature)
from civilpy.scan.mesh import Mesh
from civilpy.scan.pipeline import ScanFeatures, extract_features

__all__ = [
    "PointCloud", "las_info", "read_las", "read_ply", "read_xyz",
    "write_las", "write_ply", "write_xyz",
    "PlaneFeature", "CylinderFeature", "LineFeature", "PolylineFeature",
    "Mesh", "ScanFeatures", "extract_features",
]
