"""Staged composite CB27-48 beam: transfer -> slab cast -> composite ->
long-term, with AASHTO time-dependent materials.

Unlocks the two things the static models cannot give:
* per-tendon, per-stage losses (TNDN_LOSS_FORCE) -> the real effective
  prestress replacing the notebook's f_pe = 160 ksi placeholder
* M_dnc (the beam-only moment from the wet slab, stage 2) and true
  composite behavior for the Eq. 1.16 cracking moment

Stages:
  CS1 "Transfer"  : girder activated at 3 days, self-weight + pretension
  CS2 "SlabCast"  : 5-in CIP topping weight on the BARE beam (-> M_dnc)
  CS3 "Composite" : slab becomes part of the section (CompSec), then
                    ~10,000 days of creep/shrinkage/relaxation
"""
import json

from civilpy.structural.midas import MidasCivil
from civilpy.structural.psc_section import (
    box_beam_shape, strands_from_odot_design, midas_tendon_payloads,
)

m = MidasCivil()
L, NEL = 840.0, 14
E_G, E_S = 4768.9, 3823.7          # 7 ksi girder, 4.5 ksi CIP slab


def step(name, method, path, body=None, ok=True):
    try:
        r = m.request(method, path, body, timeout=550, retries=0)
        print(f"[{name}] OK {str(r)[:60]}")
        return r
    except Exception as e:
        print(f"[{name}] ERR {str(e)[-120:]}")
        if ok:
            raise


step("new", "POST", "/doc/new", {"Argument": {}})
step("units", "PUT", "/db/UNIT", {"Assign": {"1": {
    "FORCE": "KIPS", "DIST": "IN", "HEAT": "BTU", "TEMPER": "F"}}})
step("matl", "PUT", "/db/MATL", {"Assign": {
    "1": {"TYPE": "USER", "NAME": "Girder-7ksi", "THMAL_UNIT": "F",
          "bMASS_DENS": False, "DAMP_RAT": 0.0,
          "PARAM": [{"P_TYPE": 2, "MASS": 0.0, "ELAST": E_G,
                     "POISN": 0.2, "THERMAL": 6.0e-06,
                     "DEN": round(0.150 / 1728.0, 9)}]},
    "2": {"TYPE": "USER", "NAME": "Strand-270LR", "THMAL_UNIT": "F",
          "bMASS_DENS": False, "DAMP_RAT": 0.0,
          "PARAM": [{"P_TYPE": 2, "MASS": 0.0, "ELAST": 28500.0,
                     "POISN": 0.3, "THERMAL": 6.5e-06, "DEN": 0.0}]},
    "3": {"TYPE": "USER", "NAME": "Slab-4.5ksi", "THMAL_UNIT": "F",
          "bMASS_DENS": False, "DAMP_RAT": 0.0,
          "PARAM": [{"P_TYPE": 2, "MASS": 0.0, "ELAST": E_S,
                     "POISN": 0.2, "THERMAL": 6.0e-06,
                     "DEN": round(0.150 / 1728.0, 9)}]},
}})

# ── time-dependent materials: AASHTO creep/shrinkage + ACI strength ─────
step("tdmt", "PUT", "/db/TDMT", {"Assign": {
    "1": {"NAME": "CS-Girder", "CODE": "AASHTO", "STR": 7.0, "HU": 70,
          "AGE": 3, "VOL": 2.85, "bEXPOSE": False},
    "2": {"NAME": "CS-Slab", "CODE": "AASHTO", "STR": 4.5, "HU": 70,
          "AGE": 3, "VOL": 2.26, "bEXPOSE": False},
}})
# steam-cured precast strength gain (ACI a=1, b=0.95); moist slab 4/0.85
step("tdme", "PUT", "/db/TDME", {"Assign": {
    "1": {"NAME": "FC-Girder", "TYPE": "CODE", "CODENAME": "ACI",
          "STRENGTH": 7.0, "A": 1.0, "B": 0.95},
    "2": {"NAME": "FC-Slab", "TYPE": "CODE", "CODENAME": "ACI",
          "STRENGTH": 4.5, "A": 4.0, "B": 0.85},
}})
step("tmat", "PUT", "/db/TMAT", {"Assign": {
    "1": {"TDMT_NAME": "CS-Girder", "TDME_NAME": "FC-Girder"},
    "3": {"TDMT_NAME": "CS-Slab", "TDME_NAME": "FC-Slab"},
}})

# ── composite PSC-Value section: box polygon + 48 x 5 CIP slab ──────────
box = box_beam_shape("CB27-48")
outer = [{"X": y, "Y": z} for y, z in box.outline]
inner = [{"X": y, "Y": z} for y, z in reversed(box.voids[0])]
sect = {
    "SECTTYPE": "COMPOSITE", "SECT_NAME": "CB27-48+slab", "CALC_OPT": True,
    "SECT_BEFORE": {
        "SHAPE": "PC",
        "SECT_I": {"vSIZE": [27.0, 48.0, 6.0, 6.0],
                   "OUTER_POLYGON": [{"VERTEX": outer}],
                   "INNER_POLYGON": [{"VERTEX": inner}]},
        "SHEAR_CHK": True,
        "SHEAR_CHK_POS": [[0.0, 13.5, 27.0], [0, 0, 0]],
        "USE_AUTO_QY": [[True, True, True], [False, False, False]],
        "WEB_THICK": [12.0, 0],
        "USE_WEB_THICK_SHEAR": [[True, True, True],
                                [False, False, False]],
        "MATL_ELAST": E_G / E_S, "MATL_DENS": 1.0,
        "MATL_POIS_S": 0.2, "MATL_POIS_C": 0.2, "MATL_THERMAL": 1.0,
        "USE_MULTI_ELAST": False, "LONGTERM_ESEC": 0.0,
        "SHRINK_ESEC": 0.0,
        "OFFSET_PT": "CC", "OFFSET_CENTER": 0, "USER_OFFSET_REF": 0,
        "HORZ_OFFSET_OPT": 0, "USERDEF_OFFSET_YI": 0.0,
        "VERT_OFFSET_OPT": 0, "USERDEF_OFFSET_ZI": 0.0,
        "USE_SHEAR_DEFORM": True, "USE_WARPING_EFFECT": False,
    },
    "SECT_AFTER": {
        "SECT_I": {"vSIZE": [48.0, 0.0], "BUILT_FLAG": 1},
        "SECT_J": {"vSIZE": [48.0, 5.0, 0.0]},
    },
}
step("sect", "PUT", "/db/SECT", {"Assign": {"1": sect}})

# ── mesh, groups, supports ───────────────────────────────────────────────
nodes = {str(i + 1): {"X": i * 60.0, "Y": 0.0, "Z": 0.0}
         for i in range(NEL + 1)}
elems = {str(i + 1): {"TYPE": "BEAM", "MATL": 1, "SECT": 1,
                      "NODE": [i + 1, i + 2], "ANGLE": 0}
         for i in range(NEL)}
step("node", "PUT", "/db/NODE", {"Assign": nodes})
step("elem", "PUT", "/db/ELEM", {"Assign": elems})
step("grup", "PUT", "/db/GRUP", {"Assign": {"1": {
    "NAME": "GIRDER", "P_TYPE": 0,
    "N_LIST": list(range(1, NEL + 2)),
    "E_LIST": list(range(1, NEL + 1))}}})
step("bngr", "PUT", "/db/BNGR", {"Assign": {"1": {"NAME": "SUP"}}})
step("ldgr", "PUT", "/db/LDGR", {"Assign": {
    "1": {"NAME": "G-SW"}, "2": {"NAME": "G-PS"},
    "3": {"NAME": "G-SLABW"}}})
step("cons", "PUT", "/db/CONS", {"Assign": {
    "1": {"ITEMS": [{"ID": 1, "CONSTRAINT": "1111000",
                     "GROUP_NAME": "SUP"}]},
    str(NEL + 1): {"ITEMS": [{"ID": 2, "CONSTRAINT": "0111000",
                              "GROUP_NAME": "SUP"}]}}})

# ── loads (each in its stage's load group) ───────────────────────────────
step("stld", "PUT", "/db/STLD", {"Assign": {
    "1": {"NO": 1, "NAME": "SW", "TYPE": "CS", "DESC": "girder self wt"},
    "2": {"NO": 2, "NAME": "PS", "TYPE": "CS", "DESC": "pretension"},
    "3": {"NO": 3, "NAME": "SLABW", "TYPE": "CS", "DESC": "wet slab"},
}})
step("bodf", "PUT", "/db/BODF", {"Assign": {"1": {
    "LCNAME": "SW", "GROUP_NAME": "G-SW", "FV": [0, 0, -1]}}})
w_slab = 48.0 * 5.0 * 0.150 / 1728.0          # 0.0208 k/in wet topping
bmld = {str(e): {"ITEMS": [{
    "ID": 1, "LCNAME": "SLABW", "GROUP_NAME": "G-SLABW", "CMD": "BEAM",
    "TYPE": "UNILOAD", "DIRECTION": "GZ", "USE_PROJECTION": False,
    "USE_ECCEN": False, "D": [0, 1, 0, 0],
    "P": [-w_slab, -w_slab, 0, 0]}]} for e in range(1, NEL + 1)}
step("bmld", "PUT", "/db/BMLD", {"Assign": bmld})

# ── tendons ──────────────────────────────────────────────────────────────
strands = strands_from_odot_design("CB27-48", 70)
base = midas_tendon_payloads(strands, elems=list(range(1, NEL + 1)),
                             length_in=L, matl_id=2,
                             jack_stress_ksi=202.5, load_case="PS")
for t in base["TDPL"].values():
    t["ITEMS"][0]["GROUP_NAME"] = "G-PS"
step("tdnt", "PUT", "/db/TDNT", {"Assign": base["TDNT"]})
step("tdna", "PUT", "/db/TDNA", {"Assign": base["TDNA"]})
step("tdpl", "PUT", "/db/TDPL", {"Assign": base["TDPL"]})

# ── construction stages ──────────────────────────────────────────────────
step("stag", "PUT", "/db/STAG", {"Assign": {
    "1": {"NAME": "Transfer", "NO": 1, "DURATION": 27,
          "bSV_RSLT": True, "bSV_STEP": False, "bLOAD_STEP": False,
          "ADD_STEP": [],
          "ACT_ELEM": [{"GRUP_NAME": "GIRDER", "AGE": 3}],
          "ACT_BNGR": [{"BNGR_NAME": "SUP", "POS": "DEFORMED"}],
          "ACT_LOAD": [{"LOAD_NAME": "G-SW", "DAY": "FIRST"},
                       {"LOAD_NAME": "G-PS", "DAY": "FIRST"}]},
    "2": {"NAME": "SlabCast", "NO": 2, "DURATION": 30,
          "bSV_RSLT": True, "bSV_STEP": False, "bLOAD_STEP": False,
          "ADD_STEP": [],
          "ACT_LOAD": [{"LOAD_NAME": "G-SLABW", "DAY": "FIRST"}]},
    "3": {"NAME": "Composite", "NO": 3, "DURATION": 9940,
          "bSV_RSLT": True, "bSV_STEP": False, "bLOAD_STEP": False,
          "ADD_STEP": [3000, 6000]},
}})

# slab becomes structural at CS3, 30 days old (cast at CS2 start)
step("cscs", "PUT", "/db/cscs", {"Assign": {"1": {
    "ASTAGE": "Transfer", "SEC": 1, "TYPE": "GENERAL", "bTAP": False,
    "vPARTINFO": [
        {"PART": 1, "MTYPE": "ELEM", "MAT": "", "CSTAGE": "", "AGE": 3,
         "PARTINFO_H": 0, "PARTINFO_VS": 2.85, "PARTINFO_M": 0,
         "AREA": 1, "ASY": 1, "ASZ": 1, "IXX": 1, "IYY": 1, "IZZ": 1,
         "WAREA": 1, "IW": 1},
        {"PART": 2, "MTYPE": "MATL", "MAT": "3", "CSTAGE": "Composite", "AGE": 30,
         "PARTINFO_H": 0, "PARTINFO_VS": 2.26, "PARTINFO_M": 0,
         "AREA": 1, "ASY": 1, "ASZ": 1, "IXX": 1, "IYY": 1, "IZZ": 1,
         "WAREA": 1, "IW": 1},
    ]}}})

step("anal", "POST", "/doc/ANAL", {"Argument": {}})
print("STAGED COMPOSITE BUILD COMPLETE")
