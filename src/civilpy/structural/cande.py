"""Box-culvert soil-structure interaction through CANDE.

CANDE (Culvert ANalysis and DEsign, FHWA) solves the buried-structure
problem the AASHTO simplified methods approximate: incremental embankment
construction, nonlinear soil, and arching around the structure.  This
module builds a CANDE Level-2 box-culvert model (the engine's canned
box mesh), runs it through the `cande-wrapper
<https://pypi.org/project/cande-wrapper/>`_ package, and returns member
force envelopes in the kip/ft units the :mod:`civilpy.structural.aashto`
checks expect — so CANDE supplies the demands and civilpy the capacities.

Install the engine with ``pip install civilpy[cande]`` (or
``pip install cande-wrapper``).  Building the input file needs nothing
beyond civilpy::

    >>> from civilpy.structural.cande import BoxCulvertModel, SoilMaterial
    >>> model = BoxCulvertModel(span_ft=8, rise_ft=6, cover_ft=4,
    ...                         top_thickness_in=10, wall_thickness_in=8)
    >>> print(model.to_cid().splitlines()[0].strip())
    A-1!!ANALYS   2 0  1Box culvert 8 ft x 6 ft, 4 ft cover

The model is a half-mesh of the culvert (symmetric about midspan) with
14 beam elements on the slab/wall centerlines, three soil zones (in situ,
bedding, fill), and the fill placed in incremental lifts.  ``span_ft``
and ``rise_ft`` are centerline dimensions.  Beam elements carry no
self-weight — add the structure dead load to the demands separately.

Results are per foot of culvert length: moments in kip-in/ft, thrust and
shear in kip/ft, enveloped over all construction increments.
"""

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

import math
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from civilpy.structural.aashto.lrfd.concrete import (
    box_culvert_slab_shear,
    rc_rectangular_flexural_resistance,
)

# Duncan/Selig hyperbolic soil models bundled with CANDE: gravelly sand
# (SW), sandy silt (ML), and silty clay (CL) at percent standard Proctor.
DUNCAN_SELIG_SOILS = frozenset({
    "SW100", "SW95", "SW90", "SW85", "SW80", "SW60",
    "ML95", "ML90", "ML85", "ML80", "ML50",
    "CL95", "CL90", "CL85", "CL80", "CL45",
})

# The canned box mesh always builds 14 beam elements over the half-box.
_N_BEAM_ELEMENTS = 14


def _label(name: str) -> str:
    """CANDE input lines start with the right-justified command name and
    a double bang; the fixed-format data fields follow immediately."""
    return name.rjust(25) + "!!"


def _f10(value: float) -> str:
    """A real number in an F10.0 input field."""
    out = f"{value:10.3f}"
    if len(out) > 10:
        out = f"{value:10.4g}"
    return out[:10].rjust(10)


def _i5(value: int) -> str:
    return f"{value:5d}"


@dataclass(frozen=True)
class SoilMaterial:
    """One CANDE soil zone: linear-elastic or a canned Duncan/Selig
    hyperbolic model.  Use the constructors rather than building
    directly."""

    density_pcf: float
    model: str  # "isotropic" or "duncan_selig"
    name: str
    e_psi: float = 0.0
    nu: float = 0.0

    @classmethod
    def elastic(cls, e_psi: float, nu: float, density_pcf: float,
                name: str = "ELASTIC") -> "SoilMaterial":
        """Linear-elastic soil with Young's modulus ``e_psi`` and
        Poisson's ratio ``nu``."""
        return cls(density_pcf=density_pcf, model="isotropic",
                   name=name, e_psi=e_psi, nu=nu)

    @classmethod
    def duncan_selig(cls, name: str, density_pcf: float) -> "SoilMaterial":
        """A canned Duncan/Selig soil (e.g. ``"SW90"`` for gravelly sand
        at 90% standard Proctor)."""
        if name.upper() not in DUNCAN_SELIG_SOILS:
            raise ValueError(
                f"unknown Duncan/Selig soil {name!r}; "
                f"choose from {sorted(DUNCAN_SELIG_SOILS)}"
            )
        return cls(density_pcf=density_pcf, model="duncan_selig",
                   name=name.upper())

    def _d_lines(self, mat_number: int, last: bool) -> list[str]:
        """The D-1/D-2 input lines for this material."""
        limit = "L" if last else " "
        ityp = 1 if self.model == "isotropic" else 3
        lines = [
            _label("D-1") + limit + f"{mat_number:4d}" + _i5(ityp)
            + _f10(self.density_pcf) + self.name[:20].ljust(20)
        ]
        if self.model == "isotropic":
            lines.append(_label("D-2.Isotropic")
                         + _f10(self.e_psi) + _f10(self.nu))
        else:
            # NON=0, failure ratio default, IBULK=1 selects the
            # Duncan/Selig bulk-modulus form, NEWDS=1 the current
            # load/unload/reload algorithm.
            lines.append(_label("D-2.Duncan")
                         + _i5(0) + _f10(0.5) + _i5(1) + _i5(1))
        return lines


@dataclass
class MemberForces:
    """Force envelope for one culvert member, per foot of length:
    ``moment`` kip-in/ft, ``thrust`` kip/ft (compression positive),
    ``shear`` kip/ft, and the moment concurrent with the peak shear
    (for the Vu*de/Mu term of the slab shear check)."""

    moment: float = 0.0
    thrust: float = 0.0
    shear: float = 0.0
    shear_concurrent_moment: float = 0.0

    @property
    def moment_kip_ft(self) -> float:
        return self.moment / 12.0


class BoxCulvertModel:
    """A single-cell box culvert under earth fill, analyzed with the
    CANDE Level-2 box mesh.

    ``span_ft``/``rise_ft`` are centerline dimensions; ``cover_ft`` the
    fill above the top slab.  Wall/slab stiffnesses come from gross
    concrete sections of the given thicknesses (``e_concrete_psi``
    defaults to 57000*sqrt(f'c) with f'c = 4 ksi).  ``trench_width_ft``
    switches the mesh from embankment to trench installation.  Fill is
    placed in incremental lifts; when the cover exceeds 1.5 times the
    rise the mesh is truncated and the remainder applied as surface
    pressure (handled by the engine; an extra load step is added
    automatically).
    """

    def __init__(
        self,
        span_ft: float,
        rise_ft: float,
        cover_ft: float,
        *,
        top_thickness_in: float,
        wall_thickness_in: float,
        bottom_thickness_in: float | None = None,
        f_c_ksi: float = 4.0,
        e_concrete_psi: float | None = None,
        nu_concrete: float = 0.17,
        fill: SoilMaterial | None = None,
        in_situ: SoilMaterial | None = None,
        bedding: SoilMaterial | None = None,
        trench_width_ft: float | None = None,
        bedding_depth_in: float = 12.0,
        load_steps: int | None = None,
        title: str | None = None,
    ):
        if cover_ft < 0.0:
            raise ValueError("cover_ft must be >= 0")
        self.span_ft = float(span_ft)
        self.rise_ft = float(rise_ft)
        self.cover_ft = float(cover_ft)
        self.top_thickness_in = float(top_thickness_in)
        self.wall_thickness_in = float(wall_thickness_in)
        self.bottom_thickness_in = float(
            top_thickness_in if bottom_thickness_in is None
            else bottom_thickness_in
        )
        self.f_c_ksi = float(f_c_ksi)
        self.e_concrete_psi = (
            57000.0 * math.sqrt(f_c_ksi * 1000.0)
            if e_concrete_psi is None else float(e_concrete_psi)
        )
        self.nu_concrete = float(nu_concrete)
        self.fill = fill or SoilMaterial.duncan_selig("SW90", 120.0)
        self.in_situ = in_situ or SoilMaterial.elastic(
            5000.0, 0.33, 130.0, name="IN SITU")
        self.bedding = bedding or SoilMaterial.elastic(
            3000.0, 0.30, 120.0, name="BEDDING")
        self.trench_width_ft = trench_width_ft
        self.bedding_depth_in = float(bedding_depth_in)
        # The canned mesh truncates the soil column at 1.5*rise of cover
        # and converts the rest to pressure, applied only in load steps
        # beyond the nine construction increments.
        truncated = cover_ft * 12.0 > 1.5 * rise_ft * 12.0
        self.load_steps = (
            (10 if truncated else 9) if load_steps is None
            else int(load_steps)
        )
        self.title = title or (
            f"Box culvert {span_ft:g} ft x {rise_ft:g} ft, "
            f"{cover_ft:g} ft cover"
        )

    # Beam elements of the canned half-mesh, numbered from the crown:
    # 1-4 across the half top slab, 5-10 down the wall, 11-14 back
    # along the half bottom slab.
    _MEMBER_ELEMENTS = {
        "top_slab": range(1, 5),
        "wall": range(5, 11),
        "bottom_slab": range(11, 15),
    }

    def to_cid(self) -> str:
        """The complete CANDE input file as a string."""
        r1 = self.span_ft * 12.0 / 2.0
        r2 = self.rise_ft * 12.0 / 2.0
        lines = [
            # A-1: analysis mode, solution level 2, service method,
            # one pipe group
            _label("A-1") + "ANALYS".ljust(8) + " " + "2" + " 0" + "  1"
            + self.title[:60].ljust(60),
            # A-2: BASIC (linear beam) pipe type, canned mesh 2 = box
            _label("A-2.L12") + "BASIC".ljust(8) + "  " + _i5(2),
        ]
        # B-1: E, nu, A, I per unit length for each element range
        for (lo, hi), t in (
            ((1, 4), self.top_thickness_in),
            ((5, 10), self.wall_thickness_in),
            ((11, 14), self.bottom_thickness_in),
        ):
            lines.append(
                _label("B-1.Basic") + _i5(lo) + _i5(hi)
                + _f10(self.e_concrete_psi) + _f10(self.nu_concrete)
                + _f10(t) + _f10(t**3 / 12.0) + _f10(0.0)
            )
        lines.append(_label("B-2.Basic") + _i5(0))  # no buckling
        mesh = "EMBA" if self.trench_width_ft is None else "TREN"
        lines.append(_label("C-1.L2.Box") + mesh + self.title[:68].ljust(68))
        # C-2: plot/print flags, load steps, half span/rise (in),
        # cover (ft), fill density (pcf), trench width (ft), bedding (in)
        lines.append(
            _label("C-2.L2.Box") + _i5(3) + _i5(1) + _i5(0)
            + _i5(self.load_steps)
            + _f10(r1) + _f10(r2) + _f10(self.cover_ft)
            + _f10(self.fill.density_pcf)
            + _f10(self.trench_width_ft or 0.0)
            + _f10(self.bedding_depth_in)
        )
        # Soil zones: 1 = in situ, 2 = bedding, 3 = fill
        lines += self.in_situ._d_lines(1, last=False)
        lines += self.bedding._d_lines(2, last=False)
        lines += self.fill._d_lines(3, last=True)
        lines.append(_label("A-1") + "STOP".ljust(8))
        return "\n".join(lines) + "\n"

    def write_cid(self, work_dir, prefix: str = "culvert") -> Path:
        """Write the input file to ``work_dir`` and return its path."""
        path = Path(work_dir) / f"{prefix}.cid"
        path.write_text(self.to_cid())
        return path

    def run(self, work_dir=None, prefix: str = "culvert"
            ) -> "BoxCulvertResults":
        """Run the model through the CANDE engine and return the parsed
        results.  Requires the ``cande-wrapper`` package; outputs land in
        ``work_dir`` (a temporary directory by default)."""
        try:
            from cande_wrapper import CandeEngine
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "running a CANDE model needs the cande-wrapper package: "
                "pip install civilpy[cande]"
            ) from exc
        if work_dir is None:
            work_dir = tempfile.mkdtemp(prefix="civilpy_cande_")
        work_dir = Path(work_dir)
        self.write_cid(work_dir, prefix)
        engine = CandeEngine(work_dir=work_dir)
        engine_result = engine.run(prefix)
        text = engine_result.output_text
        if "NORMAL EXIT" not in text:
            raise RuntimeError(
                f"CANDE did not finish normally; see {work_dir}/{prefix}.out"
            )
        return BoxCulvertResults(self, work_dir, prefix)


class BoxCulvertResults:
    """Member force envelopes parsed from a CANDE box-culvert run.

    ``members`` maps ``"top_slab"``/``"wall"``/``"bottom_slab"`` to
    :class:`MemberForces` enveloped over every construction increment;
    corner nodes contribute to both adjacent members.  ``steps`` holds
    the raw nodal rows per increment for custom post-processing.
    """

    def __init__(self, model: BoxCulvertModel, work_dir, prefix: str):
        self.model = model
        self.work_dir = Path(work_dir)
        self.prefix = prefix
        xml_path = self.work_dir / f"{prefix}_BeamResults.xml"
        self.steps = _parse_beam_results(xml_path)
        self.members = self._envelope()

    def _envelope(self) -> dict:
        r1 = self.model.span_ft * 6.0  # half span, inches
        r2 = self.model.rise_ft * 6.0
        tol = 1e-3
        members = {name: MemberForces() for name in
                   ("top_slab", "wall", "bottom_slab")}

        def groups_for(x: float, y: float):
            if abs(y - r2) < tol:
                yield "top_slab"
            if abs(x - r1) < tol:
                yield "wall"
            if abs(y + r2) < tol:
                yield "bottom_slab"

        # CANDE works in lb and inches on a 1-inch slice; convert to
        # kip-in/ft and kip/ft.
        m_scale = 12.0 / 1000.0
        for rows in self.steps.values():
            for row in rows:
                m = abs(row["moment"]) * m_scale
                n = -row["thrust"] * m_scale  # compression positive
                v = abs(row["shear"]) * m_scale
                for name in groups_for(row["x"], row["y"]):
                    mf = members[name]
                    mf.moment = max(mf.moment, m)
                    mf.thrust = max(mf.thrust, n)
                    if v > mf.shear:
                        mf.shear = v
                        mf.shear_concurrent_moment = m
        return members

    # ── Spec-check glue ───────────────────────────────────────────────

    def flexure_check(self, member: str, a_s: float, d_s: float,
                      f_y: float = 60.0, load_factor: float = 1.3):
        """Flexural check of one member (per-foot strip): the enveloped
        CANDE moment times ``load_factor`` (EV maximum by default)
        becomes the demand of 5.6.3.2.3.  ``a_s`` in in^2/ft, ``d_s``
        in inches."""
        forces = self.members[member]
        return rc_rectangular_flexural_resistance(
            a_s=a_s, f_y=f_y, f_c=self.model.f_c_ksi, b=12.0, d_s=d_s,
            m_u=load_factor * forces.moment,
        )

    def slab_shear_check(self, member: str, a_s: float, d_e: float,
                         load_factor: float = 1.3):
        """Shear check of a slab member under >= 2 ft of fill
        (5.12.7.3), using the enveloped shear and its concurrent
        moment from the CANDE run."""
        forces = self.members[member]
        return box_culvert_slab_shear(
            b=12.0, d_e=d_e, f_c=self.model.f_c_ksi, a_s=a_s,
            v_u=load_factor * forces.shear,
            m_u=load_factor * forces.shear_concurrent_moment,
            fill_ft=self.model.cover_ft,
        )


def _parse_beam_results(xml_path) -> dict:
    """Nodal beam forces per construction increment from a CANDE
    ``*_BeamResults.xml`` file: {step: [{node, element, x, y, moment,
    thrust, shear}, ...]} in the engine's lb/inch units."""
    root = ET.parse(xml_path).getroot()
    steps: dict[int, list[dict]] = {}
    for br in root.iter("beamResults"):
        rows = []
        for rd in br.iter("resultsData"):
            rows.append({
                "node": int(rd.findtext("nodeNumber")),
                "element": int(rd.findtext("elementNumber")),
                "x": float(rd.findtext("xCoord")),
                "y": float(rd.findtext("yCoord")),
                "moment": float(rd.findtext("bendingMoment")),
                "thrust": float(rd.findtext("thrustForce")),
                "shear": float(rd.findtext("shearForce")),
            })
        steps[int(br.findtext("constIncrement"))] = rows
    return steps
