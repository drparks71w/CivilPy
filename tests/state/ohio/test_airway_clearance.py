"""Airway/Highway Clearance Analysis (L&D §1407.1 / Part 77.9).

Ground truth: E.L. Robinson's 2026-08-28 analysis letter for CUY-291-0299
(PID 117817) — CLE 1.4 NM away, nearest runway point 0.91 mi, runway
elevation 799.5 ft, project high point 819 ft, L = 4,787 ft, 100:1 surface
at 847.4 ft; 30-ft light poles (849.0) and a 60-ft crane (879.0) both
penetrate; SW General Hospital heliport (2.0 NM) and Columbia (7.9 NM)
outside their reach.

Facility rows are NASR 28-day (eff. 2026-08-06).  Against the surveyed
runway-28 end the nearest runway point is 5,086 ft (ELR hand-measured
4,787 ft to the pavement), so the surface is 850.4 ft: the crane still
penetrates by 28.6 ft but the poles *clear by 1.4 ft* — inside the 20-ft
accuracy band, hence "marginal" and still a notification item.
"""
import pytest

from civilpy.state.ohio.DOT.airway_clearance import (
    Facility, Runway, RunwayEnd, HeightClass, screen, surface_for,
    haversine_ft, nearest_runway_point, equipment_height_hint,
    light_pole_height_from_design, structure_high_point_hint,
    expected_plan_note, detect_g118_notes, analysis_letter, form_7460_rows,
    to_dms, NM_FT, MI_FT,
)

SITE = (41.403147, -81.825317)      # 41°24'11.33" N, 81°49'31.14" W
SITE_ELEV = 819.0


def cle():
    return Facility(
        "CLE", "CLEVELAND-HOPKINS INTL", "A", 41.40940694, -81.85469111, 799.5,
        use="PU", ownership="PU", runways=[
            Runway("06L/24R", 9000, [RunwayEnd("06L", 41.39987202, -81.8734895, 770.1),
                                     RunwayEnd("24R", 41.41576397, -81.84837541, 781.1)]),
            Runway("06R/24L", 9953, [RunwayEnd("06R", 41.39774283, -81.86981997, 775.5),
                                     RunwayEnd("24L", 41.41531694, -81.84204725, 785.7)]),
            Runway("10/28", 6018, [RunwayEnd("10", 41.41701561, -81.85424561, 767.1),
                                   RunwayEnd("28", 41.41606133, -81.83234422, 799.5)]),
        ])


def sw_general():
    return Facility("37OH", "SOUTHWEST GENERAL HOSPITAL", "H", 41.37100277, -81.83285416,
                    870.0, use="PR", ownership="PR", runways=[
                        Runway("H1", 46, [RunwayEnd("H1", 41.37084166, -81.83430277, 792.0)]),
                        Runway("H2", 60, [RunwayEnd("H2", 41.37116388, -81.83140555, 870.0)])])


def columbia():
    # 7.9 NM per the letter; 3,152-ft runway -> 50:1 / 10,000 ft
    return Facility("4G8", "COLUMBIA", "A", 41.31868019, -81.96044183, 810.7,
                    use="PU", ownership="PR",
                    runways=[Runway("18/36", 3152, [
                        RunwayEnd("18", 41.32300466, -81.9603188, 809.5),
                        RunwayEnd("36", 41.31435572, -81.96056486, 810.1)])])


HEIGHTS = [HeightClass("light poles (A10B30)", 30, "appurtenance", count=12),
           HeightClass("construction crane", 60, "equipment")]


class TestGeometry:
    def test_haversine_to_reference_point(self):
        # ELR quoted 1.4 NM; the NASR reference point is 1.38
        d = haversine_ft(*SITE, cle().lat, cle().lon)
        assert d / NM_FT == pytest.approx(1.38, abs=0.02)

    def test_nearest_runway_point_is_the_28_end(self):
        dist, pt, end, t = nearest_runway_point(*SITE, cle().runways[2])
        assert end.end_id == "28" and t == 1.0
        assert dist == pytest.approx(5086, abs=15)
        assert pt == (end.lat, end.lon)

    def test_nearest_point_interior_when_site_is_abeam(self):
        # a point abeam the middle of 10/28, 1,000 ft north of it
        r = cle().runways[2]
        mid_lat = (r.ends[0].lat + r.ends[1].lat) / 2 + 1000 / 364567
        mid_lon = (r.ends[0].lon + r.ends[1].lon) / 2
        dist, pt, end, t = nearest_runway_point(mid_lat, mid_lon, r)
        assert 0.4 < t < 0.6 and dist == pytest.approx(1000, abs=15)

    def test_single_end_runway_degenerates(self):
        r = Runway("H1", 100, [RunwayEnd("H1", 41.3733, -81.8035, 870)])
        dist, pt, end, t = nearest_runway_point(*SITE, r)
        assert pt == (41.3733, -81.8035) and t == 0.0

    def test_surface_selection(self):
        assert surface_for(cle()) == (100.0, 20000.0)
        assert surface_for(columbia()) == (50.0, 10000.0)    # 3,152 <= 3,200
        short = Facility("X", "x", "A", 40, -82, 900,
                         runways=[Runway("1", 3200, [])])
        assert surface_for(short) == (50.0, 10000.0)
        assert surface_for(sw_general()) == (25.0, 5000.0)


class TestCUY291Screen:
    @pytest.fixture
    def result(self):
        return screen(*SITE, SITE_ELEV, [cle(), sw_general(), columbia()], HEIGHTS)

    def test_reproduces_elr_letter(self, result):
        ctl = result.controlling
        assert ctl.facility.facility_id == "CLE"
        assert ctl.runway.runway_id == "10/28"
        assert ctl.datum_elev_ft == 799.5
        assert ctl.slope == 100 and ctl.within_reach
        assert ctl.surface_elev_ft == pytest.approx(850.4, abs=0.3)
        poles, crane = ctl.heights
        assert poles.top_elev_ft == 849.0 and poles.verdict == "marginal" and poles.notify
        assert poles.margin_ft == pytest.approx(1.4, abs=0.3)
        assert crane.top_elev_ft == 879.0 and crane.penetrates
        assert crane.margin_ft == pytest.approx(-28.6, abs=0.3)
        assert result.status == "faa_notification" and result.strict_penetration
        assert result.faa_notification_required and not result.agl_notification

    def test_other_facilities_outside_reach(self, result):
        by_id = {f.facility.facility_id: f for f in result.facilities}
        assert by_id["37OH"].distance_ft / NM_FT == pytest.approx(2.0, abs=0.1)
        assert by_id["37OH"].runway.runway_id == "H2"   # nearer pad
        assert not by_id["37OH"].within_reach          # ~11,700 ft > 5,000
        assert not by_id["37OH"].penetrates and not by_id["37OH"].notify
        assert by_id["4G8"].distance_ft / NM_FT == pytest.approx(7.9, abs=0.2)
        assert by_id["4G8"].slope == 50 and not by_id["4G8"].within_reach

    def test_plan_note_g118a(self, result):
        note = expected_plan_note(result)
        assert note["note"] == "G118A" and note["facility_id"] == "CLE"

    def test_as_dict_round_numbers(self, result):
        d = result.as_dict()
        assert d["status"] == "faa_notification"
        assert d["site"]["lat_dms"] == "41° 24' 11.33\" N"
        assert d["site"]["lon_dms"] == "81° 49' 31.14\" W"
        f = d["facilities"][0]
        assert f["facility_id"] == "CLE" and f["distance_nm"] == pytest.approx(1.38, abs=0.01)
        assert f["runway_distance_mi"] == pytest.approx(0.96, abs=0.01)
        assert f["clearance_below_surface_ft"] == pytest.approx(31.4, abs=0.3)
        assert f["heights"][0]["verdict"] == "marginal"
        assert d["plan_note"]["note"] == "G118A"

    def test_letter_and_7460(self, result):
        txt = analysis_letter(result, project_label="CUY-SR291-02.99 DECK",
                              pid="117817", district="12")
        assert "1.4 nautical miles" in txt and "100:1" in txt
        assert "799.5 ft" in txt and "819.0 ft" in txt and "850.4 ft" in txt
        assert "marginally" in txt and "encroaches" in txt
        assert "Form 7460-1" in txt and "G118A" in txt
        rows = form_7460_rows(result)
        assert [r["overall_amsl_ft"] for r in rows] == [849.0, 879.0]
        assert [r["penetrates"] for r in rows] == [False, True]
        assert all(r["notify"] for r in rows)
        assert rows[0]["lat_dms"].endswith("N") and rows[0]["datum"] == "NAD83"


class TestNegativeAndEdgeCases:
    def test_remote_site_not_required(self):
        # ~7 NM east of CLE: outside every reach, inside the 60,000-ft search
        res = screen(41.45, -81.70, 900.0, [cle(), sw_general()], HEIGHTS)
        assert res.status == "not_required"
        assert not res.analysis_required
        assert res.controlling.facility.facility_id == "CLE"   # nearest for context
        assert res.controlling.heights[0].margin_ft > 0
        assert expected_plan_note(res)["note"] is None

    def test_in_reach_but_clear_gives_g118b(self):
        # ~10,000 ft NE of the 28 end: surface ~900 ft, crane top 760 ft
        res = screen(41.43, -81.80, 700.0, [cle()],
                     [HeightClass("crane", 60, "equipment")])
        assert res.analysis_required and res.status == "analysis_only"
        note = expected_plan_note(res)
        assert note["note"] == "G118B"
        ctl = res.controlling
        assert note["height_ft"] == pytest.approx(ctl.surface_elev_ft - 700.0, abs=0.1)

    def test_private_heliport_penetration_is_owner_coordination(self):
        # ~1,000 ft east of pad H2 on its 25:1 surface: 870 + 40 = 910
        res = screen(41.37116, -81.8278, 905.0, [sw_general()],
                     [HeightClass("crane", 60, "equipment")])
        assert res.owner_coordination_required and not res.faa_notification_required
        assert res.status == "owner_coordination"
        assert expected_plan_note(res)["note"] == "G118C"

    def test_200ft_agl_rule(self):
        res = screen(40.0, -83.0, 900.0, [], [HeightClass("tower", 210, "structure")])
        assert res.agl_notification and res.faa_notification_required
        assert res.controlling is None

    def test_closed_airports_skipped_unless_asked(self):
        closed = cle()
        closed.status = "CI"
        assert screen(*SITE, SITE_ELEV, [closed], HEIGHTS).facilities == []
        assert screen(*SITE, SITE_ELEV, [closed], HEIGHTS,
                      include_closed=True).facilities

    def test_marginal_band(self):
        res = screen(41.43, -81.80, 700.0, [cle()],
                     [HeightClass("just under", 0, "structure")])
        ctl = res.controlling
        surf = ctl.surface_elev_ft
        res2 = screen(41.43, -81.80, surf - 5.0, [cle()],
                      [HeightClass("just under", 0, "structure")])
        h = res2.controlling.heights[0]
        assert h.verdict == "marginal" and not h.penetrates and h.notify
        assert res2.faa_notification_required and not res2.strict_penetration

    def test_facility_without_runways_uses_reference_point(self):
        fac = Facility("X", "NoRunways", "A", 41.41, -81.84, 780.0)
        res = screen(*SITE, SITE_ELEV, [fac], HEIGHTS)
        f = res.facilities[0]
        assert f.runway is None and f.datum_source == "facility elevation"
        assert f.slope == 50.0                                 # no runway > 3,200


class TestHints:
    def test_equipment_default_is_small_bridge_crane(self):
        h = equipment_height_hint()
        assert h["height_ft"] == 60 and h["controlling"] == "Crane"

    def test_equipment_takes_tallest_work_type(self):
        h = equipment_height_hint(["earthwork", "pile_driving", "large_bridges"])
        assert h["height_ft"] == 100 and h["work_type"] == "large_bridges"
        assert equipment_height_hint(["bridge_painting"], bridge_height_ft=45)["height_ft"] == 55
        assert equipment_height_hint(["highway_lighting"], pole_height_ft=40)["height_ft"] == 40

    def test_pole_design_code(self):
        assert light_pole_height_from_design("A10B30") == 30
        assert light_pole_height_from_design("ITEM 625 LIGHT POLE, DESIGN A15B40") == 40
        assert light_pole_height_from_design("none") is None

    def test_structure_high_point_stackup(self):
        h = structure_high_point_hint(803.3, max_span_ft=110, feature_under="interstate")
        assert h["high_point_elev_ft"] == pytest.approx(803.3 + 16.5 + 5.0 + 3.5, abs=0.1)
        d = structure_high_point_hint(803.3, deck_elev_ft=815.5)
        assert d["high_point_elev_ft"] == 819.0


class TestPlanNotes:
    G118A = ("AIRWAY/HIGHWAY CLEARANCE FOR AIRPORTS AND HELIPORTS\n"
             "THIS PROJECT HAS BEEN IDENTIFIED AS BEING WITHIN THE INFLUENCE AREA OF A "
             "PUBLIC USE AIRPORT OR HELIPORT. NO TEMPORARY STRUCTURES OR CONSTRUCTION "
             "EQUIPMENT AT MAXIMUM OPERATING HEIGHT SHALL EXCEED A HEIGHT OF 60 FT. ... "
             "THE CONTRACTOR WILL BE REQUIRED TO FILE A NEW FAA FORM 7460-1, ADVISING THE "
             "FAA THAT THE FOLLOWING AERONAUTICAL STUDIES NUMBERS ARE BEING RESUBMITTED")
    G118B = ("AIRWAY/HIGHWAY CLEARANCE FOR AIRPORTS AND HELIPORTS  THIS PROJECT HAS BEEN "
             "IDENTIFIED AS BEING WITHIN THE INFLUENCE AREA OF A PUBLIC USE AIRPORT OR "
             "HELIPORT. NO TEMPORARY STRUCTURES OR CONSTRUCTION EQUIPMENT AT MAXIMUM "
             "OPERATING HEIGHT SHALL EXCEED A HEIGHT OF 28 FT. ... THE CONTRACTOR WILL BE "
             "REQUIRED TO SUBMIT FORM 7460-1 TO THE FAA.")
    G118C = ("AIRWAY/HIGHWAY CLEARANCE FOR AIRPORTS AND HELIPORTS THIS PROJECT HAS BEEN "
             "IDENTIFIED AS BEING WITHIN THE INFLUENCE AREA OF A PRIVATE-USE AIRPORT OR "
             "HELIPORT. NO TEMPORARY STRUCTURES OR CONSTRUCTION EQUIPMENT, AT MAXIMUM "
             "OPERATING HEIGHT, SHALL EXCEED A HEIGHT OF ___ FT.")

    def test_cuy_291_plan_note_is_g118a_with_blank_asn(self):
        (n,) = detect_g118_notes(self.G118A)
        assert n["note"] == "G118A" and n["height_ft"] == 60 and n["asn_blank"]

    def test_g118b_height_read(self):
        (n,) = detect_g118_notes(self.G118B)
        assert n["note"] == "G118B" and n["height_ft"] == 28 and not n["asn_blank"]

    def test_g118c_blank_height(self):
        (n,) = detect_g118_notes(self.G118C)
        assert n["note"] == "G118C" and n["height_blank"]

    def test_asn_filled(self):
        n = detect_g118_notes(self.G118A.replace(
            "NUMBERS ARE BEING", "NUMBERS 2026-AGL-1234-OE ARE BEING"))[0]
        assert n["asn"] == "2026-AGL-1234-OE" and not n["asn_blank"]

    def test_no_note(self):
        assert detect_g118_notes("GENERAL NOTES\nITEM 511 CLASS QC2 CONCRETE") == []


def test_to_dms():
    assert to_dms(41.403147, "lat") == "41° 24' 11.33\" N"
    assert to_dms(-81.825317, "lon") == "81° 49' 31.14\" W"
    assert to_dms(40.0, "lat") == "40° 00' 00.00\" N"
    assert to_dms(39.99999999, "lat") == "40° 00' 00.00\" N"


def test_units():
    assert NM_FT == pytest.approx(6076.115) and MI_FT == 5280
