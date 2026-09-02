"""Offline structure checks for the Steel Composite Girder Bridge wizard
payload builder (no MIDAS session).  Counts pin what the Civil NX wizard
produced for the three-span curved tutorial on 2025 v2.1 where the builder
reproduces it; the "Dummy Beam2" family and exact node count are not yet
reproduced (see the module docstring checklist) and are not asserted."""
import math

import pytest

from civilpy.structural import midas_composite_wizard as wiz


@pytest.fixture(scope="module")
def built():
    return wiz.build(wiz.WizardInputs())


def test_table_order_covers_payload(built):
    payload, _ = built
    assert set(payload) <= set(wiz.TABLE_ORDER)


def test_group_counts_match_wizard(built):
    payload, _ = built
    groups = {v["NAME"]: len(v["E_LIST"]) for v in payload["GRUP"].values()}
    assert groups["Bracing"] == 268          # wizard: 268 (112 truss diagonals)
    assert groups["Dummy Beam"] == 730       # 73 lines x 10 (bays split at mid-bay + 2 overhangs)
    assert groups["Coping"] == 14            # 7 cap elements per pier incl. the zero-length one
    assert groups["Substructure"] == 2       # two columns
    assert 430 <= groups["Girder"] <= 450    # wizard: 440
    assert groups["Dummy Beam-D1"] + groups["Dummy Beam-D2"] == groups["Dummy Beam"]
    for i in range(1, 6):
        assert groups[f"10th Point Girder-{i}-i"] == 27 or groups[f"10th Point Girder-{i}-i"] == 30


def test_truss_count(built):
    payload, _ = built
    assert sum(1 for e in payload["ELEM"].values() if e["TYPE"] == "TRUSS") == 104


def test_supports_links_and_rigid_masters(built):
    payload, _ = built
    assert len(payload["CONS"]) == 12        # 10 abutment seats + 2 column bases
    assert len(payload["ELNK"]) == 20        # 4 supports x 5 girders
    assert len(payload["RIGD"]) == 75        # 15 bracing lines x 5 girders
    assert all(v["SDR"][3:] == [0, 0, 0] for v in payload["ELNK"].values())   # translational bearings only


def test_span_information(built):
    payload, _ = built
    spans = payload["SPAN"]
    assert len(spans) == 15
    first = spans["1"]["SPAN_BASE_ITEMS"]
    assert first[0]["SUPPORT"] in (1, 2) and first[-1]["SUPPORT"] in (1, 2)
    assert all(it["SUPPORT"] == 0 for it in first[1:-1])


def test_composite_stage_parts_positive(built):
    payload, _ = built
    for row in payload["CSCS"].values():
        for part in row["vPARTINFO"]:
            assert part["PARTINFO_VS"] > 0 and part["PARTINFO_H"] > 0
        assert row["vPARTINFO"][1]["AGE"] == 28 and row["vPARTINFO"][0]["AGE"] == 1


def test_stage_names_and_durations(built):
    payload, _ = built
    got = [(v["NAME"], v["DURATION"]) for v in payload["STAG"].values()]
    assert got == list(wiz.STAGE_DURATIONS)


def test_geometry_conventions():
    w = wiz.WizardInputs()
    # positive offset is toward the circle centre (convex), i.e. a smaller radius
    x, y = wiz.plan_xy(w, 0.0, 5.0)
    assert math.isclose(math.hypot(x, y + w.radius), w.radius - 5.0)
    # zero skew crosses at the reference station
    assert math.isclose(wiz.support_theta(wiz.WizardInputs(skews_deg=(0, 0, 0, 0)), 1, -7.0), 60.0 / w.radius, rel_tol=1e-9)
    # superelevation banks toward the inside (right) of the curve
    assert wiz.deck_elevation(w, 0.0, 5.0) < wiz.deck_elevation(w, 0.0, -19.0)


def test_tapered_section_is_user_dimension_type(built):
    payload, _ = built
    cap = payload["SECT"][str(wiz.WizardInputs().sect_cap)]["SECT_BEFORE"]
    assert cap["TYPE"] == 2 and cap["OFFSET_PT"] == "CT"
