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

"""Topology-optimized strut-and-tie generation.

Turn a concrete D-region (a drawn rectangle or arbitrary polygon, with supports
and loads) into an optimized strut-and-tie truss via SIMP topology optimization
and skeleton extraction, then size and cost it.  Implements the roadmap in
``docs/StrutAndTieSolver.md``.

Typical use::

    from civilpy.structural.stm_topology import DRegionProblem

    p = DRegionProblem.rectangle(20, 10, thickness=2.0, vol_frac=0.35)
    p.add_support(1, 0, bearing=1.0)
    p.add_support(19, 0, fix_x=False, bearing=1.0)
    p.add_load(10, 10, fy=-600, bearing=1.0)
    result = p.solve()
    print(result.summary())
    result.plot()
"""

from .problem import DRegionProblem, Material, Support, Load
from .mesh import GroundMesh
from .simp import optimize_density, DensityResult
from .extract import (
    extract_truss, refine_truss, layout_optimize_truss, is_stable,
)
from .pipeline import optimize_to_stm, STMResult
from .design import (
    optimize_pier_cap, PierCapDesign, DepthCandidate, governing_strut_angle,
)

__all__ = [
    "DRegionProblem", "Material", "Support", "Load",
    "GroundMesh", "optimize_density", "DensityResult",
    "extract_truss", "refine_truss", "layout_optimize_truss", "is_stable",
    "optimize_to_stm", "STMResult",
    "optimize_pier_cap", "PierCapDesign", "DepthCandidate",
    "governing_strut_angle",
]
