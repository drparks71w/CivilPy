#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Moving-load shear/moment envelopes on continuous beams, cross-validated
against the closed-form influence-line path and textbook constants."""

import numpy as np
import pytest

from civilpy.structural.aashto.vehicles import RATING_VEHICLES
from civilpy.structural.continuous_beam import (
    ContinuousBeam, moving_load_envelope, unit_response_matrices,
)
from civilpy.structural.influence_lines import InfluenceLine


class TestSimpleSpan:
    def test_hs20_absolute_max_moment_100ft(self):
        # Textbook HS-20 absolute maximum: M = 18L + 392/L - 280 (L > 33.8 ft)
        env = moving_load_envelope(ContinuousBeam([0.0, 100.0]),
                                   *RATING_VEHICLES["HS20"].train())
        m = env.max_positive_moment()
        assert m.value == pytest.approx(18 * 100 + 392 / 100 - 280, rel=1e-3)
        # peak under the middle axle near L/2 - 2.33 ft
        assert m.station == pytest.approx(47.667, abs=0.5)

    def test_matches_influence_line_at_midspan(self):
        # Independent path: closed-form IL + axle stepping vs stiffness solve
        env = moving_load_envelope(ContinuousBeam([0.0, 100.0]),
                                   *RATING_VEHICLES["Type 3S2"].train())
        il = InfluenceLine.moment(span=100.0, section=50.0)
        peak = il.maximize_axle_train(*RATING_VEHICLES["Type 3S2"].train())
        k = int(np.argmin(np.abs(env.stations - 50.0)))
        assert env.moment_max[k] == pytest.approx(peak.value, rel=1e-6)

    def test_shear_matches_influence_line(self):
        env = moving_load_envelope(ContinuousBeam([0.0, 80.0]),
                                   *RATING_VEHICLES["Type 3"].train())
        il = InfluenceLine.shear(span=80.0, section=0.5)
        peak = il.maximize_axle_train(*RATING_VEHICLES["Type 3"].train())
        k = int(np.argmin(np.abs(env.stations - 0.5)))
        assert env.shear_max[k] == pytest.approx(peak.value, rel=1e-6)

    def test_reversal_matters_for_asymmetric_truck(self):
        # Type 3 is front-light; at an off-center section one direction governs
        beam = ContinuousBeam([0.0, 60.0])
        train = RATING_VEHICLES["Type 3"].train()
        both = moving_load_envelope(beam, *train)
        fwd = moving_load_envelope(beam, *train, both_directions=False)
        assert np.all(both.moment_max >= fwd.moment_max - 1e-9)
        assert np.any(both.moment_max > fwd.moment_max + 1e-6)

    def test_train_longer_than_span(self):
        # 54-ft Type 3-3 on a 40-ft span: only partial axle groups fit
        env = moving_load_envelope(ContinuousBeam([0.0, 40.0]),
                                   *RATING_VEHICLES["Type 3-3"].train())
        m = env.max_positive_moment()
        assert 0.0 < m.value < 80.0 * 40.0 / 4.0   # < GVW*L/4 bound
        assert np.all(env.moment_min >= -1e-9)      # nothing hogs a simple span

    def test_lane_load_only(self):
        # 0.64 klf on a 100-ft simple span: M = wL^2/8 = 800 at midspan
        env = moving_load_envelope(ContinuousBeam([0.0, 100.0]),
                                   [0.0], [0.0], lane_klf=0.64)
        k = int(np.argmin(np.abs(env.stations - 50.0)))
        assert env.moment_max[k] == pytest.approx(800.0, abs=0.5)


class TestContinuous:
    def test_negative_moment_matches_two_span_influence_line(self):
        # Müller-Breslau closed form vs the numeric envelope, 60+80 ft
        beam = ContinuousBeam([0.0, 60.0, 140.0])
        train = RATING_VEHICLES["Type 3S2"].train()
        env = moving_load_envelope(beam, *train)
        il = InfluenceLine.two_span_moment((60.0, 80.0), section=60.0)
        peak = il.maximize_axle_train(*train, sign=-1.0)
        k = int(np.argmin(np.abs(env.stations - 60.0)))
        assert env.moment_min[k] == pytest.approx(peak.value, rel=5e-3)

    def test_positive_moment_matches_two_span_influence_line(self):
        beam = ContinuousBeam([0.0, 60.0, 140.0])
        train = RATING_VEHICLES["Type 3"].train()
        env = moving_load_envelope(beam, *train)
        il = InfluenceLine.two_span_moment((60.0, 80.0), section=30.0)
        peak = il.maximize_axle_train(*train)
        k = int(np.argmin(np.abs(env.stations - 30.0)))
        assert env.moment_max[k] == pytest.approx(peak.value, rel=5e-3)

    def test_patterned_lane_load(self):
        # For M at 25 ft of a 50+50, the adverse lane pattern loads span 1
        # only; the envelope's per-station IL clipping must reproduce it.
        beam = ContinuousBeam([0.0, 50.0, 100.0])
        env = moving_load_envelope(beam, [0.0], [0.0], lane_klf=0.64)
        exact = ContinuousBeam([0.0, 50.0, 100.0]) \
            .add_udl(0.64, 0.0, 50.0).moment_at(25.0)
        k = int(np.argmin(np.abs(env.stations - 25.0)))
        assert env.moment_max[k] == pytest.approx(exact, abs=0.5)

    def test_three_span_oril_model(self):
        # The paper's continuous sub-model: r*L + L + r*L with r = 1.2
        r, span = 1.2, 100.0
        beam = ContinuousBeam([0.0, r * span, (1 + r) * span,
                               (1 + 2 * r) * span])
        env = moving_load_envelope(beam, *RATING_VEHICLES["Type 3-3"].train())
        m_neg = env.max_negative_moment()
        assert m_neg.value < 0.0
        # hogging peak sits at an interior support
        assert min(abs(m_neg.station - s) for s in beam.supports[1:3]) < 0.26
        v = env.max_shear()
        assert min(abs(v.station - s) for s in beam.supports) < 3.0

    def test_unit_columns_are_influence_lines(self):
        # Column k of the moment matrix = IL of M at station k (moment_at path)
        beam = ContinuousBeam([0.0, 60.0, 140.0])
        xs = np.linspace(0.0, 140.0, 141)
        _, m_unit = unit_response_matrices(beam, xs)
        il = beam.moment_influence_line(60.0, n=141)
        k = int(np.argmin(np.abs(xs - 60.0)))
        assert m_unit[:, k] == pytest.approx(il.eta(xs), abs=1e-9)
