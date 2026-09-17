#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""``scan`` commands: LiDAR point clouds in, bridge features and CAD out."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from civilpy.cli import ui
from civilpy.cli.io_ import Column, CommandResult, ResultTable
from civilpy.cli.registry import CliError, CommandSpec

_CLOUD_EXTS = (".las", ".laz", ".ply", ".xyz", ".txt", ".csv", ".pts")


@dataclass(frozen=True)
class ScanInfoInput:
    """Inputs for ``scan info``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": (".las", ".laz"),
        "doc": "LAS/LAZ point cloud (header only — no points are read)",
    })


@dataclass(frozen=True)
class ScanExtractInput:
    """Inputs for ``scan extract``."""

    path: str = field(metadata={
        "positional": True, "kind": "path", "exts": _CLOUD_EXTS,
        "doc": "point cloud: .las/.laz (streamed), .ply, or .xyz/.txt rows",
    })
    voxel: float = field(default=0.25, metadata={
        "doc": "working voxel size in ft (points are averaged per voxel while "
               "streaming; 0.25 for features, 1.0 for a site overview)",
    })
    bbox: Optional[str] = field(default=None, metadata={
        "doc": "clip to 'xmin,ymin,xmax,ymax' in the file's coordinates",
    })
    plane_distance: float = field(default=0.06, metadata={
        "doc": "RANSAC inlier band for planes, ft",
    })
    plane_min_points: int = field(default=400, metadata={
        "doc": "smallest plane to keep, points",
    })
    max_planes: int = field(default=24, metadata={"doc": "planes to extract at most"})
    cylinder_min_points: int = field(default=200, metadata={
        "doc": "smallest cylinder (column / pile) to keep, points",
    })
    radius_min: float = field(default=0.4, metadata={"doc": "smallest cylinder radius, ft"})
    radius_max: float = field(default=6.0, metadata={"doc": "largest cylinder radius, ft"})
    ground_window: float = field(default=60.0, metadata={
        "doc": "ground-filter window, ft — must exceed the widest deck / building",
    })
    no_ground: bool = field(default=False, metadata={
        "doc": "skip the ground filter (a scan of the structure only)",
    })
    dxf: Optional[str] = field(default=None, metadata={
        "doc": "write the features to this .dxf (world coordinates)",
    })
    rhino: Optional[str] = field(default=None, metadata={
        "doc": "write the features to this .3dm (needs rhino3dm)",
    })
    json_out: Optional[str] = field(default=None, metadata={
        "doc": "write the feature report to this .json",
    })


def _bbox(text: Optional[str]):
    if not text:
        return None
    try:
        vals = tuple(float(v) for v in text.split(","))
    except ValueError:
        vals = ()
    if len(vals) != 4:
        raise CliError("bbox must be 'xmin,ymin,xmax,ymax'")
    return vals


def run_info(inp: ScanInfoInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.cli.registry import require

    require("laspy", "lidar")
    from civilpy.scan.cloud import las_info

    path = Path(inp.path).expanduser()
    if not path.exists():
        raise CliError(f"no such file: {path}")
    info = las_info(path)
    rows = [
        ("points", f"{info['point_count']:,}"),
        ("size", f"{info['size_bytes'] / 1e9:.2f} GB"),
        ("LAS version / point format", f"{info['version']} / {info['point_format']}"),
        ("CRS", info["crs"] or "(none stored)"),
        ("x range", f"{info['mins'][0]:.2f} – {info['maxs'][0]:.2f}"),
        ("y range", f"{info['mins'][1]:.2f} – {info['maxs'][1]:.2f}"),
        ("z range", f"{info['mins'][2]:.2f} – {info['maxs'][2]:.2f}"),
        ("extent", f"{info['maxs'][0] - info['mins'][0]:.0f} × "
                   f"{info['maxs'][1] - info['mins'][1]:.0f} × "
                   f"{info['maxs'][2] - info['mins'][2]:.0f}"),
        ("scale", ", ".join(f"{s:g}" for s in info["scales"])),
        ("colour", "RGB" if info["has_rgb"] else "none"),
        ("dimensions", ", ".join(info["dimensions"])),
    ]
    table = ResultTable(title="LAS header", columns=[Column("Field"), Column("Value")], rows=rows,
                        notes=["Units are the file's own (state-plane feet for ODOT / USFS "
                               "static scans); the CRS row is authoritative when present."])
    return CommandResult(tables=[table], input_files=[str(path)])


def run_extract(inp: ScanExtractInput, ctx) -> CommandResult:  # noqa: ANN001
    from civilpy.scan.cloud import read_cloud
    from civilpy.scan.pipeline import extract_features

    path = Path(inp.path).expanduser()
    if not path.exists():
        raise CliError(f"no such file: {path}")
    if path.suffix.lower() == ".pod":
        raise CliError("Bentley Pointools .pod is a closed format — export to LAS first")
    kwargs = {}
    if path.suffix.lower() != ".ply":
        kwargs.update(voxel=inp.voxel, bbox=_bbox(inp.bbox))
    with ui.spinner(f"Reading {path.name}"):
        cloud = read_cloud(path, **kwargs)
    if len(cloud) == 0:
        raise CliError("no points read (check the bbox)")
    notes = [f"{len(cloud):,} points at {inp.voxel} ft voxel; origin "
             f"{cloud.origin.round(2).tolist()}" + (f"; CRS {cloud.crs}" if cloud.crs else "")]
    log = [] if ui.is_quiet() else None
    with ui.spinner("Extracting features"):
        res = extract_features(
            cloud, voxel=inp.voxel, plane_distance=inp.plane_distance,
            plane_min_points=inp.plane_min_points, max_planes=inp.max_planes,
            cylinder_min_points=inp.cylinder_min_points,
            cylinder_radius=(inp.radius_min, inp.radius_max),
            ground=not inp.no_ground, ground_window=inp.ground_window,
            log=(log.append if log is not None else None))
    s = res.summary()
    off = res.origin

    overview = [
        ("points", f"{s['n_points']:,}"), ("ground points", f"{s['n_ground']:,}"),
        ("assigned to features", f"{s['assigned_fraction']:.1%}"),
        ("planes / cylinders / edges", f"{s['n_planes']} / {s['n_cylinders']} / {s['n_edges']}"),
        ("bridge axis (E, N)", f"{s['axis_direction'][0]:+.3f}, {s['axis_direction'][1]:+.3f}"),
    ]
    if "deck" in s:
        d = s["deck"]
        overview.append(("deck (L × W, elev)", f"{d['length']:.1f} × {d['width']:.1f} ft at "
                                               f"{d['elevation'] + off[2]:.2f}"))
    mc = s.get("min_clearance")
    if mc:
        overview.append(("min under-clearance",
                         f"{mc['clearance']:.2f} ft at ({mc['x'] + off[0]:.1f}, {mc['y'] + off[1]:.1f}); "
                         f"underside {mc['z_high'] + off[2]:.2f}, ground {mc['z_low'] + off[2]:.2f}"))
    tables = [ResultTable(title="Scan overview", columns=[Column("Item"), Column("Value")],
                          rows=overview, notes=notes)]

    plane_rows = [(p.name, p.role, p.orientation, round(p.centroid[0] + off[0], 2),
                   round(p.centroid[1] + off[1], 2), round(p.elevation + off[2], 2),
                   round(p.extent_u, 2), round(p.extent_v, 2), round(p.area, 1),
                   round(p.tilt_deg, 2), p.n_points, round(p.rms, 3)) for p in res.planes]
    if plane_rows:
        tables.append(ResultTable(
            title="Planes",
            columns=[Column("Name"), Column("Role"), Column("Orientation"), Column("X", "ft", ".2f"),
                     Column("Y", "ft", ".2f"), Column("Z", "ft", ".2f"), Column("Length", "ft", ".1f"),
                     Column("Width", "ft", ".1f"), Column("Area", "sq ft", ".0f"),
                     Column("Tilt", "deg", ".2f"), Column("Points"), Column("RMS", "ft", ".3f")],
            rows=plane_rows))
    cyl_rows = [(c.name, c.role, round(c.center[0] + off[0], 2), round(c.center[1] + off[1], 2),
                 round(c.start[2] + off[2], 2), round(c.end[2] + off[2], 2), round(c.diameter, 3),
                 round(c.length, 2), round(c.tilt_deg, 2), c.n_points, round(c.rms, 3))
                for c in res.cylinders]
    if cyl_rows:
        tables.append(ResultTable(
            title="Cylinders",
            columns=[Column("Name"), Column("Role"), Column("X", "ft", ".2f"), Column("Y", "ft", ".2f"),
                     Column("Z bottom", "ft", ".2f"), Column("Z top", "ft", ".2f"),
                     Column("Diameter", "ft", ".3f"), Column("Length", "ft", ".2f"),
                     Column("Tilt", "deg", ".2f"), Column("Points"), Column("RMS", "ft", ".3f")],
            rows=cyl_rows))
    if log:
        tables[0].notes.extend(log)

    written = []
    if inp.dxf:
        written.append(str(res.export_dxf(Path(inp.dxf).expanduser())))
    if inp.rhino:
        from civilpy.cli.registry import require
        require("rhino3dm", "rhino")
        written.append(str(res.export_3dm(Path(inp.rhino).expanduser())))
    if inp.json_out:
        written.append(str(res.save_json(Path(inp.json_out).expanduser())))
    for w in written:
        tables[0].notes.append(f"wrote {w}")
    return CommandResult(tables=tables, input_files=[str(path)],
                         inputs={k: v for k, v in vars(inp).items() if k != "path" and v is not None})


SPECS = [
    CommandSpec(
        name="scan info",
        summary="Show a LAS/LAZ point cloud's header: count, bounds, CRS, dimensions",
        description=(
            "Reads only the header, so it answers instantly for a multi-gigabyte "
            "static scan. Use it to pick a bbox and voxel size before ``scan extract``."
        ),
        input_model=ScanInfoInput,
        runner="civilpy.cli.commands.scan:run_info",
        requires=("laspy",),
    ),
    CommandSpec(
        name="scan extract",
        summary="Segment a bridge-site point cloud into planes, columns, edges and clearances",
        description=(
            "Streams the cloud through a voxel grid, strips the ground with a "
            "progressive morphological filter, fits planes (deck, soffit, abutments, "
            "wingwalls, barriers) and cylinders (columns, piles) by RANSAC, labels "
            "each with a bridge role, measures the minimum vertical under-clearance, "
            "and optionally writes everything to DXF / Rhino 3dm on civilpy's shared "
            "layer taxonomy. Distances are in the file's units (feet)."
        ),
        input_model=ScanExtractInput,
        runner="civilpy.cli.commands.scan:run_extract",
    ),
]
