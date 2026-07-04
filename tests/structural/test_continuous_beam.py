#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Continuous-beam analysis (offline line-girder envelopes).  Validated against
closed-form results; the influence-line path feeds the existing HL-93 machinery."""

import pytest

from civilpy.structural.continuous_beam import ContinuousBeam


class TestClosedForm:
    def test_single_span_udl(self):
        b = ContinuousBeam([0, 20]).add_udl(2.0)
        assert b.reactions() == pytest.approx([20.0, 20.0])
        assert b.moment_at(10) == pytest.approx(100.0)   # wL^2/8

    def test_single_span_point_load_at_mid(self):
        b = ContinuousBeam([0, 20]).add_point(10.0, 10.0)
        assert b.reactions() == pytest.approx([5.0, 5.0])
        assert b.moment_at(10) == pytest.approx(50.0)     # PL/4

    def test_two_equal_spans_udl(self):
        # classic: interior reaction 1.25wL, ends 3wL/8, interior M = -wL^2/8
        b = ContinuousBeam([0, 20, 40]).add_udl(2.0)
        assert b.reactions() == pytest.approx([15.0, 50.0, 15.0])
        assert b.moment_at(20) == pytest.approx(-100.0)
        assert b.moment_at(10) == pytest.approx(50.0)

    def test_reactions_balance_total_load(self):
        b = ContinuousBeam([0, 60, 140, 200]).add_udl(1.5)
        assert sum(b.reactions()) == pytest.approx(1.5 * 200.0)

    def test_three_span_symmetry_and_contraflexure(self):
        b = ContinuousBeam([0, 60, 140, 200]).add_udl(1.0)
        r = b.reactions()
        assert r[0] == pytest.approx(r[3])       # symmetric
        assert r[1] == pytest.approx(r[2])
        assert b.moment_at(60) == pytest.approx(b.moment_at(140))  # pier moments
        assert b.moment_at(60) < 0               # hogging over the pier
        assert b.moment_at(100) > 0              # sagging mid interior span
        # a contraflexure (sign change) exists between mid-span and the pier
        assert b.moment_at(80) * b.moment_at(60) < 0


class TestInfluenceLineAndHL93:
    def test_moment_influence_line_hl93_envelope(self):
        b = ContinuousBeam([0, 60, 140, 200])
        il = b.moment_influence_line(100.0)      # mid of interior span
        # HL-93 gives a nonzero positive (and negative) live-load moment there
        pos = il.hl93_effect()
        assert pos != 0.0

    def test_influence_line_ordinate_zero_at_supports(self):
        b = ContinuousBeam([0, 60, 140, 200])
        il = b.moment_influence_line(100.0)
        # a unit load sitting on a support produces no moment at the section
        assert il.eta(0.0) == pytest.approx(0.0, abs=1e-6)
        assert il.eta(200.0) == pytest.approx(0.0, abs=1e-6)
