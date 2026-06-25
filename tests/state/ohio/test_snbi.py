"""
CivilPy
Copyright (C) 2019-2026 - Dane Parks

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

Tests for the FHWA SNBI validation models in civilpy.state.ohio.snbi.
"""
import pytest
from pydantic import ValidationError

from civilpy.state.ohio.snbi import (
    Bridge, Element, Route, Feature, Inspection, PostingEvaluation,
    PostingStatus, SpanSet, SubstructureSet, Work,
)


def _features():
    return [Feature(BF01="H", Routes=[Route(BRT01="R1")])]


def _valid_kwargs(**overrides):
    """A minimal bridge that satisfies every required FHWA check."""
    data = dict(
        BID01="0100226",
        BL01=39, BL05=40.0, BL06=-82.0,
        BCL01="1", BCL02="1",
        BG01=100.0, BG02=110.0, BG05=40.0, BG09=36.0,
        BC01="7", BC02="6", BC03="6", BC04="N",
        Features=_features(),
        PostingStatuses=[PostingStatus(BPS01="A")],
        SpanSets=[SpanSet(BSP01="M", BSP06="G01")],
        SubstructureSets=[SubstructureSet(BSB01="A1")],
        Works=[Work(BW02=1985)],
    )
    data.update(overrides)
    return data


def make_bridge(**overrides):
    return Bridge(**_valid_kwargs(**overrides))


# --------------------------------------------------------------------------- #
# Baseline
# --------------------------------------------------------------------------- #
def test_valid_bridge_passes():
    b = make_bridge()
    assert b.BID01 == "0100226"
    assert b.BID03 == "0"  # default


# --------------------------------------------------------------------------- #
# State code (B.L.01) - replaces the broken Field(eq=39) no-op
# --------------------------------------------------------------------------- #
class TestStateCode:
    def test_ohio_valid(self):
        assert make_bridge(BL01=39).BL01 == 39

    def test_other_state_valid(self):
        # Generic FHWA check: any valid state code passes, not just Ohio
        assert make_bridge(BL01=6).BL01 == 6      # California
        assert make_bridge(BL01=72).BL01 == 72    # Puerto Rico

    def test_invalid_state_raises(self):
        with pytest.raises(ValidationError):
            make_bridge(BL01=99)


# --------------------------------------------------------------------------- #
# Data-type / length corrections
# --------------------------------------------------------------------------- #
class TestTypesAndLengths:
    def test_district_alphanumeric_allowed(self):
        # B.L.04: FHWA allows A-Z, a-z, 0-9 (was wrongly int-only before)
        assert make_bridge(BL04="0A").BL04 == "0A"

    def test_district_symbol_rejected(self):
        with pytest.raises(ValidationError):
            make_bridge(BL04="*")

    def test_longitude_accepts_decimal(self):
        assert make_bridge(BL06=-82.123456).BL06 == pytest.approx(-82.123456)

    def test_previous_number_max_15(self):
        with pytest.raises(ValidationError):
            make_bridge(BID03="x" * 16)

    def test_bridge_location_restored(self):
        assert make_bridge(BL11="Over Main St, 0.5 mi N of SR-10").BL11.startswith("Over")

    def test_min_span_length_restored(self):
        assert make_bridge(BG04=25.0).BG04 == 25.0

    def test_bridge_number_charset(self):
        with pytest.raises(ValidationError):
            make_bridge(BID01="BAD%CHAR")


# --------------------------------------------------------------------------- #
# FHWA-calculated items must NOT be reported
# --------------------------------------------------------------------------- #
class TestDoNotReport:
    @pytest.mark.parametrize("field", ["BG16", "BC12", "BC13"])
    def test_calculated_fields_rejected(self, field):
        with pytest.raises(ValidationError):
            make_bridge(**{field: "5"})

    def test_inspection_due_date_rejected(self):
        with pytest.raises(ValidationError):
            Inspection(BIE01="2", BIE02="20240101", BIE06="20250101")


# --------------------------------------------------------------------------- #
# Enumerations & condition ratings
# --------------------------------------------------------------------------- #
class TestEnumerations:
    def test_condition_rating_valid(self):
        assert make_bridge(BC01="9").BC01 == "9"
        assert make_bridge(BC04="N").BC04 == "N"

    def test_condition_rating_invalid(self):
        with pytest.raises(ValidationError):
            make_bridge(BC01="X")

    def test_median_range(self):
        assert make_bridge(BG10="3").BG10 == "3"
        with pytest.raises(ValidationError):
            make_bridge(BG10="4")

    def test_toll_enum(self):
        with pytest.raises(ValidationError):
            make_bridge(BCL05="9")

    def test_approach_alignment_enum(self):
        assert make_bridge(BAP01="G").BAP01 == "G"
        with pytest.raises(ValidationError):
            make_bridge(BAP01="Z")

    def test_border_state_or_country(self):
        assert make_bridge(BL08="MX").BL08 == "MX"
        with pytest.raises(ValidationError):
            make_bridge(BL08="99")


# --------------------------------------------------------------------------- #
# Date format / calendar validity
# --------------------------------------------------------------------------- #
class TestDates:
    def test_valid_date(self):
        assert make_bridge(BLR03="20240101").BLR03 == "20240101"

    def test_non_numeric_date_raises(self):
        with pytest.raises(ValidationError):
            make_bridge(BLR03="2024-01-01")

    def test_impossible_calendar_date_raises(self):
        with pytest.raises(ValidationError):
            make_bridge(BLR03="20241350")


# --------------------------------------------------------------------------- #
# Numeric magnitude bounds
# --------------------------------------------------------------------------- #
class TestRanges:
    def test_span_length_magnitude(self):
        with pytest.raises(ValidationError):
            make_bridge(BG03=10000.0)   # exceeds 9999.9

    def test_load_rating_factor_magnitude(self):
        with pytest.raises(ValidationError):
            make_bridge(BLR05=100.0)    # exceeds 99.99


# --------------------------------------------------------------------------- #
# "At least one dataset" critical rules
# --------------------------------------------------------------------------- #
class TestRequiredDatasets:
    @pytest.mark.parametrize("field", ["Features", "PostingStatuses", "SpanSets", "Works"])
    def test_missing_dataset_raises(self, field):
        with pytest.raises(ValidationError):
            make_bridge(**{field: None})

    def test_substructure_required_for_non_culvert(self):
        with pytest.raises(ValidationError):
            make_bridge(SubstructureSets=None)

    def test_substructure_optional_for_buried_culvert(self):
        # All spans are buried pipe culverts (BSP06 = P01) -> substructure optional
        b = make_bridge(
            SpanSets=[SpanSet(BSP01="C01", BSP06="P01")],
            SubstructureSets=None,
            BC04="5",
        )
        assert b.SubstructureSets is None


# --------------------------------------------------------------------------- #
# Feature-type conditional rules
# --------------------------------------------------------------------------- #
class TestFeatureConditionals:
    def test_highway_requires_route(self):
        with pytest.raises(ValidationError):
            make_bridge(Features=[Feature(BF01="H")])

    def test_waterway_requires_navigable_code(self):
        with pytest.raises(ValidationError):
            make_bridge(Features=[Feature(BF01="W")])

    def test_waterway_with_navigable_code_ok(self):
        b = make_bridge(Features=[Feature(BF01="W", BN01="N")])
        assert b.Features[0].BN01 == "N"


# --------------------------------------------------------------------------- #
# Load evaluation / posting requirement (B.EP)
# --------------------------------------------------------------------------- #
class TestPostingEvaluation:
    def test_required_when_open_and_under_rated(self):
        with pytest.raises(ValidationError):
            make_bridge(BLR07=0.8, PostingStatuses=[PostingStatus(BPS01="SP")])

    def test_satisfied_with_evaluation(self):
        b = make_bridge(
            BLR07=0.8,
            PostingStatuses=[PostingStatus(BPS01="SP")],
            PostingEvaluations=[PostingEvaluation(BEP01="Type3")],
        )
        assert b.PostingEvaluations[0].BEP01 == "Type3"

    def test_not_required_when_closed(self):
        b = make_bridge(BLR07=0.8, PostingStatuses=[PostingStatus(BPS01="C")])
        assert b.PostingEvaluations is None


# --------------------------------------------------------------------------- #
# Safety checks
# --------------------------------------------------------------------------- #
class TestSafety:
    def test_low_condition_rating_not_closed(self):
        with pytest.raises(ValidationError):
            make_bridge(BC01="1")  # < 2 and not posted closed

    def test_low_condition_rating_closed_ok(self):
        b = make_bridge(BC01="1", PostingStatuses=[PostingStatus(BPS01="C")])
        assert b.BC01 == "1"

    def test_low_operating_rating_not_closed(self):
        with pytest.raises(ValidationError):
            make_bridge(BLR06=0.05)

    def test_legal_rating_below_one_requires_posting(self):
        with pytest.raises(ValidationError):
            make_bridge(
                BLR07=0.8,
                PostingStatuses=[PostingStatus(BPS01="A")],
                PostingEvaluations=[PostingEvaluation(BEP01="T")],
            )


# --------------------------------------------------------------------------- #
# Length consistency & previous bridge number
# --------------------------------------------------------------------------- #
class TestConsistency:
    def test_nbis_not_greater_than_total(self):
        with pytest.raises(ValidationError):
            make_bridge(BG01=200.0, BG02=110.0)

    def test_previous_number_must_differ(self):
        with pytest.raises(ValidationError):
            make_bridge(BID03="0100226")  # equals BID01

    def test_nstm_condition_only_when_required(self):
        with pytest.raises(ValidationError):
            make_bridge(BC14="7")  # BIR01 != 'Y'
        b = make_bridge(BIR01="Y", BC14="7")
        assert b.BC14 == "7"


# --------------------------------------------------------------------------- #
# Element quantity reconciliation
# --------------------------------------------------------------------------- #
class TestElement:
    def test_total_equals_sum(self):
        e = Element(BE01="12", BE02="0", BE03=100, BCS01=70, BCS02=20, BCS03=10, BCS04=0)
        assert e.BE03 == 100

    def test_total_mismatch_raises(self):
        with pytest.raises(ValidationError):
            Element(BE01="12", BE02="0", BE03=100, BCS01=70, BCS02=20, BCS03=5, BCS04=0)


# --------------------------------------------------------------------------- #
# Child key-field requirements
# --------------------------------------------------------------------------- #
class TestChildRequirements:
    def test_route_designation_starts_with_r(self):
        with pytest.raises(ValidationError):
            Route(BRT01="US")

    def test_work_year_required(self):
        with pytest.raises(ValidationError):
            Work()

    def test_inspection_requires_type_and_begin_date(self):
        with pytest.raises(ValidationError):
            Inspection()
        insp = Inspection(BIE01="2", BIE02="20240101")
        assert insp.BIE01 == "2"