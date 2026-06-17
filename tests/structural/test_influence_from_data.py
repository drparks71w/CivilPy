"""Tests for building influence lines from sampled / MIDAS data and running
permit trucks against them (influence_line_from_ordinates / _from_midas)."""

import numpy as np
import pytest

from civilpy.structural.influence_lines import (
    InfluenceLine,
    influence_line_from_ordinates,
    influence_line_from_midas,
)


class TestFromOrdinates:
    def test_reproduces_simple_span_moment(self):
        # Sample the analytical midspan-moment line, rebuild it from samples,
        # and confirm the reconstruction matches (peak L/4 at midspan).
        ref = InfluenceLine.moment(span=20.0, section=10.0)
        x, eta = ref.ordinates(n=201)
        il = influence_line_from_ordinates(x, eta)
        assert il.length == pytest.approx(20.0)
        assert il.eta(10.0) == pytest.approx(5.0, abs=1e-3)
        assert il.eta(5.0) == pytest.approx(ref.eta(5.0), abs=1e-2)

    def test_off_span_positions_are_zero(self):
        il = influence_line_from_ordinates([0.0, 10.0, 20.0], [0.0, 5.0, 0.0])
        assert il.eta(-5.0) == 0.0
        assert il.eta(25.0) == 0.0

    def test_explicit_length_and_label(self):
        il = influence_line_from_ordinates([0, 5, 10], [0, 1, 0],
                                           length=12.0, label="R_B")
        assert il.length == 12.0
        assert il.label == "R_B"

    def test_unsorted_input_is_sorted(self):
        il = influence_line_from_ordinates([20.0, 0.0, 10.0], [0.0, 0.0, 5.0])
        assert il.eta(10.0) == pytest.approx(5.0)

    def test_too_few_samples_raises(self):
        with pytest.raises(ValueError):
            influence_line_from_ordinates([0.0], [0.0])

    def test_mismatched_lengths_raise(self):
        with pytest.raises(ValueError):
            influence_line_from_ordinates([0.0, 1.0, 2.0], [0.0, 1.0])

    def test_permit_truck_against_reconstructed_line(self):
        # A reconstructed midspan-moment line should rate a 2-axle permit truck
        # the same as the analytical line (within interpolation tolerance).
        ref = InfluenceLine.moment(span=100.0, section=50.0)
        x, eta = ref.ordinates(n=2001)
        il = influence_line_from_ordinates(x, eta)
        loads, spacing = [30.0, 30.0], [0.0, 14.0]
        assert (il.maximize_axle_train(loads, spacing).value
                == pytest.approx(ref.maximize_axle_train(loads, spacing).value,
                                 rel=1e-3))


class _FakeMidas:
    """Returns a /post/TABLE-shaped BEAMFORCE response built from a position->
    moment map keyed by load-case name."""

    def __init__(self, element, case_moment, part="Part I"):
        self.element, self.case_moment, self.part = element, case_moment, part
        self.calls = []

    def beam_forces(self, elem_ids, load_case_names, unit=None):
        self.calls.append((list(elem_ids), list(load_case_names)))
        data = []
        for name in load_case_names:
            data.append([str(self.element), name, self.part,
                         f"{self.case_moment.get(name, 0.0)}"])
        return {"BeamForce": {"HEAD": ["Elem", "Load", "Part", "Moment-y"],
                              "DATA": data}}


class TestFromMidas:
    def _cases(self):
        # Triangular influence line for midspan moment of a 20-ft span: peak 5.0.
        positions = [0.0, 5.0, 10.0, 15.0, 20.0]
        etas = [0.0, 2.5, 5.0, 2.5, 0.0]
        cases = [(p, f"UNIT_{i}") for i, p in enumerate(positions)]
        case_moment = {name: e for (_, name), e in zip(cases, etas)}
        return cases, case_moment

    def test_assembles_line_from_unit_cases(self):
        cases, case_moment = self._cases()
        midas = _FakeMidas(element=42, case_moment=case_moment)
        il = influence_line_from_midas(midas, 42, cases)
        assert il.eta(10.0) == pytest.approx(5.0)
        assert il.length == pytest.approx(20.0)
        # one batched read for the single element across all cases
        assert midas.calls == [([42], [n for _, n in cases])]
        assert "elem 42 Moment-y" in il.label

    def test_runs_permit_truck(self):
        cases, case_moment = self._cases()
        midas = _FakeMidas(element=42, case_moment=case_moment)
        il = influence_line_from_midas(midas, 42, cases)
        # single 10-kip axle parked at the peak -> 10 * 5.0
        assert il.maximize_axle_train([10.0], [0.0]).value == pytest.approx(50.0)

    def test_ignores_other_elements_and_parts(self):
        cases, case_moment = self._cases()

        class MixedMidas(_FakeMidas):
            def beam_forces(self, elem_ids, load_case_names, unit=None):
                base = super().beam_forces(elem_ids, load_case_names, unit)
                # inject noise rows: wrong element + wrong part
                base["BeamForce"]["DATA"] += [
                    ["999", load_case_names[0], "Part I", "9999.0"],
                    [str(self.element), load_case_names[0], "Part J", "8888.0"],
                ]
                return base

        midas = MixedMidas(element=42, case_moment=case_moment)
        il = influence_line_from_midas(midas, 42, cases, part="Part I")
        assert il.eta(10.0) == pytest.approx(5.0)   # noise rows excluded

    def test_too_few_resolved_raises(self):
        cases, case_moment = self._cases()
        # Response only carries a different element, so nothing resolves for 42.
        midas = _FakeMidas(element=777, case_moment=case_moment)
        with pytest.raises(ValueError, match="resolved"):
            influence_line_from_midas(midas, 42, cases)
