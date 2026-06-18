#  CivilPy
#  Copyright (C) 2026 Dane Parks
#  (AGPL v3 — see the module header for the full notice)

"""LPILE integration (civilpy.geotech.lpile): data-file codegen, the
built-in simulation, and the text-report parser round-trip."""

import numpy as np
import pytest

from civilpy.geotech import lpile
from civilpy.geotech.lateral_pile import LinearPY, SandPY, SoftClayPY, StiffClayPY
from civilpy.geotech.soil_profile import SoilLayer, SoilProfile


def _section():
    return lpile.PileSection(length=300.0, diameter=24.0, ei=5.0e10)


def _layers():
    return [
        lpile.LPileSoilLayer(0, 120, SoftClayPY(cu=8.0, b=24.0, gamma=0.04)),
        lpile.LPileSoilLayer(120, 300, SandPY(phi_deg=36, gamma=0.06, b=24.0)),
    ]


def _model(**kw):
    return lpile.LPileModel(_section(), _layers(), lpile.LPileLoad(shear=20000.0,
                            moment=5.0e5), **kw)


class TestModelSpec:
    def test_soft_clay(self):
        name, p = lpile._lpile_model_spec(SoftClayPY(cu=5, b=12, gamma=0.04))
        assert name == "Matlock Soft Clay"
        assert p["c"] == 5

    def test_stiff_clay(self):
        name, _ = lpile._lpile_model_spec(StiffClayPY(cu=20, b=12, gamma=0.05))
        assert name == "Stiff Clay without Free Water"

    def test_sand(self):
        name, p = lpile._lpile_model_spec(SandPY(phi_deg=35, gamma=0.06, b=12))
        assert name == "API Sand"
        assert "phi" in p

    def test_linear(self):
        name, p = lpile._lpile_model_spec(LinearPY(k=100.0))
        assert name == "Elastic Subgrade"
        assert p["k"] == 100.0

    def test_unknown(self):
        class Weird(lpile.PYCurve):
            def pu(self, z):
                return 0.0

            def p(self, y, z):
                return 0.0

        with pytest.raises(TypeError):
            lpile._lpile_model_spec(Weird())


class TestPileSection:
    def test_defaults(self):
        s = _section()
        assert s.area == pytest.approx(np.pi * 24 ** 2 / 4)
        assert s.moment_of_inertia == pytest.approx(5e10 / 29e6)

    def test_explicit_area(self):
        s = lpile.PileSection(length=100, diameter=12, ei=1e9, area=50.0)
        assert s.area == 50.0

    def test_bad(self):
        with pytest.raises(ValueError):
            lpile.PileSection(length=0, diameter=12, ei=1e9)
        with pytest.raises(ValueError):
            lpile.PileSection(length=100, diameter=0, ei=1e9)
        with pytest.raises(ValueError):
            lpile.PileSection(length=100, diameter=12, ei=0)


class TestSoilLayer:
    def test_bad_range(self):
        with pytest.raises(ValueError):
            lpile.LPileSoilLayer(120, 100, SoftClayPY(cu=5, b=12, gamma=0.04))

    def test_model_name_and_contains(self):
        lyr = lpile.LPileSoilLayer(0, 120, SoftClayPY(cu=5, b=12, gamma=0.04))
        assert lyr.model_name == "Matlock Soft Clay"
        assert lyr.contains(50) and not lyr.contains(150)


class TestLoad:
    def test_conditions(self):
        assert lpile.LPileLoad(shear=1000).condition == 1
        assert lpile.LPileLoad(shear=1000, condition=2, slope=0.0).condition == 2

    def test_bad_condition(self):
        with pytest.raises(ValueError):
            lpile.LPileLoad(shear=1000, condition=3)


class TestModel:
    def test_requires_layers(self):
        with pytest.raises(ValueError):
            lpile.LPileModel(_section(), [], lpile.LPileLoad(shear=1000))

    def test_layers_sorted(self):
        m = lpile.LPileModel(
            _section(),
            [lpile.LPileSoilLayer(120, 300, SandPY(phi_deg=36, gamma=0.06, b=24)),
             lpile.LPileSoilLayer(0, 120, SoftClayPY(cu=8, b=24, gamma=0.04))],
            lpile.LPileLoad(shear=1000),
        )
        assert m.layers[0].top == 0

    def test_curve_at_layers_and_fallthrough(self):
        m = _model()
        assert isinstance(m.curve_at(50), SoftClayPY)
        assert isinstance(m.curve_at(200), SandPY)
        # below the deepest layer -> extends the last curve
        assert isinstance(m.curve_at(9999), SandPY)

    def test_from_soil_profile(self):
        sp = SoilProfile([SoilLayer("Clay", 10, 120), SoilLayer("Sand", 15, 125)])
        m = lpile.LPileModel.from_soil_profile(
            sp, [SoftClayPY(cu=8, b=24, gamma=0.04),
                 SandPY(phi_deg=36, gamma=0.06, b=24)],
            _section(), lpile.LPileLoad(shear=1000),
        )
        assert m.layers[0].bottom == pytest.approx(120.0)  # 10 ft -> 120 in
        assert m.layers[1].name == "Sand"

    def test_from_soil_profile_mismatch(self):
        sp = SoilProfile([SoilLayer("Clay", 10, 120)])
        with pytest.raises(ValueError):
            lpile.LPileModel.from_soil_profile(
                sp, [], _section(), lpile.LPileLoad(shear=1000))


class TestCodegen:
    def test_to_lpd_static(self):
        lpd = _model().to_lpd()
        assert f"Data Format Version {lpile.DATA_FORMAT_VERSION}" in lpd
        assert "Loading Type = Static" in lpd
        assert "Matlock Soft Clay" in lpd
        assert "API Sand" in lpd

    def test_to_lpd_cyclic(self):
        lpd = _model(cyclic=True, n_cycles=20).to_lpd()
        assert "Loading Type = Cyclic" in lpd
        assert "Number of Cycles = 20" in lpd

    def test_write_lpd(self, tmp_path):
        path = _model().write_lpd(tmp_path, prefix="mypile")
        assert path.name == "mypile.lpd"
        assert path.read_text().startswith("LPILE Data File")


class TestSimulateAndRun:
    def test_simulate_free_head(self):
        res = _model().simulate()
        assert res.source == "civilpy-fe"
        assert res.pile_head_deflection > 0
        assert res.max_moment > 0

    def test_simulate_fixed_head(self):
        free = _model().simulate()
        fixed_model = lpile.LPileModel(
            _section(), _layers(),
            lpile.LPileLoad(shear=20000.0, condition=2, slope=0.0),
        )
        fixed = fixed_model.simulate()
        assert fixed.pile_head_deflection < free.pile_head_deflection

    def test_run_without_executable(self):
        with pytest.raises(FileNotFoundError):
            _model().run(lpile_exe=None)


class TestResults:
    def test_lateral_stiffness(self):
        res = _model().simulate()
        assert res.lateral_stiffness == pytest.approx(
            res.shear[0] / res.pile_head_deflection
        )

    def test_lateral_stiffness_zero_deflection(self):
        res = lpile.LPileResults(
            depth=np.array([0.0, 1.0]), deflection=np.array([0.0, 0.0]),
            moment=np.zeros(2), shear=np.array([1000.0, 0.0]),
            soil_reaction=np.zeros(2), pile_head_deflection=0.0,
            max_moment=0.0, max_moment_depth=0.0,
        )
        assert res.lateral_stiffness == float("inf")

    def test_plot(self):
        fig = _model().simulate().plot()
        assert fig is not None
        assert len(fig.data) == 4


class TestRoundTrip:
    def test_report_roundtrip(self):
        res = _model().simulate()
        parsed = lpile.parse_lpile_report(res.to_report_text())
        assert parsed.source == "lpile-report"
        assert np.allclose(parsed.deflection, res.deflection, atol=1e-6)
        assert np.allclose(parsed.moment, res.moment, rtol=1e-4, atol=1.0)
        assert parsed.pile_head_deflection == pytest.approx(
            res.pile_head_deflection, rel=1e-4)
        assert parsed.max_moment == pytest.approx(res.max_moment, rel=1e-4)

    def test_parse_realistic_fixture(self):
        text = """
        LPILE Plus 11.0 Output

                 Depth     Deflection      Moment       Shear   Soil Reaction
                  (in)        (in)        (lb-in)        (lb)        (lb/in)
        ----------------------------------------------------------------------
                 0.000      0.45230      0.00000E+00    10000.00     0.00000E+00
                 6.000      0.43100      6.00000E+04     9700.00     1.50000E+02
                12.000      0.40500      1.17000E+05     9100.00     2.80000E+02

          Pile-head deflection  = 4.52300E-01 in
          Pile-head rotation    = -2.10000E-03 radians
          Maximum bending moment = 1.71000E+05 lb-in  at depth 42.000 in
        """
        res = lpile.parse_lpile_report(text)
        assert len(res.depth) == 3
        assert res.pile_head_deflection == pytest.approx(0.45230)
        assert res.pile_head_rotation == pytest.approx(-2.1e-3)
        assert res.max_moment == pytest.approx(1.71e5)
        assert res.max_moment_depth == pytest.approx(42.0)

    def test_parse_without_summary_uses_defaults(self):
        text = """
        Depth   Deflection   Moment   Shear   Soil Reaction
        0.000    0.50000     0.0      1000.0    0.0
        6.000    0.40000     50000.0   900.0    100.0
        12.000   0.30000     90000.0   800.0    200.0
        """
        res = lpile.parse_lpile_report(text)
        # no summary lines -> defaults derived from the table
        assert res.pile_head_deflection == pytest.approx(0.5)
        assert res.pile_head_rotation == 0.0
        assert res.max_moment == pytest.approx(90000.0)
        assert res.max_moment_depth == pytest.approx(12.0)

    def test_parse_no_table_raises(self):
        with pytest.raises(ValueError):
            lpile.parse_lpile_report("no data here at all")
