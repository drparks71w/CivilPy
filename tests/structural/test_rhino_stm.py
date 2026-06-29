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

"""Round-trip and reader tests for the Rhino <-> strut-and-tie bridge.

Skipped entirely when the optional ``rhino3dm`` dependency is absent.
"""

import pytest

pytest.importorskip("rhino3dm")

import rhino3dm  # noqa: E402

from civilpy.structural import rhino_stm  # noqa: E402
from civilpy.structural.strut_and_tie import StrutAndTieModel  # noqa: E402


def _example_1():
    """FHWA-NHI-17-071 Design Example 1 (deep beam), drawn in feet."""
    m = StrutAndTieModel()
    coords = {"A": (0, 0), "B": (4.5, 0), "C": (27, 0),
              "D": (4.5, 16 / 3), "E": (9, 16 / 3), "F": (18, 16 / 3)}
    for label, (x, y) in coords.items():
        m.add_node(label, x, y)
    m.add_support("A", fix_x=True, fix_y=True)
    m.add_support("C", fix_y=True)
    m.add_load("E", fy=-600)
    m.add_load("F", fy=-600)
    for a, b in [("A", "B"), ("A", "D"), ("B", "C"), ("B", "D"), ("D", "E"),
                 ("B", "E"), ("E", "F"), ("C", "F"), ("C", "E")]:
        m.add_member(a, b)
    return m


class TestRoundTrip:
    def test_forces_survive_round_trip(self, tmp_path):
        src = _example_1()
        src.solve()
        path = tmp_path / "ex1.3dm"
        src.to_3dm(path)

        back = StrutAndTieModel.from_3dm(path)
        back.solve()

        # auto-labeling reproduces the elevation order A..F
        assert list(back.nodes) == ["A", "B", "C", "D", "E", "F"]
        for member, force in src.forces.items():
            assert back.forces[member] == pytest.approx(force, abs=1e-6)

    def test_matches_published_values(self, tmp_path):
        path = tmp_path / "ex1.3dm"
        _example_1().to_3dm(path)
        m = StrutAndTieModel.from_3dm(path)
        m.solve()
        # bottom tie and vertical tie from the FHWA worked example
        assert m.forces[("B", "C")] == pytest.approx(1012.5, abs=0.1)
        assert m.forces[("B", "D")] == pytest.approx(600.0, abs=0.1)

    def test_supports_and_loads_survive(self, tmp_path):
        path = tmp_path / "ex1.3dm"
        _example_1().to_3dm(path)
        m = StrutAndTieModel.from_3dm(path)
        assert m.supports["A"] == (True, True)   # pin
        assert m.supports["C"] == (False, True)  # vertical roller
        assert m.loads["E"] == pytest.approx([0.0, -600.0])
        assert m.loads["F"] == pytest.approx([0.0, -600.0])


class TestTemplate:
    def test_build_template_has_layers(self, tmp_path):
        path = tmp_path / "tpl.3dm"
        rhino_stm.build_template(path)
        f = rhino3dm.File3dm.Read(str(path))
        names = {layer.FullPath for layer in f.Layers}
        assert {rhino_stm.LAYER_MEMBERS, rhino_stm.LAYER_SUPPORTS,
                rhino_stm.LAYER_LOADS, rhino_stm.LAYER_RESULTS} <= names

    def test_results_writer_runs(self, tmp_path):
        m = _example_1()
        m.solve()
        path = tmp_path / "res.3dm"
        rhino_stm.results_to_3dm(m, path)
        f = rhino3dm.File3dm.Read(str(path))
        assert sum(1 for _ in f.Objects) > 0


class TestReader:
    def test_untagged_curves_fall_back_to_members(self, tmp_path):
        """A plain drawing (untagged lines) imports as members."""
        f = rhino3dm.File3dm()
        f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Feet
        # a simple triangle truss in the XZ plane
        pts = {"A": (0, 0, 0), "B": (8, 0, 0), "C": (4, 0, 4)}
        for a, b in [("A", "B"), ("B", "C"), ("A", "C")]:
            f.Objects.AddLine(rhino3dm.Point3d(*pts[a]),
                              rhino3dm.Point3d(*pts[b]))
        path = tmp_path / "raw.3dm"
        f.Write(str(path), 7)

        m = rhino_stm.model_from_3dm(path)
        assert len(m.nodes) == 3
        assert len(m.members) == 3

    def test_plane_autodetect_xz(self, tmp_path):
        path = tmp_path / "ex1.3dm"
        _example_1().to_3dm(path, plane="XZ")
        m = rhino_stm.model_from_3dm(path, plane="auto")
        # the model was drawn in XZ, so node y-coords recover the heights
        assert max(y for _, y in m.nodes.values()) == pytest.approx(16 / 3)

    def test_fix_overrides_from_user_text(self, tmp_path):
        """An explicit stm.fix_x override on a support point is honored."""
        f = rhino3dm.File3dm()
        f.Settings.ModelUnitSystem = rhino3dm.UnitSystem.Feet
        for a, b in [((0, 0, 0), (8, 0, 0)), ((8, 0, 0), (4, 0, 4)),
                     ((0, 0, 0), (4, 0, 4))]:
            f.Objects.AddLine(rhino3dm.Point3d(*a), rhino3dm.Point3d(*b))
        attr = rhino3dm.ObjectAttributes()
        attr.SetUserString("stm.kind", "support")
        attr.SetUserString("stm.fix_x", "true")
        attr.SetUserString("stm.fix_y", "true")
        f.Objects.AddPoint(rhino3dm.Point3d(0, 0, 0), attr)
        path = tmp_path / "sup.3dm"
        f.Write(str(path), 7)

        m = rhino_stm.model_from_3dm(path)
        # the node nearest (0,0) carries the pin
        pinned = [n for n, s in m.supports.items() if s == (True, True)]
        assert len(pinned) == 1
