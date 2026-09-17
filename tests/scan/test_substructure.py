#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Substructure units from the under-deck profile, span layout, box meshes."""

import numpy as np
import pytest

from civilpy.scan import features as F
from civilpy.scan.mesh import box_mesh
from civilpy.scan.segment import ground_mask, ransac_plane
from tests.scan.conftest import TRUTH


@pytest.fixture(scope="module")
def deck_and_mask(bridge_xyz):
    top = bridge_xyz[np.abs(bridge_xyz[:, 2] - TRUTH["deck_z"]) < 0.2]
    pm = ransac_plane(top, distance=0.05, n_iter=50)
    deck = F.plane_feature(pm, top, name="deck")
    deck.role = "deck"
    gm = ground_mask(bridge_xyz, cell=1.0, max_window=60, slope=0.2, initial_threshold=0.3)
    return deck, ~gm


def test_units_and_spans(bridge_xyz, deck_and_mask):
    deck, structure = deck_and_mask
    origin, direction = F.bridge_axis(bridge_xyz, deck)
    units, info = F.substructure_from_profile(bridge_xyz, structure, deck, origin, direction)
    assert info["superstructure_depth"] == pytest.approx(TRUTH["deck_z"] - TRUTH["soffit_z"], abs=0.6)
    assert [u.role for u in units] == ["abutment", "pier", "pier", "abutment"]
    stations = [u.station for u in units]
    assert stations[1] == pytest.approx(-25, abs=1.5) and stations[2] == pytest.approx(25, abs=1.5)
    piers = [u for u in units if u.role == "pier"]
    for u in piers:
        assert u.height == pytest.approx(TRUTH["soffit_z"] - 1.0, abs=1.5)     # column from ground to soffit
        assert u.width == pytest.approx(24, abs=1.0)                            # two columns 20 ft apart, r=2
        assert u.length == pytest.approx(4.0, abs=1.0)
        assert u.corners.shape == (8, 3) and u.inliers is not None
        assert u.layer == F.LAYER_SUB_PIERS
        assert u.to_dict()["height"] == pytest.approx(u.height)
    assert units[0].layer == F.ROLE_LAYERS["abutment"]
    assert [u.name for u in units] == ["unit_00", "unit_01", "unit_02", "unit_03"]
    spans = F.span_layout(units, info["deck_station_range"])
    assert [round(sp["length"]) for sp in spans] == [50, 50, 50] or \
        all(abs(sp["length"] - 50) <= 2.0 for sp in spans)
    assert spans[0]["span"] == 1 and spans[-1]["end_station"] > spans[-1]["start_station"]
    # spans close at the deck ends when there are no abutment units
    only_piers = F.span_layout(piers, info["deck_station_range"])
    assert len(only_piers) == 3 and only_piers[0]["start_station"] == pytest.approx(-75, abs=0.5)
    assert len(F.span_layout([], (0.0, 100.0))) == 1
    # profile arrays are exposed for plotting
    assert len(info["profile_station"]) == len(info["profile_depth"]) > 10


def test_units_degenerate(bridge_xyz, deck_and_mask):
    deck, structure = deck_and_mask
    origin, direction = F.bridge_axis(bridge_xyz, deck)
    none, info = F.substructure_from_profile(bridge_xyz, np.zeros(len(bridge_xyz), bool), deck,
                                             origin, direction)
    assert none == [] and info["superstructure_depth"] is None
    # only the deck itself: no drops, so no units
    deck_only = np.abs(bridge_xyz[:, 2] - TRUTH["soffit_z"]) < 0.2
    flat, info = F.substructure_from_profile(bridge_xyz, deck_only, deck, origin, direction)
    assert flat == []
    few = F.substructure_from_profile(bridge_xyz, structure, deck, origin, direction,
                                      min_points=10 ** 6)[0]
    assert few == []


def test_box_mesh(bridge_xyz, deck_and_mask):
    deck, structure = deck_and_mask
    origin, direction = F.bridge_axis(bridge_xyz, deck)
    units, _ = F.substructure_from_profile(bridge_xyz, structure, deck, origin, direction)
    m = box_mesh(units[1])
    u = units[1]
    assert m.n_faces == 12
    expected = 2 * (u.length * u.width + u.length * u.height + u.width * u.height)
    assert m.area() == pytest.approx(expected, rel=1e-6)
    assert m.layer == F.LAYER_SUB_PIERS and m.meta["role"] == "pier"


def test_clearance_footprint(bridge_xyz, deck_and_mask):
    deck, _ = deck_and_mask
    r = np.random.default_rng(1)
    low = np.column_stack([r.uniform(120, 121, 30), r.uniform(50, 51, 30), r.uniform(0, 0.3, 30)])
    high = low + [0, 0, 6.0]                                   # a canopy ~5 ft over the approach
    pts = np.vstack([bridge_xyz, low, high])
    everywhere = F.clearance_grid(pts, cell=2.0, min_gap=4.0)
    under_deck = F.clearance_grid(pts, cell=2.0, min_gap=4.0, footprint=deck.corners)
    assert everywhere.min_clearance()["clearance"] < 6
    assert under_deck.min_clearance()["clearance"] > 25
    assert under_deck.valid.sum() < everywhere.valid.sum()


def test_merge_coplanar_and_span_clearances(bridge_xyz, deck_and_mask, rng):
    from civilpy.scan.segment import PlaneModel, fit_plane_lsq

    deck, structure = deck_and_mask
    # split the deck points into two halves → two coplanar fragments → one after merge
    on_deck = ((np.abs(bridge_xyz[:, 2] - TRUTH["deck_z"]) < 0.2) & (np.abs(bridge_xyz[:, 0]) < 75)
               & (np.abs(bridge_xyz[:, 1]) < 18))
    inl = np.nonzero(on_deck)[0]
    left = inl[bridge_xyz[inl, 0] < 0]
    right = inl[bridge_xyz[inl, 0] >= 0]
    frags = []
    for part, name in ((left, "a"), (right, "b")):
        n, d, rms = fit_plane_lsq(bridge_xyz[part])
        frags.append(F.plane_feature(PlaneModel(n, d, part, rms), bridge_xyz, name=name))
    wall_pts = bridge_xyz[np.abs(bridge_xyz[:, 0] + 75) < 0.2]
    n, d, rms = fit_plane_lsq(wall_pts)
    wall = F.plane_feature(PlaneModel(n, d, np.arange(len(wall_pts)), rms), wall_pts, name="w")
    merged = F.merge_coplanar(frags + [wall], bridge_xyz)
    assert len(merged) == 2
    big = max(merged, key=lambda p: p.area)
    assert big.extent_u == pytest.approx(TRUTH["deck_len"], abs=1.0)
    assert big.meta["merged_from"] == ["a", "b"]
    assert F.merge_coplanar([wall, wall], bridge_xyz) == [wall, wall]      # vertical: untouched
    # per-span clearance and the upper-body restriction
    origin, direction = F.bridge_axis(bridge_xyz, deck)
    units, info = F.substructure_from_profile(bridge_xyz, structure, deck, origin, direction)
    spans = F.span_layout(units, info["deck_station_range"])
    grid = F.clearance_grid(bridge_xyz, cell=2.0, min_gap=4.0, footprint=deck.corners)
    F.span_clearances(spans, grid, origin, direction)
    assert all(25 < sp["min_clearance"] < 27.5 for sp in spans)
    assert all("clearance_z_high" in sp for sp in spans)
    none_grid = grid.restrict_upper(10_000.0)
    assert not none_grid.valid.any()
    F.span_clearances(spans, none_grid, origin, direction)
    assert all(sp["min_clearance"] is None for sp in spans)
    far = F.span_layout([], (5000.0, 5100.0))
    F.span_clearances(far, grid, origin, direction)
    assert far[0]["min_clearance"] is None
