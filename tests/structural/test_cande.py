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

"""CANDE box-culvert integration: input-file generation (fixed-format
field positions), result parsing, and an end-to-end engine run when
cande-wrapper is installed."""

import math

import pytest

from civilpy.structural.cande import (
    BoxCulvertModel,
    DUNCAN_SELIG_SOILS,
    SoilMaterial,
    _parse_beam_results,
)


@pytest.fixture
def model():
    return BoxCulvertModel(
        span_ft=8.0, rise_ft=6.0, cover_ft=4.0,
        top_thickness_in=10.0, wall_thickness_in=8.0,
    )


class TestInputGeneration:
    def test_line_labels_in_order(self, model):
        labels = [line.split("!!")[0].strip()
                  for line in model.to_cid().splitlines()]
        assert labels == [
            "A-1", "A-2.L12",
            "B-1.Basic", "B-1.Basic", "B-1.Basic", "B-2.Basic",
            "C-1.L2.Box", "C-2.L2.Box",
            "D-1", "D-2.Isotropic", "D-1", "D-2.Isotropic",
            "D-1", "D-2.Duncan", "A-1",
        ]

    def test_a1_fixed_fields(self, model):
        a1 = model.to_cid().splitlines()[0].split("!!")[1]
        assert a1[0:8] == "ANALYS  "  # A8 mode word
        assert a1[9] == "2"           # I1 solution level
        assert a1[10:12] == " 0"      # I2 service method
        assert a1[12:15] == "  1"     # I3 one pipe group

    def test_a2_selects_box_canned_mesh(self, model):
        a2 = model.to_cid().splitlines()[1].split("!!")[1]
        assert a2[0:8] == "BASIC   "
        assert int(a2[10:15]) == 2  # NPCAN 2 = box

    def test_b1_element_ranges_cover_all_14(self, model):
        b1s = [line.split("!!")[1] for line in model.to_cid().splitlines()
               if line.lstrip().startswith("B-1.Basic")]
        ranges = [(int(l[0:5]), int(l[5:10])) for l in b1s]
        assert ranges == [(1, 4), (5, 10), (11, 14)]

    def test_b1_section_properties(self, model):
        # wall line: A = t, I = t^3/12 per unit length
        wall = [line.split("!!")[1] for line in model.to_cid().splitlines()
                if line.lstrip().startswith("B-1.Basic")][1]
        e = float(wall[10:20])
        a = float(wall[30:40])
        i = float(wall[40:50])
        assert e == pytest.approx(57000.0 * math.sqrt(4000.0), rel=1e-3)
        assert a == pytest.approx(8.0)
        assert i == pytest.approx(8.0**3 / 12.0, rel=1e-4)

    def test_c2_geometry_fields(self, model):
        c2 = [line.split("!!")[1] for line in model.to_cid().splitlines()
              if line.lstrip().startswith("C-2.L2.Box")][0]
        assert int(c2[15:20]) == 9                       # NINC
        assert float(c2[20:30]) == pytest.approx(48.0)   # half span, in
        assert float(c2[30:40]) == pytest.approx(36.0)   # half rise, in
        assert float(c2[40:50]) == pytest.approx(4.0)    # cover, ft
        assert float(c2[50:60]) == pytest.approx(120.0)  # fill density

    def test_deep_fill_adds_pressure_load_step(self):
        # cover > 1.5*rise: mesh truncates, overburden needs a 10th step
        deep = BoxCulvertModel(span_ft=8, rise_ft=6, cover_ft=12,
                               top_thickness_in=10, wall_thickness_in=8)
        c2 = [line.split("!!")[1] for line in deep.to_cid().splitlines()
              if line.lstrip().startswith("C-2.L2.Box")][0]
        assert int(c2[15:20]) == 10

    def test_trench_mesh_word(self):
        trench = BoxCulvertModel(span_ft=8, rise_ft=6, cover_ft=4,
                                 top_thickness_in=10, wall_thickness_in=8,
                                 trench_width_ft=4.0)
        c1 = [line.split("!!")[1] for line in trench.to_cid().splitlines()
              if line.lstrip().startswith("C-1.L2.Box")][0]
        assert c1.startswith("TREN")

    def test_soil_lines_last_material_flagged(self, model):
        d1s = [line.split("!!")[1] for line in model.to_cid().splitlines()
               if line.lstrip().startswith("D-1!!") or
               line.strip().startswith("D-1!!")]
        assert [l[0] for l in d1s] == [" ", " ", "L"]
        assert [int(l[1:5]) for l in d1s] == [1, 2, 3]

    def test_duncan_selig_name_validation(self):
        with pytest.raises(ValueError):
            SoilMaterial.duncan_selig("SW42", 120.0)
        for name in DUNCAN_SELIG_SOILS:
            SoilMaterial.duncan_selig(name, 120.0)

    def test_negative_cover_rejected(self):
        with pytest.raises(ValueError):
            BoxCulvertModel(span_ft=8, rise_ft=6, cover_ft=-1,
                            top_thickness_in=10, wall_thickness_in=8)


class TestResultParsing:
    def test_parse_beam_results(self, tmp_path):
        xml = """<CandeBeamResults><Control><Heading>t</Heading></Control>
        <beamResults><constIncrement>1</constIncrement>
          <resultsData><resultId>1</resultId><nodeNumber>1</nodeNumber>
            <elementNumber>1</elementNumber>
            <xCoord>0.0</xCoord><yCoord>36.0</yCoord>
            <bendingMoment>2500.0</bendingMoment>
            <thrustForce>-100.0</thrustForce><shearForce>40.0</shearForce>
          </resultsData>
        </beamResults></CandeBeamResults>"""
        path = tmp_path / "x_BeamResults.xml"
        path.write_text(xml)
        steps = _parse_beam_results(path)
        assert list(steps) == [1]
        row = steps[1][0]
        assert row["moment"] == pytest.approx(2500.0)
        assert row["thrust"] == pytest.approx(-100.0)


class TestEngineRun:
    """End-to-end through the real CANDE engine (skipped without
    cande-wrapper)."""

    @pytest.fixture(scope="class")
    def results(self, tmp_path_factory):
        pytest.importorskip("cande_wrapper")
        model = BoxCulvertModel(
            span_ft=8.0, rise_ft=6.0, cover_ft=4.0,
            top_thickness_in=10.0, wall_thickness_in=8.0,
        )
        return model.run(work_dir=tmp_path_factory.mktemp("cande"))

    def test_all_members_loaded(self, results):
        for name in ("top_slab", "wall", "bottom_slab"):
            mf = results.members[name]
            assert mf.moment > 0.0
            assert mf.shear > 0.0

    def test_wall_thrust_compressive(self, results):
        assert results.members["wall"].thrust > 0.0

    def test_top_slab_moment_near_hand_statics(self, results):
        # 4 ft of 120 pcf fill on an 8 ft clear span: a frame corner
        # fixity puts midspan near wL^2/11 ~ 2.8 kip-ft/ft; soil-structure
        # interaction should land in the same neighborhood.
        m = results.members["top_slab"].moment_kip_ft
        assert 1.5 < m < 5.0

    def test_construction_increments_present(self, results):
        assert len(results.steps) == 9

    def test_flexure_check_glue(self, results):
        # #5s at 6" (0.62 in^2/ft), d = 7.5 in: should pass with margin
        check = results.flexure_check("top_slab", a_s=0.62, d_s=7.5)
        assert check.article == "5.6.3.2"
        assert check.demand == pytest.approx(
            1.3 * results.members["top_slab"].moment)
        assert check.ok

    def test_slab_shear_check_glue(self, results):
        check = results.slab_shear_check("top_slab", a_s=0.62, d_e=7.5)
        assert check.article == "5.12.7.3"
        assert check.ok
