#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""Pre-solve diagnostics and member-type classification for
:class:`civilpy.structural.strut_and_tie.StrutAndTieModel` (no rhino3dm dep)."""

import pytest

from civilpy.structural.strut_and_tie import StrutAndTieModel


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


class TestDiagnose:
    def test_clean_model_has_no_problems(self):
        assert _example_1().diagnose() == []

    def test_names_dangling_node(self):
        m = _example_1()
        m.add_node("Z", 50, 50)            # connected to nothing
        problems = m.diagnose()
        assert any("Z" in p and "not connected" in p for p in problems)

    def test_flags_load_with_no_load_path(self):
        m = StrutAndTieModel()
        m.add_node("A", 0, 0)
        m.add_node("B", 1, 0)
        m.add_node("P", 5, 5)
        m.add_member("A", "B")
        m.add_load("P", fy=-10)
        assert any("P" in p and "load path" in p for p in m.diagnose())

    def test_no_supports_is_a_mechanism(self):
        m = StrutAndTieModel()
        m.add_node("A", 0, 0)
        m.add_node("B", 1, 0)
        m.add_member("A", "B")
        assert any("no supports" in p for p in m.diagnose())

    def test_under_constrained_reported(self):
        m = StrutAndTieModel()
        m.add_node("A", 0, 0)
        m.add_node("B", 1, 0)
        m.add_member("A", "B")
        m.add_support("A", fix_x=True)     # 1 member + 1 reaction < 4 eqs
        assert any("under-constrained" in p for p in m.diagnose())

    def test_indeterminate_reported_as_solvable_by_dsm(self):
        # internally redundant: a square braced by BOTH diagonals (one is the
        # redundant member) with a pin + roller -> degree 1, but solvable by DSM
        m = StrutAndTieModel()
        for label, (x, y) in {"A": (0, 0), "B": (4, 0),
                              "C": (4, 4), "D": (0, 4)}.items():
            m.add_node(label, x, y)
        for a, b in [("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"),
                     ("A", "C"), ("B", "D")]:
            m.add_member(a, b)
        m.add_support("A", fix_x=True, fix_y=True)
        m.add_support("B", fix_y=True)
        m.add_load("C", fy=-10)
        assert m.degree_of_indeterminacy() == 1
        problems = m.diagnose()
        assert any("statically indeterminate" in p for p in problems)
        # genuinely solvable now (DSM auto-dispatch), not a hard failure
        m.solve()
        assert m.forces is not None and len(m.forces) == 6

    def test_solve_error_includes_named_diagnostics(self):
        m = StrutAndTieModel()
        m.add_node("A", 0, 0)
        m.add_node("B", 1, 0)
        m.add_member("A", "B")
        m.add_support("A", fix_x=True)
        with pytest.raises(ValueError, match="under-constrained"):
            m.solve()


class TestClassify:
    def test_forced_override_wins_before_solve(self):
        m = _example_1()
        m.member_types[("A", "B")] = "strut"
        assert m.classify(("A", "B")) == "strut"   # even un-solved

    def test_auto_classifies_by_sign(self):
        m = _example_1()
        m.solve()
        # bottom tie B-C is tension -> tie; a diagonal in compression -> strut
        assert m.classify(("B", "C")) == "tie"
        strut = next(mem for mem, f in m.forces.items() if f < -1e-9)
        assert m.classify(strut) == "strut"

    def test_classify_none_before_solve_when_auto(self):
        assert _example_1().classify(("B", "C")) is None
