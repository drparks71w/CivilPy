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

"""Turn a boring log into CANDE soil zones.

:mod:`civilpy.structural.cande` builds a buried-culvert model from three
soil materials (in situ, bedding, fill).  This adapter derives those
:class:`~civilpy.structural.cande.SoilMaterial` objects from the measured
:class:`~civilpy.geotech.boring.Borehole`: an SPT-based linear-elastic
soil for the in-situ ground, or a canned Duncan/Selig material chosen from
the gradation and a target compaction for engineered fill/bedding.

The elastic moduli come from the SPT correlations in
:mod:`civilpy.geotech.spt`; they are estimates and should yield to a
laboratory-characterised soil when one exists.
"""

from __future__ import annotations

from civilpy.geotech.boring import Borehole, GradingResult
from civilpy.geotech.spt import (
    elastic_modulus_from_spt,
    elastic_modulus_from_su,
    undrained_shear_strength_from_n,
    unit_weight_from_n,
)
from civilpy.structural.cande import DUNCAN_SELIG_SOILS, SoilMaterial

# Default drained Poisson's ratio by coarse-grained Bowles soil type;
# fine-grained (undrained) soils use ~0.45.
_POISSON = {
    "sand": 0.30,
    "sand_saturated": 0.30,
    "gravelly_sand": 0.30,
    "silty_sand": 0.35,
    "clayey_sand": 0.35,
}
_POISSON_CLAY = 0.45


def soil_material_from_spt(
    n: float,
    soil_type: str = "sand",
    poisson: float | None = None,
    density_pcf: float | None = None,
    name: str | None = None,
) -> SoilMaterial:
    """A linear-elastic :class:`SoilMaterial` from an SPT N value.

    ``soil_type`` is one of the Bowles coarse-grained categories (see
    :func:`civilpy.geotech.spt.elastic_modulus_from_spt`).  Young's modulus
    comes from N; Poisson's ratio and unit weight default by soil type and
    N unless given.
    """
    e_psi = elastic_modulus_from_spt(n, soil_type)
    nu = poisson if poisson is not None else _POISSON.get(soil_type, 0.30)
    gamma = density_pcf if density_pcf is not None else unit_weight_from_n(n, coarse=True)
    return SoilMaterial.elastic(
        e_psi=e_psi, nu=nu, density_pcf=gamma,
        name=name or f"SPT N{int(round(n))} {soil_type}",
    )


def clay_soil_material_from_spt(
    n60: float,
    modulus_ratio: float = 300.0,
    su_factor_psf: float = 92.0,
    poisson: float | None = None,
    density_pcf: float | None = None,
    name: str | None = None,
) -> SoilMaterial:
    """A linear-elastic :class:`SoilMaterial` for a fine-grained soil:
    Su from N60 (Stroud), then Eu = ``modulus_ratio`` * Su."""
    su = undrained_shear_strength_from_n(n60, su_factor_psf)
    e_psi = elastic_modulus_from_su(su, modulus_ratio)
    nu = poisson if poisson is not None else _POISSON_CLAY
    gamma = density_pcf if density_pcf is not None else unit_weight_from_n(n60, coarse=False)
    return SoilMaterial.elastic(
        e_psi=e_psi, nu=nu, density_pcf=gamma,
        name=name or f"Clay N{int(round(n60))}",
    )


def _nearest_compaction(group: str, compaction_percent: float) -> str:
    """Closest canned Duncan/Selig material of ``group`` ("SW"/"ML"/"CL")
    to a target percent standard Proctor."""
    options = []
    for soil in DUNCAN_SELIG_SOILS:
        if soil.startswith(group):
            try:
                options.append((int(soil[len(group):]), soil))
            except ValueError:
                continue
    if not options:
        raise ValueError(f"no Duncan/Selig soils for group {group!r}")
    return min(options, key=lambda o: abs(o[0] - compaction_percent))[1]


def duncan_selig_from_gradation(
    grading: GradingResult,
    compaction_percent: float,
    density_pcf: float,
    fine_group: str = "ML",
) -> SoilMaterial:
    """Pick a canned Duncan/Selig :class:`SoilMaterial` for engineered
    fill/bedding from a gradation and a target compaction.

    Coarse soils (fines < 50%) map to the gravelly-sand ``SW`` family; fine
    soils map to ``fine_group`` (``"ML"`` sandy silt by default, ``"CL"``
    for plastic clays).  The canned material nearest ``compaction_percent``
    standard Proctor is selected.
    """
    fines = grading.fines_percent
    if fines is not None and fines >= 50.0:
        group = fine_group.upper()
    else:
        group = "SW"
    name = _nearest_compaction(group, compaction_percent)
    return SoilMaterial.duncan_selig(name, density_pcf)


def _classify_coarse(grading: GradingResult | None) -> str:
    """Map a gradation to a Bowles coarse-grained soil_type."""
    if grading is None:
        return "sand"
    fines = grading.fines_percent
    if fines is not None and fines >= 12.0:
        return "silty_sand"
    d50 = grading.d50
    if d50 is not None and d50 >= 2.0:  # gravel-sized median
        return "gravelly_sand"
    return "sand"


def in_situ_soil_material(
    borehole: Borehole,
    depth_ft: float,
    energy_ratio: float = 0.60,
    sigma_v_eff_psf: float | None = None,
    density_pcf: float | None = None,
    name: str | None = None,
) -> SoilMaterial:
    """The in-situ CANDE soil zone for ``borehole`` at ``depth_ft``.

    Uses the SPT nearest the depth, classifies coarse vs fine from the
    nearest gradation (fines >= 50% -> clay path), and returns the matching
    linear-elastic :class:`SoilMaterial`.  Raises if the hole has no SPT
    data near the depth.
    """
    spt = None
    if borehole.spt:
        spt = min(borehole.spt, key=lambda s: abs(s.depth_ft - depth_ft))
    if spt is None or spt.n_value is None:
        raise ValueError(
            f"no usable SPT near {depth_ft} ft in boring {borehole.boring_id}"
        )
    grading = borehole.grading_at(depth_ft)
    label = name or f"{borehole.boring_id} @ {depth_ft:g} ft"
    fines = grading.fines_percent if grading else None
    if fines is not None and fines >= 50.0:
        n60 = spt.n60(energy_ratio, rod_length_ft=depth_ft) or spt.n_value
        return clay_soil_material_from_spt(
            n60, density_pcf=density_pcf, name=label
        )
    soil_type = _classify_coarse(grading)
    return soil_material_from_spt(
        spt.n_value, soil_type=soil_type, density_pcf=density_pcf, name=label
    )
