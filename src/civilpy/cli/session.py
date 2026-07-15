#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Workspace: named objects loaded from files, shared across commands.

``load <path>`` dispatches on extension to a typed loader (DIGGS XML →
:class:`~civilpy.geotech.boring.Borehole`, ``.las``/``.laz`` → Terrain,
``.3dm`` → rhino3dm model, ``.csv``/``.xlsx`` → DataFrame).  Loaded
objects are addressable by name, so a shell session runs
``load B-001.xml`` once and then ``hydro scour-pier --boring B-001 …``
without re-parsing.  Batch mode gets a throwaway workspace: path-typed
arguments load inline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from civilpy.cli.registry import CliError, require


@dataclass
class LoadedObject:
    name: str
    kind: str          # "boring" | "table" | "terrain" | "3dm"
    obj: Any
    source: str
    summary: str


@dataclass
class Workspace:
    objects: Dict[str, LoadedObject] = field(default_factory=dict)
    log: List[str] = field(default_factory=list)

    def load(self, path: str, name: Optional[str] = None) -> List[LoadedObject]:
        """Load ``path`` by extension; returns the objects added (a DIGGS
        document may hold several holes)."""
        p = Path(path).expanduser()
        if not p.exists():
            raise CliError(f"no such file: {p}")
        suffix = p.suffix.lower()
        if suffix == ".xml":
            loaded = self._load_diggs(p)
        elif suffix in (".csv", ".xlsx"):
            loaded = [self._load_table(p)]
        elif suffix in (".las", ".laz"):
            loaded = [self._load_terrain(p)]
        elif suffix == ".3dm":
            loaded = [self._load_3dm(p)]
        else:
            raise CliError(
                f"don't know how to load {suffix!r} files "
                "(known: .xml DIGGS, .csv, .xlsx, .las, .laz, .3dm)"
            )
        if name:
            if len(loaded) > 1:
                raise CliError(
                    f"{p.name} holds {len(loaded)} objects; "
                    "'as <name>' works only for single-object files"
                )
            loaded[0].name = name
        for lo in loaded:
            self.objects[lo.name] = lo
        return loaded

    def _load_diggs(self, p: Path) -> List[LoadedObject]:
        from civilpy.geotech.boring_io import parse_diggs

        holes = parse_diggs(str(p))
        if not holes:
            raise CliError(f"{p.name}: no boreholes found in DIGGS document")
        out = []
        for hole in holes:
            depth = (
                f"{hole.total_depth_ft:g} ft"
                if hole.total_depth_ft is not None
                else "depth unknown"
            )
            out.append(
                LoadedObject(
                    name=hole.boring_id,
                    kind="boring",
                    obj=hole,
                    source=str(p),
                    summary=(
                        f"{depth}, {len(hole.spt)} SPT, "
                        f"{len(hole.grading)} gradations, "
                        f"{len(hole.samples)} samples"
                    ),
                )
            )
        return out

    def _load_table(self, p: Path) -> LoadedObject:
        import pandas as pd

        df = pd.read_csv(p) if p.suffix.lower() == ".csv" else pd.read_excel(p)
        return LoadedObject(
            name=p.stem,
            kind="table",
            obj=df,
            source=str(p),
            summary=f"{len(df)} rows × {len(df.columns)} columns",
        )

    def _load_terrain(self, p: Path) -> LoadedObject:
        require("laspy", "geo")
        from civilpy.transportation.terrain import Terrain

        terrain = Terrain.from_las(p)
        return LoadedObject(
            name=p.stem,
            kind="terrain",
            obj=terrain,
            source=str(p),
            summary="LiDAR TIN surface",
        )

    def _load_3dm(self, p: Path) -> LoadedObject:
        rhino3dm = require("rhino3dm", "rhino")
        model = rhino3dm.File3dm.Read(str(p))
        if model is None:
            raise CliError(f"rhino3dm could not read {p.name}")
        return LoadedObject(
            name=p.stem,
            kind="3dm",
            obj=model,
            source=str(p),
            summary=f"{len(model.Objects)} objects, {len(model.Layers)} layers",
        )

    def resolve_boring(self, ref: str):
        """A ``--boring`` value: the name of a loaded hole, or a DIGGS
        path (single-hole files load implicitly)."""
        lo = self.objects.get(ref)
        if lo is not None:
            if lo.kind != "boring":
                raise CliError(f"'{ref}' is a loaded {lo.kind}, not a boring")
            return lo.obj
        p = Path(ref).expanduser()
        if p.exists():
            holes = self._load_diggs(p)
            if len(holes) > 1:
                names = ", ".join(h.name for h in holes)
                raise CliError(
                    f"{p.name} holds several holes ({names}); load it and "
                    "pass one name"
                )
            return holes[0].obj
        raise CliError(
            f"'{ref}' is neither a loaded boring nor a DIGGS file path"
        )


@dataclass
class CliContext:
    """What a command runner gets besides its inputs."""

    workspace: Workspace = field(default_factory=Workspace)
    interactive: bool = False
