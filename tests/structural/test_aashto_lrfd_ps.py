#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Hand-checked values for the prestressed concrete LRFD checks.

Geometry loosely follows a typical Ohio precast I-beam with a composite
deck: 30 x 0.6" low-relaxation strands (Aps = 6.51 in^2 using 0.217 in^2
strands ~ generic), 270 ksi, composite slab f'c = 4 ksi.
"""

import math

import pytest

from civilpy.structural.aashto import lrfd


# Shared rectangular-behavior case: Aps=4.59 (30 x 0.153), dp=36, b=48, f'c=4
RECT = dict(a_ps=4.59, f_pu=270.0, d_p=36.0, f_c=4.0, b=48.0)


class TestStrandStress:
    def test_rectangular_neutral_axis(self):
        # c = Aps*fpu / (0.85*f'c*beta1*b + k*Aps*fpu/dp)
        #   = 1239.3 / (0.85*4*0.85*48 + 0.28*1239.3/36)
        #   = 1239.3 / (138.72 + 9.639) = 8.353 in
        r = lrfd.ps_strand_stress_at_nominal(**RECT)
        c = 4.59 * 270.0 / (0.85 * 4.0 * 0.85 * 48.0 + 0.28 * 4.59 * 270.0 / 36.0)
        assert r.details["c"] == pytest.approx(c, rel=1e-6)
        assert r.details["behavior"] == "rectangular"

    def test_fps_from_c(self):
        r = lrfd.ps_strand_stress_at_nominal(**RECT)
        c = r.details["c"]
        assert r.capacity == pytest.approx(270.0 * (1.0 - 0.28 * c / 36.0))
        # fps for a tension-controlled section should be near fpu
        assert 245.0 < r.capacity < 270.0

    def test_flanged_behavior_when_na_below_flange(self):
        # Thin 3" flange on a 6" web forces the neutral axis below the flange
        r = lrfd.ps_strand_stress_at_nominal(**RECT, b_w=6.0, h_f=3.0)
        assert r.details["behavior"] == "flanged"
        rect_c = lrfd.ps_strand_stress_at_nominal(**RECT).details["c"]
        assert r.details["c"] > rect_c  # web-only compression needs deeper NA

    def test_stress_relieved_k(self):
        low = lrfd.ps_strand_stress_at_nominal(**RECT)
        sr = lrfd.ps_strand_stress_at_nominal(**RECT, k=lrfd.prestressed.K_STRESS_RELIEVED)
        assert sr.capacity < low.capacity  # larger k -> lower fps


class TestPSFlexure:
    def test_rectangular_mn(self):
        r = lrfd.ps_flexural_resistance(**RECT)
        c = r.details["c"]
        f_ps = r.details["fps"]
        a = 0.85 * c
        assert r.capacity == pytest.approx(4.59 * f_ps * (36.0 - a / 2.0), rel=1e-6)
        # ~3,100 kip-ft ballpark for this section
        assert 30000.0 < r.capacity < 45000.0

    def test_tension_controlled_phi_is_one(self):
        r = lrfd.ps_flexural_resistance(**RECT)
        assert r.details["tension_controlled"]
        assert r.phi == pytest.approx(1.0)

    def test_demand_ratio(self):
        r = lrfd.ps_flexural_resistance(**RECT, m_u=30000.0)
        assert r.ratio == pytest.approx(r.capacity / 30000.0)

    def test_flanged_mn_adds_overhang_term(self):
        r = lrfd.ps_flexural_resistance(**RECT, b_w=6.0, h_f=3.0)
        assert r.details["behavior"] == "flanged"
        # capacity still positive and below the rectangular idealization
        rect = lrfd.ps_flexural_resistance(**RECT)
        assert 0 < r.capacity < rect.capacity

    def test_mild_steel_increases_capacity(self):
        base = lrfd.ps_flexural_resistance(**RECT)
        with_mild = lrfd.ps_flexural_resistance(**RECT, a_s=2.0, d_s=38.0)
        assert with_mild.capacity > base.capacity


class TestStressLimits:
    def test_transfer_compression(self):
        r = lrfd.ps_transfer_compression_check(f_ci=5.0, stress=3.0)
        assert r.capacity == pytest.approx(0.65 * 5.0)
        assert r.ok

    def test_transfer_tension_without_bonded_reinf_caps_at_02(self):
        # 0.0948*sqrt(5) = 0.212 > 0.2 -> capped
        r = lrfd.ps_transfer_tension_check(f_ci=5.0)
        assert r.capacity == pytest.approx(0.2)

    def test_transfer_tension_with_bonded_reinf(self):
        r = lrfd.ps_transfer_tension_check(f_ci=5.0, bonded_reinforcement=True)
        assert r.capacity == pytest.approx(0.24 * math.sqrt(5.0))

    def test_service_compression_governing_case(self):
        # permanent: 0.45*7 = 3.15 vs 2.8 -> margin 1.125
        # total:     0.60*7 = 4.20 vs 4.0 -> margin 1.05 (governs)
        r = lrfd.ps_service_compression_check(
            f_c=7.0, stress_permanent=2.8, stress_total=4.0
        )
        assert r.details["governing"] == "total"
        assert r.capacity == pytest.approx(4.2)
        assert r.ok

    def test_service_tension_normal_exposure(self):
        r = lrfd.ps_service_tension_check(f_c=7.0, stress=0.4)
        assert r.capacity == pytest.approx(min(0.19 * math.sqrt(7.0), 0.6))
        assert r.ok

    def test_service_tension_severe_corrosion(self):
        r = lrfd.ps_service_tension_check(f_c=7.0, severe_corrosion=True)
        assert r.capacity == pytest.approx(min(0.0948 * math.sqrt(7.0), 0.3))


class TestLosses:
    def test_elastic_shortening(self):
        # Ep/Ect * fcgp = 28500/4500 * 1.2 = 7.6 ksi
        r = lrfd.ps_elastic_shortening_loss(f_cgp=1.2, e_ct=4500.0)
        assert r.capacity == pytest.approx(28500.0 / 4500.0 * 1.2)

    def test_approximate_longterm_at_reference_conditions(self):
        # H=70 -> gamma_h = 1.0; f'ci = 4 -> gamma_st = 1.0
        # loss = 10*fpi*Aps/Ag + 12 + 2.4
        r = lrfd.ps_approximate_longterm_loss(
            f_pi=202.5, a_ps=4.59, a_g=789.0, f_ci=4.0, humidity_pct=70.0
        )
        creep = 10.0 * 202.5 * 4.59 / 789.0
        assert r.details["gamma_h"] == pytest.approx(1.0)
        assert r.details["gamma_st"] == pytest.approx(1.0)
        assert r.capacity == pytest.approx(creep + 12.0 + 2.4)

    def test_humidity_reduces_loss(self):
        dry = lrfd.ps_approximate_longterm_loss(
            f_pi=202.5, a_ps=4.59, a_g=789.0, f_ci=4.0, humidity_pct=40.0
        )
        humid = lrfd.ps_approximate_longterm_loss(
            f_pi=202.5, a_ps=4.59, a_g=789.0, f_ci=4.0, humidity_pct=90.0
        )
        assert dry.capacity > humid.capacity


class TestRegistry:
    def test_ps_articles_registered(self):
        for num in ("5.6.3.1.1", "5.6.3.2.2", "5.9.2.3.1a", "5.9.2.3.1b",
                    "5.9.2.3.2a", "5.9.2.3.2b", "5.9.3.2.3a", "5.9.3.3"):
            assert num in lrfd.ARTICLES

    def test_strand_pattern_design_loop(self):
        """Size a strand pattern by looping candidate strand counts."""
        m_u = 28000.0  # kip-in
        counts = range(20, 42, 2)
        passing = [
            n for n in counts
            if lrfd.ps_flexural_resistance(
                a_ps=n * 0.153, f_pu=270.0, d_p=36.0, f_c=4.0, b=48.0, m_u=m_u
            ).ok
        ]
        assert passing
        assert min(passing) > 20  # demand high enough to reject the lightest


class TestUnbondedStrandStress:
    def test_rectangular_fixed_point_hand_calc(self):
        # le = 2*480/(2+0) = 480; solve fps = 150 + 900*(20 - c)/480 with
        # c = Aps*fps/(0.85*4? ...) hand: f'c=5 -> beta1=0.80,
        # c = fps/(0.85*5*0.80*12) = fps/40.8
        # fps*(1 + 1.875/40.8) = 150 + 37.5 -> fps = 179.26, c = 4.394
        r = lrfd.ps_strand_stress_unbonded(
            a_ps=1.0, f_pe=150.0, d_p=20.0, f_c=5.0, b=12.0,
            l_i=480.0, f_py=243.0)
        assert r.capacity == pytest.approx(179.26, abs=0.05)
        assert r.details["c"] == pytest.approx(4.394, abs=0.01)
        assert r.details["le"] == pytest.approx(480.0)
        assert r.details["behavior"] == "rectangular"
        assert not r.details["capped_at_fpy"]

    def test_support_hinges_shorten_le(self):
        # Ns = 2 halves le, raising fps
        r0 = lrfd.ps_strand_stress_unbonded(
            a_ps=1.0, f_pe=150.0, d_p=20.0, f_c=5.0, b=12.0,
            l_i=480.0, f_py=243.0)
        r2 = lrfd.ps_strand_stress_unbonded(
            a_ps=1.0, f_pe=150.0, d_p=20.0, f_c=5.0, b=12.0,
            l_i=480.0, f_py=243.0, n_s=2)
        assert r2.details["le"] == pytest.approx(240.0)
        assert r2.capacity > r0.capacity

    def test_caps_at_fpy(self):
        # very short tendon -> huge strain concentration -> fpy governs
        r = lrfd.ps_strand_stress_unbonded(
            a_ps=1.0, f_pe=150.0, d_p=20.0, f_c=5.0, b=12.0,
            l_i=60.0, f_py=243.0)
        assert r.capacity == 243.0
        assert r.details["capped_at_fpy"]

    def test_far_below_the_bonded_value(self):
        # same section bonded vs unbonded: the bonded strand approaches
        # fpu while the unbonded one stays near fpe
        bonded = lrfd.ps_strand_stress_at_nominal(
            a_ps=1.0, f_pu=270.0, d_p=20.0, f_c=5.0, b=12.0)
        unbonded = lrfd.ps_strand_stress_unbonded(
            a_ps=1.0, f_pe=150.0, d_p=20.0, f_c=5.0, b=12.0,
            l_i=480.0, f_py=243.0)
        assert unbonded.capacity < bonded.capacity - 50.0


class TestPrestressedMinimumReinforcement:
    def test_composite_prestressed_mcr_hand_calc(self):
        # 5.6.3.3-1 with all terms: fr = 0.24*sqrt(7) = 0.635 ksi,
        # gamma = 1.6 / 1.1 / 1.0 (prestressed), Sc = 6403, Snc = 4945,
        # f_cpe = 1.2 ksi, Mdnc = 6000 kip-in:
        # Mcr = 1.0*[(1.6*0.635 + 1.1*1.2)*6403 - 6000*(6403/4945 - 1)]
        fr = 0.24 * math.sqrt(7.0)
        expect = ((1.6 * fr + 1.1 * 1.2) * 6403.0
                  - 6000.0 * (6403.0 / 4945.0 - 1.0))
        r = lrfd.rc_minimum_reinforcement(
            m_n=20000.0, phi=1.0, f_c=7.0, s_c=6403.0,
            gamma_3=1.0, f_cpe=1.2, m_dnc=6000.0, s_nc=4945.0)
        assert r.details["Mcr"] == pytest.approx(expect)

    def test_defaults_reproduce_the_nonprestressed_form(self):
        # no prestress/composite args -> gamma_3*gamma_1*fr*Sc as before
        r = lrfd.rc_minimum_reinforcement(m_n=1000.0, phi=0.9, f_c=4.0,
                                          s_c=1152.0)
        assert r.details["Mcr"] == pytest.approx(0.67 * 1.6 * 0.48 * 1152.0)

    def test_governs_by_the_lesser_of_mcr_and_133mu(self):
        # AASHTO 5.6.3.3 takes the LESSER (the guide's Eq 1.15 prints max
        # -- an erratum)
        r = lrfd.rc_minimum_reinforcement(
            m_n=20000.0, phi=1.0, f_c=7.0, s_c=6403.0, m_u=1000.0,
            gamma_3=1.0, f_cpe=1.2)
        assert r.demand == pytest.approx(1.33 * 1000.0)

    def test_pre_2012_scales_the_full_mcr(self):
        # the historical 1.2 multiplies the whole Mcr, composite term
        # included
        r = lrfd.rc_minimum_reinforcement(
            m_n=20000.0, phi=1.0, f_c=7.0, s_c=6403.0, design_year=2008,
            f_cpe=1.2, m_dnc=6000.0, s_nc=4945.0)
        fr = 0.24 * math.sqrt(7.0)
        expect = 1.2 * ((fr + 1.2) * 6403.0
                        - 6000.0 * (6403.0 / 4945.0 - 1.0))
        assert r.details["Mcr"] == pytest.approx(expect)

    def test_fr_override_reproduces_midas_convention(self):
        # Midas always uses fr = 0.37*sqrt(f'c) in Mcr; the override
        # scales the fr term only
        base = lrfd.rc_minimum_reinforcement(
            m_n=20000.0, phi=1.0, f_c=7.0, s_c=4945.0, gamma_3=1.0,
            f_cpe=2.99)
        midas = lrfd.rc_minimum_reinforcement(
            m_n=20000.0, phi=1.0, f_c=7.0, s_c=4945.0, gamma_3=1.0,
            f_cpe=2.99, f_r=0.37 * math.sqrt(7.0))
        d = (1.6 * (0.37 - 0.24) * math.sqrt(7.0)) * 4945.0
        assert midas.details["Mcr"] - base.details["Mcr"] == pytest.approx(d)
        assert midas.details["fr"] == pytest.approx(0.37 * math.sqrt(7.0))


class TestTendonAndPrincipalStress:
    def test_low_relaxation_limits_table(self):
        lim = lrfd.ps_tendon_stress_limits(270.0)
        assert lim["pre_prior_to_transfer"] == pytest.approx(0.75 * 270.0)
        assert lim["pre_service_after_losses"] == pytest.approx(
            0.80 * 0.90 * 270.0)
        assert lim["post_at_anchorage_after_set"] == pytest.approx(189.0)
        assert lim["post_elsewhere_after_set"] == pytest.approx(0.74 * 270.0)

    def test_stress_relieved_transfer_drops_to_070(self):
        lim = lrfd.ps_tendon_stress_limits(270.0,
                                           tendon_type="stress_relieved")
        assert lim["pre_prior_to_transfer"] == pytest.approx(0.70 * 270.0)
        # fpy default 0.85*fpu for stress-relieved
        assert lim["pre_service_after_losses"] == pytest.approx(
            0.80 * 0.85 * 270.0)

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            lrfd.ps_tendon_stress_limits(270.0, tendon_type="rope")

    def test_principal_tension_limit(self):
        r = lrfd.ps_principal_tension_check(f_ci=4.5, sigma_ps=0.15)
        assert r.capacity == pytest.approx(0.110 * math.sqrt(4.5))
        assert r.demand == 0.15
