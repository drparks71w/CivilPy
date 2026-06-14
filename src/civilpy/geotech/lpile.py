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

"""LPILE (Ensoft) integration: input-file generation and output parsing.

LPILE has no COM/SDK automation interface, so -- following the same
codegen-run-parse pattern as the CANDE box-culvert wrapper in
:mod:`civilpy.structural.cande` -- this module integrates through LPILE's
versioned ASCII data-file format.  An :class:`LPileModel` carries the pile
section, the soil layers (each backed by a p-y curve from
:mod:`civilpy.geotech.lateral_pile`, so the same models drive both the
in-process solver and the LPILE run), and the pile-head loading; it emits a
data file with :meth:`LPileModel.to_lpd`.  Output is read back from an LPILE
text report with :func:`parse_lpile_report` into an :class:`LPileResults`
object holding the depth-wise deflection / moment / shear / soil-reaction
profiles and the pile-head response, with plotly plot helpers.

Because LPILE is rarely installed alongside civilpy,
:meth:`LPileModel.simulate` runs the equivalent analysis with civilpy's own
finite-element p-y solver and returns the same :class:`LPileResults`, so a
model is fully usable (and round-trips through the report format) without
the Ensoft engine.

Soil layering can be sourced from a
:class:`~civilpy.geotech.soil_profile.SoilProfile` (and therefore from a
parsed DIGGS boring) via :meth:`LPileModel.from_soil_profile`.

Units: inches, pounds, psi (unit weights pci), matching LPILE's English
unit set and :mod:`civilpy.geotech.lateral_pile`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from civilpy.geotech.lateral_pile import (
    LinearPY,
    PYCurve,
    SandPY,
    SoftClayPY,
    StiffClayPY,
    solve_lateral_pile,
)
from civilpy.geotech.soil_profile import SoilProfile

#: LPILE ASCII data-file format this module targets.  LPILE's data exchange
#: file is versioned ("Data Format Version 9/10/11"); we pin 11.
DATA_FORMAT_VERSION = 11

#: Inches per foot, for SoilProfile (ft, pcf) -> LPILE (in, pci) conversion.
_IN_PER_FT = 12.0
#: pcf -> pci.
_PCI_PER_PCF = 1.0 / 1728.0


def _lpile_model_spec(curve: PYCurve) -> tuple[str, dict]:
    """Map a civilpy p-y curve to an LPILE soil-model name and its
    parameter fields."""
    if isinstance(curve, SoftClayPY):
        return "Matlock Soft Clay", {
            "c": curve.cu, "eps50": curve.eps50, "gamma": curve.gamma,
        }
    if isinstance(curve, StiffClayPY):
        return "Stiff Clay without Free Water", {
            "c": curve.cu, "eps50": curve.eps50, "gamma": curve.gamma,
        }
    if isinstance(curve, SandPY):
        return "API Sand", {
            "phi": curve.phi_deg, "k": curve.k, "gamma": curve.gamma,
        }
    if isinstance(curve, LinearPY):
        return "Elastic Subgrade", {"k": curve.k}
    raise TypeError(f"no LPILE soil model for curve type {type(curve).__name__}")


@dataclass
class PileSection:
    """A prismatic pile section.

    ``length`` and ``diameter`` in inches, ``ei`` the flexural stiffness
    (lb-in^2).  ``area`` and ``modulus`` are optional (used only for the
    data-file fields and axial reporting); if omitted, ``modulus`` is taken
    as steel and ``area`` from a solid circle."""

    length: float
    diameter: float
    ei: float
    modulus: float = 29.0e6
    area: float | None = None

    def __post_init__(self):
        if self.length <= 0 or self.diameter <= 0 or self.ei <= 0:
            raise ValueError("length, diameter, ei must be positive")
        if self.area is None:
            self.area = 3.141592653589793 * self.diameter ** 2 / 4.0

    @property
    def moment_of_inertia(self) -> float:
        """I implied by EI / modulus (in^4)."""
        return self.ei / self.modulus


@dataclass
class LPileSoilLayer:
    """One LPILE soil layer over a depth range, backed by a p-y curve.

    ``top``/``bottom`` are depths below the pile head (in); ``curve`` is the
    :class:`~civilpy.geotech.lateral_pile.PYCurve` supplying both the LPILE
    p-y model parameters and the in-process simulation."""

    top: float
    bottom: float
    curve: PYCurve
    name: str = ""

    def __post_init__(self):
        if self.bottom <= self.top:
            raise ValueError("layer bottom must be below its top")

    @property
    def model_name(self) -> str:
        return _lpile_model_spec(self.curve)[0]

    def contains(self, depth: float) -> bool:
        return self.top <= depth < self.bottom


@dataclass
class LPileLoad:
    """Pile-head loading.  ``condition`` 1 = shear + moment (free head),
    2 = shear + slope (slope in radians, 0 for a fixed head).  Forces in
    lb / lb-in."""

    shear: float
    moment: float = 0.0
    axial: float = 0.0
    condition: int = 1
    slope: float = 0.0

    def __post_init__(self):
        if self.condition not in (1, 2):
            raise ValueError("condition must be 1 (shear+moment) or 2 (shear+slope)")


class LPileModel:
    """An LPILE single-pile model: section, soil layers, and head loading."""

    def __init__(
        self,
        section: PileSection,
        layers: list[LPileSoilLayer],
        load: LPileLoad,
        n_increments: int = 100,
        cyclic: bool = False,
        n_cycles: int = 1,
        title: str | None = None,
    ):
        if not layers:
            raise ValueError("at least one soil layer is required")
        self.section = section
        self.layers = sorted(layers, key=lambda lyr: lyr.top)
        self.load = load
        self.n_increments = int(n_increments)
        self.cyclic = bool(cyclic)
        self.n_cycles = int(n_cycles)
        self.title = title or "civilpy LPILE model"

    # ------------------------------------------------------ soil sourcing

    @classmethod
    def from_soil_profile(
        cls,
        profile: SoilProfile,
        curves: list[PYCurve],
        section: PileSection,
        load: LPileLoad,
        **kwargs,
    ) -> "LPileModel":
        """Build a model whose layers follow a
        :class:`~civilpy.geotech.soil_profile.SoilProfile` (feet, pcf),
        converting depths to inches.  ``curves`` is one p-y curve per soil
        layer (top to bottom)."""
        if len(curves) != len(profile.layers):
            raise ValueError("need exactly one p-y curve per profile layer")
        layers = []
        top = 0.0
        for soil, curve in zip(profile.layers, curves):
            bottom = top + soil.thickness * _IN_PER_FT
            layers.append(LPileSoilLayer(top, bottom, curve, name=soil.name))
            top = bottom
        return cls(section=section, layers=layers, load=load, **kwargs)

    def curve_at(self, depth: float) -> PYCurve:
        """The p-y curve governing a given depth (in); the deepest layer
        extends below its nominal bottom."""
        for layer in self.layers:
            if layer.contains(depth):
                return layer.curve
        return self.layers[-1].curve

    # ----------------------------------------------------------- codegen

    def to_lpd(self) -> str:
        """The complete LPILE ASCII data file as a string."""
        s = self.section
        lines = [
            f"LPILE Data File - Data Format Version {DATA_FORMAT_VERSION}",
            f"TITLE: {self.title}",
            "UNITS: English (in, lb)",
            "",
            "SECTION: PROGRAM OPTIONS",
            f"  Number of Pile Increments = {self.n_increments}",
            f"  Loading Type = {'Cyclic' if self.cyclic else 'Static'}",
            f"  Number of Cycles = {self.n_cycles}",
            "",
            "SECTION: PILE PROPERTIES",
            f"  Pile Length = {s.length:.3f}",
            f"  Diameter = {s.diameter:.3f}",
            f"  Flexural Stiffness EI = {s.ei:.4E}",
            f"  Modulus = {s.modulus:.4E}",
            f"  Area = {s.area:.4f}",
            f"  Moment of Inertia = {s.moment_of_inertia:.4f}",
            "",
            "SECTION: SOIL LAYERS",
            "  Layer, Top, Bottom, p-y Model, Parameters",
        ]
        for i, layer in enumerate(self.layers, start=1):
            name, params = _lpile_model_spec(layer.curve)
            kv = ", ".join(f"{k}={v:g}" for k, v in params.items())
            lines.append(
                f"  {i}, {layer.top:.3f}, {layer.bottom:.3f}, {name}, {kv}"
            )
        lines += [
            "",
            "SECTION: PILE HEAD LOADING",
            f"  Condition = {self.load.condition}",
            f"  Shear = {self.load.shear:.3f}",
            f"  Moment = {self.load.moment:.3f}",
            f"  Axial = {self.load.axial:.3f}",
            f"  Slope = {self.load.slope:.6f}",
            "",
            "END OF DATA",
        ]
        return "\n".join(lines) + "\n"

    def write_lpd(self, work_dir, prefix: str = "pile") -> Path:
        """Write the data file to ``work_dir`` and return its path."""
        path = Path(work_dir) / f"{prefix}.lpd"
        path.write_text(self.to_lpd())
        return path

    # ------------------------------------------------------------- solve

    def simulate(self, **solver_kwargs) -> "LPileResults":
        """Run the analysis with civilpy's own FE p-y solver (no Ensoft
        engine needed) and return :class:`LPileResults`."""
        fixed = self.load.condition == 2 and self.load.slope == 0.0
        res = solve_lateral_pile(
            self.curve_at,
            length=self.section.length,
            ei=self.section.ei,
            shear=self.load.shear,
            moment=self.load.moment,
            n_elem=self.n_increments,
            fixed_head=fixed,
            **solver_kwargs,
        )
        return LPileResults(
            depth=res.depth, deflection=res.deflection, moment=res.moment,
            shear=res.shear, soil_reaction=res.soil_reaction,
            pile_head_deflection=res.head_deflection,
            max_moment=res.max_moment, max_moment_depth=res.max_moment_depth,
            source="civilpy-fe",
        )

    def run(self, work_dir=None, prefix: str = "pile", lpile_exe=None
            ) -> "LPileResults":
        """Run the model through an installed LPILE engine.  LPILE has no
        automation API, so this writes the data file, invokes the LPILE
        command-line executable on it, and parses the text report.  Raises
        if no executable is available -- use :meth:`simulate` to analyze
        without Ensoft LPILE."""
        import shutil
        import subprocess
        import tempfile

        exe = lpile_exe or shutil.which("lpile") or shutil.which("LPile")
        if exe is None:
            raise FileNotFoundError(
                "no LPILE executable found; pass lpile_exe= or use "
                "LPileModel.simulate() for the built-in p-y solver"
            )
        if work_dir is None:  # pragma: no cover - needs a local LPILE install
            work_dir = tempfile.mkdtemp(prefix="civilpy_lpile_")
        work_dir = Path(work_dir)  # pragma: no cover
        lpd = self.write_lpd(work_dir, prefix)  # pragma: no cover
        subprocess.run([exe, str(lpd)], cwd=work_dir, check=True)  # pragma: no cover
        report = (work_dir / f"{prefix}.lpo")  # pragma: no cover
        return parse_lpile_report(report.read_text())  # pragma: no cover


@dataclass
class LPileResults:
    """Depth-wise pile response from an LPILE run or simulation."""

    depth: np.ndarray
    deflection: np.ndarray
    moment: np.ndarray
    shear: np.ndarray
    soil_reaction: np.ndarray
    pile_head_deflection: float
    max_moment: float
    max_moment_depth: float
    pile_head_rotation: float = 0.0
    source: str = "lpile"

    @property
    def lateral_stiffness(self) -> float:
        """Secant pile-head lateral stiffness (lb/in) = head shear / head
        deflection, recovered from the shear at the top node."""
        if self.pile_head_deflection == 0.0:
            return float("inf")
        return float(self.shear[0] / self.pile_head_deflection)

    def to_report_text(self) -> str:
        """Format the results as an LPILE-style text report (the inverse of
        :func:`parse_lpile_report`)."""
        out = [
            "LPILE Output Report",
            f"  Results source: {self.source}",
            "",
            "         Depth     Deflection      Moment       Shear   Soil Reaction",
            "          (in)        (in)        (lb-in)        (lb)        (lb/in)",
            "    " + "-" * 70,
        ]
        for z, y, m, v, p in zip(
            self.depth, self.deflection, self.moment, self.shear,
            self.soil_reaction
        ):
            out.append(
                f"   {z:11.3f} {y:13.5E} {m:13.5E} {v:13.5E} {p:13.5E}"
            )
        out += [
            "",
            f"  Pile-head deflection  = {self.pile_head_deflection:.5E} in",
            f"  Pile-head rotation    = {self.pile_head_rotation:.5E} radians",
            f"  Maximum bending moment = {self.max_moment:.5E} lb-in"
            f"  at depth {self.max_moment_depth:.3f} in",
        ]
        return "\n".join(out) + "\n"

    def plot(self):
        """A 1x4 plotly figure of deflection / moment / shear / soil
        reaction vs depth (depth increasing downward)."""
        from plotly.subplots import make_subplots

        y = -self.depth
        fig = make_subplots(
            rows=1, cols=4, shared_yaxes=True,
            subplot_titles=("Deflection (in)", "Moment (lb-in)",
                            "Shear (lb)", "Soil reaction (lb/in)"),
        )
        for col, data in enumerate(
            (self.deflection, self.moment, self.shear, self.soil_reaction),
            start=1,
        ):
            fig.add_scatter(x=data, y=y, mode="lines", row=1, col=col,
                            showlegend=False)
        fig.update_yaxes(title_text="Depth (in)", row=1, col=1)
        return fig


_NUM = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"


def parse_lpile_report(text: str) -> LPileResults:
    """Parse an LPILE text report into :class:`LPileResults`.

    Reads the depth / deflection / moment / shear / soil-reaction table
    (any block of rows with five numeric columns under a header naming
    ``Depth`` and ``Deflection``) and the pile-head deflection, rotation,
    and maximum-moment summary lines."""
    lines = text.splitlines()
    rows: list[list[float]] = []
    in_table = False
    row_re = re.compile(rf"^\s*({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})\s+({_NUM})\s*$")
    for line in lines:
        low = line.lower()
        if "depth" in low and "deflection" in low:
            in_table = True
            continue
        if in_table:
            m = row_re.match(line)
            if m:
                rows.append([float(g) for g in m.groups()])
            elif rows:
                in_table = False  # table ended
    if not rows:
        raise ValueError("no results table found in LPILE report")
    arr = np.array(rows)
    depth, defl, moment, shear, soil = (arr[:, i] for i in range(5))

    def _find(pattern, default=None):
        m = re.search(pattern, text, re.IGNORECASE)
        return float(m.group(1)) if m else default

    head_defl = _find(rf"Pile-head deflection\s*=\s*({_NUM})", float(defl[0]))
    head_rot = _find(rf"Pile-head rotation\s*=\s*({_NUM})", 0.0)
    max_m = _find(rf"Maximum bending moment\s*=\s*({_NUM})",
                  float(np.max(np.abs(moment))))
    max_m_depth = _find(rf"Maximum bending moment\s*=\s*{_NUM}\s*lb-in\s*at depth\s*({_NUM})",
                        float(depth[int(np.argmax(np.abs(moment)))]))
    return LPileResults(
        depth=depth, deflection=defl, moment=moment, shear=shear,
        soil_reaction=soil, pile_head_deflection=head_defl,
        pile_head_rotation=head_rot, max_moment=max_m,
        max_moment_depth=max_m_depth, source="lpile-report",
    )
