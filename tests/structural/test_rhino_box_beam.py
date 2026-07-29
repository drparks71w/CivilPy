#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""G9 -- prestressed concrete adjacent box-beam bridges built from a standard
PSBD-1-25 / PSBDD-1-25 box designation. Checks the beam-solid/tendon/
diaphragm/tie-rod/bearing-pad geometry counts, the self-weight, and the tag
round-trip the BoxBeamLines importer consumes."""

import pytest

rhino3dm = pytest.importorskip("rhino3dm")

from civilpy.structural.odot import box_section_properties
from civilpy.structural.rhino_box_beam import build_box_beams, read_box_beam_model


class TestBuildBoxBeams:
    def test_composite_geometry_counts(self, tmp_path):
        out = tmp_path / "box.3dm"
        # CB27-48 @ 50 ft: strands_2in=12, strands_4in=6, strands_6in=0
        m = build_box_beams(out_path=out, box="CB27-48", span_ft=50, n_beams=4)
        assert m.n_beams == 4
        assert m.bridge_width_ft == pytest.approx(4 * 4.0)  # 48 in beams
        assert m.n_beam_solids == 4 * 4          # 4 walls x 4 beams
        assert m.n_tendons == 4 * 2              # 2 active rows x 4 beams
        assert m.n_bearing_pads == 4 * 2         # 2 ends x 4 beams
        assert m.n_diaphragms == 1               # span 50 ft <= 50
        # n_diaphragms is the INTERMEDIATE count; the bridge also has two
        # end diaphragms, so three get drawn and three tie-rod runs with them
        assert m.n_diaphragm_objects == 3
        assert m.n_tie_rods == 3
        assert m.composite is True
        assert m.n_slab == 1

    def test_non_composite_has_no_slab(self, tmp_path):
        out = tmp_path / "box.3dm"
        m = build_box_beams(out_path=out, box="B27-48", span_ft=50, n_beams=3)
        assert m.composite is False
        assert m.n_slab == 0

    def test_self_weight_matches_section_area(self, tmp_path):
        out = tmp_path / "box.3dm"
        m = build_box_beams(out_path=out, box="CB27-48", span_ft=50, n_beams=2)
        s = box_section_properties(27)
        assert m.self_weight_klf_per_beam == pytest.approx(
            s.area / 144.0 * 0.150)

    def test_more_diaphragms_for_longer_span(self, tmp_path):
        out = tmp_path / "box.3dm"
        # CB33-48 @ 80 ft -> span > 75 ft => 3 diaphragms
        m = build_box_beams(out_path=out, box="CB33-48", span_ft=80, n_beams=3)
        assert m.n_diaphragms == 3
        assert m.n_diaphragm_objects == 5        # 3 intermediate + 2 end
        assert m.n_tie_rods == 5        # one run per diaphragm

    def test_unknown_span_rejected(self, tmp_path):
        with pytest.raises(KeyError, match="no PSBDD-1-25 design"):
            build_box_beams(out_path=tmp_path / "x.3dm", box="CB27-48",
                            span_ft=999, n_beams=3)

    def test_roundtrip_tags(self, tmp_path):
        out = tmp_path / "box.3dm"
        build_box_beams(out_path=out, box="CB27-48", span_ft=50, n_beams=4)
        rows = read_box_beam_model(str(out))
        kinds = {r["kind"] for r in rows}
        assert kinds == {"girder", "box_beam", "tendon", "diaphragm",
                          "tie_rod", "bearing_pad", "deck"}

        girders = [r for r in rows if r["kind"] == "girder"]
        assert len(girders) == 4
        assert girders[0]["attrs"]["family"] == "box"
        assert girders[0]["attrs"]["box"] == "CB27-48"

        beams = [r for r in rows if r["kind"] == "box_beam"]
        assert beams[0]["attrs"]["depth"] == pytest.approx(27.0)

        tendons = [r for r in rows if r["kind"] == "tendon"]
        rows_seen = {t["attrs"]["tendon.row"] for t in tendons}
        assert rows_seen == {2.0, 4.0}
        strands_seen = {t["attrs"]["tendon.strands"] for t in tendons}
        assert strands_seen == {12.0, 6.0}

        pads = [r for r in rows if r["kind"] == "bearing_pad"]
        assert all(p["attrs"]["bearing_pad.type"] == "B1" for p in pads)

        diaphragms = [r for r in rows if r["kind"] == "diaphragm"]
        # stations are sorted: the first is the END diaphragm 2'-6" in
        assert diaphragms[0]["attrs"]["diaphragm.station"] == pytest.approx(2.5)
        assert diaphragms[1]["attrs"]["diaphragm.station"] == pytest.approx(25.0)

        tie_rods = [r for r in rows if r["kind"] == "tie_rod"]
        assert tie_rods[0]["attrs"]["tie_rod.max_beams_per_rod"] == pytest.approx(3.0)

        deck = [r for r in rows if r["kind"] == "deck"]
        assert len(deck) == 1
        assert deck[0]["attrs"]["deck.t"] == pytest.approx(5.0)
        assert deck[0]["attrs"]["deck.wearing_surface"] == pytest.approx(1.0)
