"""Are Midas's built-in rating vehicles current with the ODOT BDM?

A standard-DB vehicle record stores only ``VEHICLE_TYPE_NAME`` and
``STANDARD_CODE`` -- the axle train is never exposed, so it cannot be read
back and compared.  This script answers the question the other way round,
by **load effect**: run the same span, same lane, same everything, once
with Midas's DB vehicle and once with an explicit axle train taken off the
BDM figure, then diff the envelopes.  Identical envelopes mean identical
axle trains; a difference is the discrepancy, already expressed in the
units that matter.

PREREQUISITE -- one manual step, once per model:
    Analysis > Moving Load Analysis Control > OK
``/db/MVCT`` is modify-only: PUT works normally once the record exists
(full body, a single field, even an empty body), but while it is absent
every PUT returns "Wrong Field".  Creating it is the UI's job.  Once it
exists this script runs unattended.

Usage:
    python verify_db_vehicles.py            # against the open model
"""
from __future__ import annotations

import sys

from civilpy.structural.aashto.vehicles import RATING_VEHICLES
from civilpy.structural.midas import MidasCivil, parse_result_table
from civilpy.structural.midas_models import (
    BDM_908_STANDARD_DB, midas_standard_vehicle, midas_vehicle_payload,
)

GROUP = "GIRDER"


def ensure_control(client) -> bool:
    """The moving-load control record must already exist (UI-created)."""
    got = client.request("GET", "db/MVCT")
    if "MVCT" in got and got["MVCT"]:
        return True
    print("BLOCKED: no Moving Load Analysis Control record.\n"
          "  In Civil NX: Analysis > Moving Load Analysis Control > OK,\n"
          "  then re-run.  /db/MVCT is modify-only -- PUT works once the\n"
          "  record exists, but returns 'Wrong Field' while it is absent.")
    return False


def lane_name(client, n_elems: int = 14) -> str:
    """Name of the traffic lane, creating one only if none exists.

    Schema read off a UI-created record (2026-07-28) -- LL_NAME lives
    inside COMMON, LOAD_DIST is "LANE", and the items carry
    ECC/FACT/SPAN_START/ECCEN_VERT_LOAD/CENT_F.  Like /db/MVCT, this
    table rejects every write with "Wrong Field" until a record exists,
    so a missing lane has to be added once through the UI
    (Load > Moving Load > Traffic Line Lanes, Lane Element method --
    Cross Beam needs transverse members a line-girder model lacks).
    """
    got = client.request("GET", "db/llan").get("LLAN", {})
    if got:
        return got[sorted(got, key=int)[0]]["COMMON"]["LL_NAME"]
    client.request("PUT", "db/llan", {"Assign": {"1": {
        "COMMON": {"LL_NAME": "Lane1", "LOAD_DIST": "LANE",
                   "GROUP_NAME": "", "SKEW_START": 0, "SKEW_END": 0,
                   "MOVING": "BOTH", "WHEEL_SPACE": 72.0,
                   "WIDTH": 120.0, "OPT_AUTO_LANE": False,
                   "ALLOW_WIDTH": 120.0},
        "LANE_ITEMS": [{"ELEM": e, "ECC": 0, "FACT": 0,
                        "SPAN_START": False, "ECCEN_VERT_LOAD": 0,
                        "CENT_F": 0.5} for e in range(1, n_elems + 1)],
    }}})
    return "Lane1"


def push_pairs(client) -> dict[str, tuple[str, str]]:
    """One DB vehicle and one BDM-defined vehicle per rating load."""
    # PUT appends rather than replacing, so clear first
    for vid in sorted(client.request("GET", "db/mvhl").get("MVHL", {}),
                      key=int, reverse=True):
        client.request("DELETE", f"db/mvhl/{vid}")
    assign, pairs, vid = {}, {}, 1
    for name, (code, type_name) in BDM_908_STANDARD_DB.items():
        if name not in RATING_VEHICLES:
            continue
        db_name, bdm_name = f"DB_{name}", f"BDM_{name}"
        assign[str(vid)] = midas_standard_vehicle(
            type_name, name=db_name, standard_code=code, im_percent=0.0)
        assign[str(vid + 1)] = midas_vehicle_payload(
            RATING_VEHICLES[name], im_percent=0.0)
        assign[str(vid + 1)]["VEHICLE_LOAD_NAME"] = bdm_name
        pairs[name] = (db_name, bdm_name)
        vid += 2
    client.request("PUT", "db/mvhl", {"Assign": assign})
    return pairs


def push_cases(client, pairs, lane: str) -> dict[str, tuple[str, str]]:
    """One single-lane moving load case per vehicle.

    Body per the API manual for db/MVLD (article 35959068573209), AASHTO
    LRFD example.  Note ``COMB_OPTION`` is the STRING "INDEPENDENT" and
    the lane counts are ``MIN_LOADED_LANE``/``MAX_LOADED_LANE`` -- both
    are easy to get wrong, and a wrong field yields "Wrong Field" with no
    hint which one.  Both variants of a vehicle get an identical case, so
    the multiple-presence factors cancel in the comparison.
    """
    # drop anything already there so ids and names are predictable
    for cid in sorted(client.request("GET", "db/mvld").get("MVLD", {}),
                      key=int, reverse=True):
        client.request("DELETE", f"db/mvld/{cid}")

    assign, cases, cid = {}, {}, 1
    for name, (db_name, bdm_name) in pairs.items():
        for veh in (db_name, bdm_name):
            assign[str(cid)] = {
                "LCNAME": veh, "DESC": "", "TYPE": 0,
                "DEFAULT": {
                    "SCALE_FACTORS": [1.2, 1, 0.85, 0.65, 0.65, 0.65],
                    "COMB_OPTION": "INDEPENDENT",
                    "LANE_FACTOR_TYPE": 1,
                    "SUB_LOAD_DATAS": [{
                        "VEHICLE_TYPE": "VL", "VEHICLE_NAME": veh,
                        "SCALE_FACTOR": 1,
                        "MIN_LOADED_LANE": 1, "MAX_LOADED_LANE": 1,
                        "LANE_NAMES": [lane],
                    }],
                },
            }
            cid += 1
        cases[name] = (db_name, bdm_name)
    client.request("PUT", "db/mvld", {"Assign": assign})
    return cases


def midspan_envelopes(client) -> dict[str, float]:
    """Max |My| at midspan for every moving load case, keyed by case name.

    Pulled in one request with no load-case filter, then grouped by the
    table's own Load column -- Midas decorates moving-load case names
    (e.g. "SU5(MV:all)"), so matching on a guessed suffix is fragile.
    """
    resp = client.result_table(
        "BeamForce", table_type="BEAMFORCE",
        components=["Elem", "Load", "Moment-y"],
        node_elems={"KEYS": [7, 8]})
    out: dict[str, float] = {}
    for row in parse_result_table(resp):
        load = next((str(v) for k, v in row.items()
                     if str(k).strip().lower() == "load"), None)
        if not load:
            continue
        case = load.split("(")[0].strip()
        for k, v in row.items():
            if "Moment-y" in str(k):
                try:
                    m = abs(float(v))
                except (TypeError, ValueError):
                    continue
                out[case] = max(out.get(case, 0.0), m)
    return out


def main() -> int:
    client = MidasCivil(timeout=300, reconnect_retries=0)
    if not ensure_control(client):
        return 1
    print("pushing vehicle pairs ...")
    pairs = push_pairs(client)
    lane = lane_name(client)
    print(f"using traffic lane {lane!r}")
    cases = push_cases(client, pairs, lane)
    print(f"analyzing ({2 * len(cases)} moving load cases) ...")
    client.analyze()
    env = midspan_envelopes(client)
    print(f"result table returned {len(env)} load cases")

    print(f"\n{'vehicle':<10}{'DB (kip-ft)':>14}{'BDM (kip-ft)':>14}"
          f"{'diff':>9}  verdict")
    print("-" * 60)
    worst = 0.0
    for name, (db_name, bdm_name) in cases.items():
        m_db = env.get(db_name)
        m_bdm = env.get(bdm_name)
        if not m_db or not m_bdm:
            print(f"{name:<10}{'-':>14}{'-':>14}{'':>9}  NO RESULT "
                  f"(unresolved vehicle name applies zero load)")
            continue
        d = 100.0 * (m_db / m_bdm - 1.0)
        worst = max(worst, abs(d))
        verdict = "match" if abs(d) < 0.5 else "*** DIFFERS ***"
        print(f"{name:<10}{m_db:14,.1f}{m_bdm:14,.1f}{d:8.2f}%  {verdict}")
    print(f"\nlargest deviation: {worst:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
