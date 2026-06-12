"""Tests for the two-span continuous (Müller-Breslau) influence lines."""

import numpy as np
import pytest

from civilpy.structural.influence_lines import InfluenceLine


def test_middle_reaction_il_anchors():
    il = InfluenceLine.two_span_reaction((40.0, 40.0), support="B")
    assert il.eta(40.0) == pytest.approx(1.0)     # load on the support
    assert il.eta(0.0) == pytest.approx(0.0)
    assert il.eta(80.0) == pytest.approx(0.0)
    # ordinates exceed the simple-span tributary peak near midspans
    assert il.eta(20.0) > 0.5


def test_reactions_satisfy_statics_everywhere():
    spans = (35.0, 50.0)
    il_a = InfluenceLine.two_span_reaction(spans, "A")
    il_b = InfluenceLine.two_span_reaction(spans, "B")
    il_c = InfluenceLine.two_span_reaction(spans, "C")
    for u in np.linspace(0.0, 85.0, 18):
        assert il_a.eta(u) + il_b.eta(u) + il_c.eta(u) == pytest.approx(1.0)
        # moments about A: R_B*L1 + R_C*L - 1*u = 0
        m_a = il_b.eta(u) * 35.0 + il_c.eta(u) * 85.0 - u
        assert m_a == pytest.approx(0.0, abs=1e-9)


def test_support_moment_matches_three_moment_equation():
    span = 30.0
    il = InfluenceLine.two_span_moment((span, span), section=span)
    # classic result for equal spans: M_B = -a (L^2 - a^2) / (4 L^2)
    for a in (5.0, 12.0, 15.0, 22.5):
        expected = -a * (span**2 - a**2) / (4.0 * span**2)
        assert il.eta(a) == pytest.approx(expected, rel=1e-6)
    # symmetric: load in span 2 mirrors span 1
    assert il.eta(span + 7.0) == pytest.approx(il.eta(span - 7.0))
    # negative everywhere (the classic two-span hump)
    x, y = il.ordinates(501)
    assert (y <= 1e-9).all()


def test_midspan_moment_il_sign_regions():
    il = InfluenceLine.two_span_moment((40.0, 40.0), section=20.0)
    assert il.eta(20.0) > 0.0           # load at the section: positive
    assert il.eta(60.0) < 0.0           # load in the far span: relief
    # continuity: smaller positive peak than the 10.0 of a simple span
    assert il.eta(20.0) < 10.0


def test_shear_il_jumps_at_section():
    il = InfluenceLine.two_span_shear((40.0, 40.0), section=10.0)
    assert il.eta(10.0 - 1e-6) - il.eta(10.0 + 1e-6) == pytest.approx(-1.0)


def test_uniform_load_on_two_span_negative_moment():
    spans = (40.0, 40.0)
    il = InfluenceLine.two_span_moment(spans, section=40.0)
    # both spans loaded: M_B = -w L^2 / 8 for equal spans
    w = 1.0
    effect = il.uniform_load_effect(w, positive_only=False)
    assert effect == pytest.approx(-w * 40.0**2 / 8.0, rel=1e-4)
