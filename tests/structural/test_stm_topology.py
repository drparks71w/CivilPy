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

"""Tests for the topology-optimized strut-and-tie pipeline and the
direct-stiffness (indeterminate) solver upgrade."""

import math

import numpy as np
import pytest

from civilpy.structural.strut_and_tie import StrutAndTieModel
from civilpy.structural.stm_topology import DRegionProblem, Material
from civilpy.structural.stm_topology.mesh import GroundMesh
from civilpy.structural.stm_topology.simp import optimize_density, element_stiffness
from civilpy.structural.stm_topology.extract import (
    zhang_suen, extract_truss, is_stable,
)


# ── Phase 4: direct-stiffness / indeterminate solver ─────────────────────────

def test_determinate_solve_unchanged():
    """The method-of-joints path must give the documented deep-beam answer."""
    m = StrutAndTieModel()
    for n, x, y in [("A", 0, 0), ("B", 8, 0), ("C", 4, 4)]:
        m.add_node(n, x, y)
    m.add_member("A", "C"); m.add_member("B", "C"); m.add_member("A", "B")
    m.add_support("A", fix_x=True, fix_y=True); m.add_support("B", fix_y=True)
    m.add_load("C", fy=-100)
    f = m.solve()
    assert m.degree_of_indeterminacy() == 0
    assert round(f[("A", "B")], 2) == 50.0
    assert round(f[("A", "C")], 2) == -70.71


def test_indeterminate_equilibrium():
    """A braced square (one redundant) solves by DSM and satisfies statics."""
    m = StrutAndTieModel()
    for n, x, y in [("A", 0, 0), ("B", 10, 0), ("C", 10, 10), ("D", 0, 10)]:
        m.add_node(n, x, y)
    for a, b in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"),
                 ("A", "C"), ("B", "D")]:
        m.add_member(a, b)
    m.add_support("A", fix_x=True, fix_y=True); m.add_support("B", fix_y=True)
    m.add_load("C", fy=-50)
    assert m.degree_of_indeterminacy() == 1
    m.solve()  # auto -> stiffness
    ry = sum(v[1] for v in m.reactions.values())
    assert ry == pytest.approx(50.0, abs=1e-6)
    rx = sum(v[0] for v in m.reactions.values())
    assert rx == pytest.approx(0.0, abs=1e-6)


def test_dsm_matches_joints_on_determinate():
    """DSM and method-of-joints must agree where both are valid."""
    m = StrutAndTieModel()
    for n, x, y in [("A", 0, 0), ("B", 8, 0), ("C", 4, 4)]:
        m.add_node(n, x, y)
    m.add_member("A", "C"); m.add_member("B", "C"); m.add_member("A", "B")
    m.add_support("A", fix_x=True, fix_y=True); m.add_support("B", fix_y=True)
    m.add_load("C", fy=-100)
    fj = dict(m.solve(method="joints"))
    fs = dict(m.solve(method="stiffness"))
    for k in fj:
        assert fj[k] == pytest.approx(fs[k], abs=1e-6)


def test_mechanism_raises():
    m = StrutAndTieModel()
    for n, x, y in [("A", 0, 0), ("B", 10, 0), ("C", 20, 0)]:
        m.add_node(n, x, y)
    m.add_member("A", "B"); m.add_member("B", "C")
    m.add_support("A", fix_x=True, fix_y=True); m.add_support("C", fix_y=True)
    m.add_load("B", fy=-10)
    with pytest.raises(ValueError):
        m.solve(method="stiffness")


# ── Phase 1-2: mesh + SIMP ───────────────────────────────────────────────────

def test_element_stiffness_properties():
    KE = element_stiffness(0.2)
    assert KE.shape == (8, 8)
    assert np.allclose(KE, KE.T)                       # symmetric
    assert np.allclose(KE.sum(axis=0), 0, atol=1e-9)   # rigid-body: zero row sums


def test_mesh_masks_polygon():
    p = DRegionProblem.rectangle(20, 10, thickness=2.0)
    mesh = GroundMesh(p, nelx=40)
    assert mesh.nelx == 40 and mesh.nely == 20
    assert mesh.active.all()                # full rectangle, no voids
    # a void removes interior elements
    p.voids = [[(8, 4), (12, 4), (12, 6), (8, 6)]]
    mesh2 = GroundMesh(p, nelx=40)
    assert mesh2.active.sum() < mesh2.in_domain.size


def test_simp_runs_and_reduces_compliance():
    p = DRegionProblem.rectangle(20, 10, thickness=2.0, vol_frac=0.35)
    p.add_support(1, 0, bearing=1.5)
    p.add_support(19, 0, fix_x=False, bearing=1.5)
    p.add_load(10, 10, fy=-600, bearing=1.5)
    mesh = GroundMesh(p, nelx=40)
    res = optimize_density(mesh, vol_frac=0.35, max_iter=30)
    assert res.history[-1] < res.history[0]            # compliance drops
    assert 0.0 <= res.density.min() and res.density.max() <= 1.0 + 1e-9


# ── Phase 3: extraction (thinning) ───────────────────────────────────────────

def test_zhang_suen_thins_to_one_pixel():
    img = np.zeros((9, 20), bool)
    img[3:6, 2:18] = True            # a 3-px-thick bar
    skel = zhang_suen(img)
    assert skel.sum() < img.sum()
    # each populated column has a single skeleton pixel through the middle band
    cols = np.where(skel.any(axis=0))[0]
    for c in cols:
        assert skel[:, c].sum() == 1


# ── Phases 1-5: end-to-end pipeline ──────────────────────────────────────────

def test_deep_beam_pipeline_statics():
    """Rectangle deep beam → tied arch with the textbook tie/strut forces."""
    span, depth = 18.0, 10.0
    p = DRegionProblem.rectangle(20, depth, thickness=2.0, vol_frac=0.35)
    p.add_support(1, 0, bearing=1.5)
    p.add_support(19, 0, fix_x=False, bearing=1.5)
    p.add_load(10, depth, fy=-600, bearing=1.5)
    result = p.solve(nelx=60, max_iter=40)

    assert result.stable
    m = result.model
    # vertical equilibrium
    ry = sum(v[1] for v in m.reactions.values())
    assert ry == pytest.approx(600.0, abs=1.0)
    # exactly one tension tie (the bottom chord) and compression struts
    ties = [f for f in result.forces.values() if f > 1e-6]
    struts = [f for f in result.forces.values() if f < -1e-6]
    assert ties and struts
    # tie force ~ (P/2)*(half span)/(arch height) for the tied arch
    expected_tie = 300.0 * (span / 2) / depth
    assert max(ties) == pytest.approx(expected_tie, rel=0.25)


def test_pipeline_sizes_ties_and_costs():
    p = DRegionProblem.rectangle(20, 10, thickness=2.0, vol_frac=0.35)
    p.add_support(1, 0, bearing=1.5)
    p.add_support(19, 0, fix_x=False, bearing=1.5)
    p.add_load(10, 10, fy=-600, bearing=1.5)
    result = p.solve(nelx=60, max_iter=40)
    assert result.report.ties
    gov = max(result.report.ties, key=lambda t: t.force)
    assert gov.bar_count >= 1
    # provided steel meets demand (capacity/demand >= ~1)
    assert gov.check.ratio >= 0.99
    assert result.report.cost.total > 0


def test_arbitrary_polygon_void_pipeline_runs():
    p = DRegionProblem.rectangle(20, 10, thickness=2.0, vol_frac=0.4)
    p.voids = [[(8, 4), (12, 4), (12, 6), (8, 6)]]
    p.add_support(1, 0, bearing=1.5)
    p.add_support(19, 0, fix_x=False, bearing=1.5)
    p.add_load(10, 10, fy=-600, bearing=1.5)
    result = p.solve(nelx=60, max_iter=40)
    assert len(result.model.nodes) >= 3


# ── Phase 3½: ground-structure refinement / stability ────────────────────────

def test_is_stable_detects_mechanism():
    """is_stable must flag an under-braced truss (collinear chain) and accept a
    properly triangulated one — the honest test the pipeline relies on."""
    mech = StrutAndTieModel()
    for n, x, y in [("A", 0, 0), ("B", 10, 0), ("C", 20, 0)]:
        mech.add_node(n, x, y)
    mech.add_member("A", "B"); mech.add_member("B", "C")
    mech.add_support("A", fix_x=True, fix_y=True); mech.add_support("C", fix_y=True)
    assert not is_stable(mech)

    tri = StrutAndTieModel()
    for n, x, y in [("A", 0, 0), ("B", 8, 0), ("C", 4, 4)]:
        tri.add_node(n, x, y)
    tri.add_member("A", "C"); tri.add_member("B", "C"); tri.add_member("A", "B")
    tri.add_support("A", fix_x=True, fix_y=True); tri.add_support("B", fix_y=True)
    assert is_stable(tri)


def test_pier_cap_multipanel():
    """Three columns + five girder loads must produce a rich, symmetric,
    multi-panel strut-and-tie model — not the bare triangle a single load
    collapses to — via the LP layout optimization."""
    cap = DRegionProblem.rectangle(40, 12, thickness=4.0,
                                   material=Material(f_c=5.0), vol_frac=0.30)
    cap.add_support(5, 0, fix_x=False, fix_y=True, bearing=3.0)
    cap.add_support(20, 0, fix_x=True, fix_y=True, bearing=3.0)
    cap.add_support(35, 0, fix_x=False, fix_y=True, bearing=3.0)
    for x in (2.5, 12.5, 20, 27.5, 37.5):
        cap.add_load(x, 12, fy=-250, bearing=1.5)
    result = cap.solve(nelx=80, max_iter=60)

    m = result.model
    assert result.stable                      # a valid equilibrium load path
    # genuinely more than a triangle: many joints, both chords and a web
    assert len(m.nodes) >= 8
    assert len(m.members) >= 12
    # global equilibrium against the five 250-kip girders, with no net thrust
    ry = sum(v[1] for v in m.reactions.values())
    rx = sum(v[0] for v in m.reactions.values())
    assert ry == pytest.approx(1250.0, abs=2.0)
    assert rx == pytest.approx(0.0, abs=2.0)
    # the LP global optimum is symmetric: the two outer columns react equally
    outer = sorted(v[1] for v in m.reactions.values())[:2]
    assert outer[0] == pytest.approx(outer[1], abs=1.0)
    # a real strut-and-tie mix (top tension chord + compression fans)
    ties = [f for f in result.forces.values() if f > 1e-6]
    struts = [f for f in result.forces.values() if f < -1e-6]
    assert len(ties) >= 3 and len(struts) >= 5


def test_extraction_aci_geometry():
    """ACI 318 geometry rules: no member crosses another without a shared joint
    (every crossing is a nodal zone), and a continuous bottom chord is present."""
    from itertools import combinations
    from civilpy.structural.stm_topology.extract import _seg_intersection

    cap = DRegionProblem.rectangle(40, 12, thickness=4.0,
                                   material=Material(f_c=5.0), vol_frac=0.30)
    cap.add_support(5, 0, fix_x=False, fix_y=True, bearing=3.0)
    cap.add_support(20, 0, fix_x=True, fix_y=True, bearing=3.0)
    cap.add_support(35, 0, fix_x=False, fix_y=True, bearing=3.0)
    for x in (2.5, 12.5, 20, 27.5, 37.5):
        cap.add_load(x, 12, fy=-250, bearing=1.5)
    m = cap.solve(nelx=80, max_iter=60).model

    # no un-noded crossings among members that do not already share a joint
    segs = [(m.nodes[a], m.nodes[b], (a, b)) for a, b in m.members]
    for (p1, p2, e1), (p3, p4, e2) in combinations(segs, 2):
        if set(e1) & set(e2):
            continue
        assert _seg_intersection(p1, p2, p3, p4) is None

    # a continuous bottom chord ties the three column nodes together
    bottom = [(a, b) for a, b in m.members
              if max(m.nodes[a][1], m.nodes[b][1]) < 1.0]
    assert len(bottom) >= 2
