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
``/db/MVCT`` rejects every write, including an empty body ("Wrong Field"),
so the control record cannot be created from the API.  Once it exists this
script runs unattended.

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

LANE = "L1"
GROUP = "GIRDER"


def ensure_control(client) -> bool:
    """The moving-load control record must already exist (UI-created)."""
    got = client.request("GET", "db/MVCT")
    if "MVCT" in got and got["MVCT"]:
        return True
    print("BLOCKED: no Moving Load Analysis Control record.\n"
          "  In Civil NX: Analysis > Moving Load Analysis Control > OK,\n"
          "  then re-run.  The API cannot create it (every write, including\n"
          "  an empty body, returns 'Wrong Field').")
    return False


def build_lane(client) -> None:
    client.request("PUT", "db/LLAN", {"Assign": {"1": {
        "LANE_NAME": LANE,
        "COMMON": {"VEHICULAR_LOAD": "LANE", "ECCEN": 0.0,
                   "IMPACT_FACTOR": 0.0, "SKEW": 0.0,
                   "WIDTH": 12.0 * 12.0, "CENT_F": 0.001,
                   "LOAD_DIST": "CROSS", "GROUP_NAME": GROUP},
        "LANE_ITEMS": [{"ELEM": e, "ECCEN": 0.0}
                       for e in range(1, 15)],
    }}})


def push_pairs(client) -> dict[str, tuple[str, str]]:
    """One DB vehicle and one BDM-defined vehicle per rating load."""
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


def push_cases(client, pairs) -> dict[str, tuple[str, str]]:
    """One single-lane moving load case per vehicle, no multiple presence."""
    assign, cases, cid = {}, {}, 1
    for name, (db_name, bdm_name) in pairs.items():
        for veh in (db_name, bdm_name):
            assign[str(cid)] = {
                "LCNAME": veh, "TYPE": 0,
                "DEFAULT": {
                    "COMB_OPTION": 0, "LANE_FACTOR_TYPE": 0,
                    "SCALE_FACTORS": [1.0],
                    "SUB_LOAD_DATAS": [{
                        "VEHICLE_TYPE": "VL", "VEHICLE_NAME": veh,
                        "MIN_NUM": 1, "MAX_NUM": 1,
                        "LANE_NAMES": [LANE],
                    }],
                },
            }
            cid += 1
        cases[name] = (db_name, bdm_name)
    client.request("PUT", "db/mvld", {"Assign": assign})
    return cases


def midspan_moment(client, case_name: str) -> float | None:
    """Max |My| envelope on the midspan element for one moving load case."""
    resp = client.result_table(
        "BeamForce", table_type="BEAMFORCE",
        components=["Elem", "Load", "Moment-y"],
        node_elems={"KEYS": [7, 8]},
        load_case_names=[f"{case_name}(MV:all)"])
    rows = parse_result_table(resp)
    vals = []
    for r in rows:
        for k, v in r.items():
            if "Moment-y" in str(k):
                try:
                    vals.append(abs(float(v)))
                except (TypeError, ValueError):
                    pass
    return max(vals) if vals else None


def main() -> int:
    client = MidasCivil(timeout=300, reconnect_retries=0)
    if not ensure_control(client):
        return 1
    print("pushing vehicle pairs ...")
    pairs = push_pairs(client)
    build_lane(client)
    cases = push_cases(client, pairs)
    print(f"analyzing ({2 * len(cases)} moving load cases) ...")
    client.analyze()

    print(f"\n{'vehicle':<10}{'DB (kip-ft)':>14}{'BDM (kip-ft)':>14}"
          f"{'diff':>9}  verdict")
    print("-" * 60)
    worst = 0.0
    for name, (db_name, bdm_name) in cases.items():
        m_db = midspan_moment(client, db_name)
        m_bdm = midspan_moment(client, bdm_name)
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
