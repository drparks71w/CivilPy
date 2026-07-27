"""Six-beam CB27-48 bridge (70 ft, 24-ft roadway) built via the Civil NX
JSON API — the authoritative capstone build (v5, moving loads working).

Geometry per PSBD-1-25 (0-degree skew): solid 3'-3" end blocks (lifting
inserts at 8"/20" noded for erection cases; end diaphragm cl 2'-6"), two
18-in intermediate diaphragm blocks at third points, bearings as spring
supports at the real pad locations (2 per end, 6" in, 2'-4" c-c, B2 pad
stiffness), with transverse
connection through the four diaphragm lines only: a with/without test
showed the per-node key strips changed the HL-93 per-girder envelopes by
< 0.5% on this bridge (torsionally stiff closed boxes + 4 diaphragms),
so they are omitted per that evidence.  Caveat: lanes ride girder lines,
so between-beam wheel placement — where real keyways work locally — is
not exercised by this idealization.

NOTE: elastic links are banned throughout — Civil NX's moving-load
post-processor crashes reading link influence results (RB_ELNK3,
reported defect) — so the bearing outriggers are stiff weightless beams
(honest anyway: they pass through the solid end block).

Vehicles: standard-DB HL-93TRK and HS20-FTG (STANDARD_CODE is REQUIRED
or the vehicle silently applies zero load), Ohio legal 5C1, and ODOT
BDM's EV3 injected from civilpy (absent from Midas's Ohio DB).
"""
import json

from dataclasses import replace

from civilpy.structural.aashto.vehicles import EMERGENCY_VEHICLES
from civilpy.structural.midas import MidasCivil
from civilpy.structural.midas_models import (
    midas_standard_vehicle, midas_vehicle_payload,
)
from civilpy.structural.odot.box_beam import bearing_pad
from civilpy.structural.psc_section import (
    box_beam_shape, strands_from_odot_design,
    midas_section_payload, midas_tendon_payloads,
)

m = MidasCivil()
NG, DY, L = 6, 48.0, 840.0
STA = [0, 6, 8, 20, 30, 39, 60, 120, 180, 231, 240, 249, 300, 360, 420,
       480, 540, 591, 600, 609, 660, 720, 780, 801, 810, 820, 832, 834,
       840]
SOLID = [(0.0, 39.0), (231.0, 249.0), (591.0, 609.0), (801.0, 840.0)]
DIAPH_X = [30.0, 240.0, 600.0, 810.0]
BRG_X = [6.0, 834.0]
NS = len(STA)


def nid(g, s):
    return g * 1000 + s + 1


def is_solid(xa, xb):
    mid = (xa + xb) / 2.0
    return any(a <= mid <= b for a, b in SOLID)


def step(name, method, path, body=None):
    r = m.request(method, path, body, timeout=550, retries=0)
    print(f"[{name}] {str(r)[:70]}")
    return r


def rect(name, h, b):
    return {"SECTTYPE": "DBUSER", "SECT_NAME": name,
            "SECT_BEFORE": {"SHAPE": "SB", "DATATYPE": 2,
                            "SECT_I": {"vSIZE": [h, b]},
                            "OFFSET_PT": "CC", "OFFSET_CENTER": 0,
                            "USER_OFFSET_REF": 0, "HORZ_OFFSET_OPT": 0,
                            "USERDEF_OFFSET_YI": 0.0,
                            "VERT_OFFSET_OPT": 0,
                            "USERDEF_OFFSET_ZI": 0.0,
                            "USE_SHEAR_DEFORM": True,
                            "USE_WARPING_EFFECT": False}}


step("new", "POST", "/doc/new", {"Argument": {}})
step("units", "PUT", "/db/UNIT", {"Assign": {"1": {
    "FORCE": "KIPS", "DIST": "IN", "HEAT": "BTU", "TEMPER": "F"}}})
step("matl", "PUT", "/db/MATL", {"Assign": {
    "1": {"TYPE": "USER", "NAME": "Conc-7ksi", "THMAL_UNIT": "F",
          "bMASS_DENS": False, "DAMP_RAT": 0.0,
          "PARAM": [{"P_TYPE": 2, "MASS": 0.0, "ELAST": 4768.9,
                     "POISN": 0.2, "THERMAL": 6.0e-06,
                     "DEN": round(0.150 / 1728.0, 9)}]},
    "2": {"TYPE": "USER", "NAME": "Strand-270LR", "THMAL_UNIT": "F",
          "bMASS_DENS": False, "DAMP_RAT": 0.0,
          "PARAM": [{"P_TYPE": 2, "MASS": 0.0, "ELAST": 28500.0,
                     "POISN": 0.3, "THERMAL": 6.5e-06, "DEN": 0.0}]},
    "3": {"TYPE": "USER", "NAME": "StiffWeightless", "THMAL_UNIT": "F",
          "bMASS_DENS": False, "DAMP_RAT": 0.0,
          "PARAM": [{"P_TYPE": 2, "MASS": 0.0, "ELAST": 1.0e6,
                     "POISN": 0.2, "THERMAL": 0.0, "DEN": 0.0}]},
}})

box = box_beam_shape("CB27-48")
solid = replace(box, name="CB27-48-solid", voids=())
step("sect", "PUT", "/db/SECT", {"Assign": {
    "1": midas_section_payload(box),
    "3": rect("Diaphragm", 27.0, 12.0),
    "4": midas_section_payload(solid),
}})

# ── grillage ─────────────────────────────────────────────────────────────
nodes, elems = {}, {}
girder_elems = {g: [] for g in range(NG)}
for g in range(NG):
    for s, x in enumerate(STA):
        nodes[str(nid(g, s))] = {"X": x, "Y": g * DY, "Z": 0.0}
    for s in range(NS - 1):
        eid = g * 100 + s + 1
        sect = 4 if is_solid(STA[s], STA[s + 1]) else 1
        elems[str(eid)] = {"TYPE": "BEAM", "MATL": 1, "SECT": sect,
                           "NODE": [nid(g, s), nid(g, s + 1)], "ANGLE": 0}
        girder_elems[g].append(eid)
tid = 10000
for g in range(NG - 1):
    for s, x in enumerate(STA):
        if x not in DIAPH_X:
            continue
        tid += 1
        elems[str(tid)] = {"TYPE": "BEAM", "MATL": 1, "SECT": 3,
                           "NODE": [nid(g, s), nid(g + 1, s)],
                           "ANGLE": 0}

# bearing connections: node-to-node RIGID links (no dummy elements);
# pads sit under the soffit, 13.5 in below the element axis.  Verified
# 2026-07-27: RIGID links coexist fine with moving-load results — the
# earlier RB_ELNK3 crash traces to the GEN-type link records.
bid, brg_nodes, brg_links = 50000, [], {}
lid = 0
for g in range(NG):
    for x in BRG_X:
        s = STA.index(x)
        for dy in (-14.0, 14.0):
            bid += 1
            nodes[str(bid)] = {"X": x, "Y": g * DY + dy, "Z": -13.5}
            lid += 1
            brg_links[str(lid)] = {"NODE": [nid(g, s), bid],
                                   "LINK": "RIGID", "ANGLE": 0,
                                   "BNGR_NAME": ""}
            brg_nodes.append(bid)
step("node", "PUT", "/db/NODE", {"Assign": nodes})
step("elem", "PUT", "/db/ELEM", {"Assign": elems})
step("elnk", "PUT", "/db/elnk", {"Assign": brg_links})

# bearing springs from the sheet-6 B2 pad data
b2 = bearing_pad("B2")
A = b2.length * b2.width
hrt = 2 * b2.t_external + (b2.n_laminates - 1) * b2.t_internal
S = A / (2 * b2.t_internal * (b2.length + b2.width))
kv = 4.8 * 0.095 * S ** 2 * A / hrt
kh = 0.130 * A / hrt
nspr = {str(bn): {"ITEMS": [{
    "ID": 1, "TYPE": "LINEAR", "GROUP_NAME": "",
    "SDR": [round(kh, 2), round(kh, 2), round(kv, 0), 0, 0, 0],
    "F_S": [False] * 6, "DAMPING": False}]} for bn in brg_nodes}
step("nspr", "PUT", "/db/nspr", {"Assign": nspr})
print(f"B2 pads: kv={kv:.0f} k/in, kh={kh:.1f} k/in x {len(brg_nodes)}")

# ── load cases, self weight, temporary barrier ───────────────────────────
step("stld", "PUT", "/db/STLD", {"Assign": {
    "1": {"NO": 1, "NAME": "DC", "TYPE": "D", "DESC": "self weight"},
    "2": {"NO": 2, "NAME": "PS", "TYPE": "PS", "DESC": "prestress"},
    "3": {"NO": 3, "NAME": "TB", "TYPE": "D", "DESC": "temp barrier"},
}})
step("bodf", "PUT", "/db/BODF", {"Assign": {"1": {
    "LCNAME": "DC", "GROUP_NAME": "", "FV": [0, 0, -1]}}})
bmld = {str(e): {"ITEMS": [{
    "ID": 1, "LCNAME": "TB", "GROUP_NAME": "", "CMD": "BEAM",
    "TYPE": "UNILOAD", "DIRECTION": "GZ", "USE_PROJECTION": False,
    "USE_ECCEN": False, "D": [0, 1, 0, 0],
    "P": [-0.04167, -0.04167, 0, 0]}]} for e in girder_elems[5]}
step("bmld", "PUT", "/db/BMLD", {"Assign": bmld})

# ── tendons ──────────────────────────────────────────────────────────────
strands = strands_from_odot_design("CB27-48", 70)
base = midas_tendon_payloads(strands, elems=[], length_in=L, matl_id=2,
                             jack_stress_ksi=202.5)
tdna, tdpl = {}, {}
k = 0
for g in range(NG):
    for key in sorted(base["TDNA"], key=int):
        k += 1
        prof = json.loads(json.dumps(base["TDNA"][key]))
        prof["NAME"] = f"G{g + 1}-{prof['NAME']}"
        prof["ELEM"] = girder_elems[g]
        for pt in prof["PROF"]:
            pt["PT"][1] += g * DY
        tdna[str(k)] = prof
        tdpl[str(k)] = {"ITEMS": [{
            "ID": 1, "LCNAME": "PS", "GROUP_NAME": "",
            "TENDON_NAME": prof["NAME"], "TYPE": "STRESS",
            "ORDER": "BEGIN", "BEGIN": 202.5, "END": 0.0, "GROUTING": 0}]}
step("tdnt", "PUT", "/db/TDNT", {"Assign": base["TDNT"]})
step("tdna", "PUT", "/db/TDNA", {"Assign": tdna})
step("tdpl", "PUT", "/db/TDPL", {"Assign": tdpl})

# ── moving load: WORKING configuration ───────────────────────────────────
step("mvcd", "PUT", "/db/mvcd", {"Assign": {"1": {"CODE": "AASHTO LRFD"}}})
step("mvct", "PUT", "/db/MVCT", {"Assign": {"1": {
    "METHOD": "EXACT", "POINT": "INF", "iIGP": 0, "iIGPN": 3,
    "PLATE": "NODAL", "bSTRCALC": True, "bCONCURRENT": True,
    "FRAME": "AXIAL", "bCSTRCALC": True, "bCONCLINK": False,
    "bREAC": True, "bRG": False, "RGN": "", "bDISP": True, "bDG": False,
    "DGN": "", "bFM": True, "bFG": False, "FGN": "", "bL": False,
    "bLG": False, "LGN": ""}}})


def lane(name, girder, ecc):
    return {
        "COMMON": {"LL_NAME": name, "LOAD_DIST": "LANE",
                   "GROUP_NAME": "", "SKEW_START": 0.0, "SKEW_END": 0.0,
                   "MOVING": "BOTH", "WHEEL_SPACE": 72.0, "WIDTH": 144.0,
                   "OPT_AUTO_LANE": False, "ALLOW_WIDTH": 0.0},
        "LANE_ITEMS": [{"ELEM": e, "ECC": ecc, "CENT_F": 0.001,
                        "SPAN_START": i == 0}
                       for i, e in enumerate(girder_elems[girder])],
    }


step("llan", "PUT", "/db/llan", {"Assign": {
    "1": lane("Lane1", 1, 0.0), "2": lane("Lane2", 4, 0.0),
    "3": lane("TempLane", 2, 24.0)}})

# STANDARD_CODE is mandatory (verified: without it the vehicle stores but
# applies zero load); EV3 injected from civilpy — absent from Midas's DB
step("mvhl", "PUT", "/db/mvhl", {"Assign": {
    "1": midas_standard_vehicle("HL-93TRK"),
    "2": midas_standard_vehicle("HS20-FTG"),
    "3": midas_standard_vehicle("OH Legal load 5C1",
                                standard_code="OHDOT LOAD",
                                im_percent=0.0),
    "4": midas_vehicle_payload(EMERGENCY_VEHICLES["EV3"],
                               im_percent=33.0),
}})
SF = [1.2, 1.0, 0.85, 0.65, 0.65, 0.65]


def case(name, veh, lanes, minl, maxl, desc=""):
    return {"LCNAME": name, "DESC": desc, "TYPE": 0,
            "DEFAULT": {"COMB_OPTION": "COMBINED", "LANE_FACTOR_TYPE": 1,
                        "SCALE_FACTORS": SF,
                        "SUB_LOAD_DATAS": [{
                            "VEHICLE_TYPE": "VL", "VEHICLE_NAME": veh,
                            "SCALE_FACTOR": 1.0,
                            "MIN_LOADED_LANE": minl,
                            "MAX_LOADED_LANE": maxl,
                            "LANE_NAMES": lanes}]}}


step("mvld", "PUT", "/db/mvld", {"Assign": {
    "1": case("HL93", "HL-93TRK", ["Lane1", "Lane2"], 1, 2),
    "2": case("HS20", "HS20-FTG", ["Lane1", "Lane2"], 1, 2),
    "3": case("TEMP", "HL-93TRK", ["TempLane"], 1, 1, "work-zone lane"),
    "4": case("EV3", "EV3", ["Lane1"], 1, 1, "ODOT BDM emergency veh"),
}})

step("anal", "POST", "/doc/ANAL", {"Argument": {}})
print("SIX-BEAM BRIDGE BUILD COMPLETE (v5 — moving loads live)")
